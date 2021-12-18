import torch
import torch.nn as nn
import torch.nn.functional as F
from mmcv.cnn import (build_activation_layer, build_norm_layer, constant_init,
                      normal_init)
from mmcv.ops.modulated_deform_conv import ModulatedDeformConv2d
from mmcv.runner import BaseModule

from ..builder import NECKS
from ..utils import DYReLU

# Reference:
# https://github.com/microsoft/DynamicHead
# https://github.com/jshilong/SEPC


class DyDCNv2(nn.Module):
    """ModulatedDeformConv2d with normalization layer used in DyHead.

    Args:
        in_channels (int): Number of input channels.
        out_channels (int): Number of output channels.
        stride (int | tuple[int], optional): Stride of the convolution.
            Default: 1.
        norm_cfg (dict, optional): Config dict for normalization layer.
            Default: dict(type='GN', num_groups=16, requires_grad=True).
    """

    def __init__(self,
                 in_channels,
                 out_channels,
                 stride=1,
                 norm_cfg=dict(type='GN', num_groups=16, requires_grad=True)):
        super().__init__()
        self.with_norm = norm_cfg is not None
        bias = not self.with_norm
        self.conv = ModulatedDeformConv2d(
            in_channels, out_channels, 3, stride=stride, padding=1, bias=bias)
        self.norm = build_norm_layer(norm_cfg, out_channels)[1]

    def forward(self, x, offset, mask):
        """Forward function."""
        x = self.conv(x.contiguous(), offset, mask)
        if self.with_norm:
            x = self.norm(x)
        return x


class DyHeadBlock(nn.Module):
    """DyHead Block with three types of attention.

    HSigmoid arguments in default act_cfg follow official code, not paper.
    https://github.com/microsoft/DynamicHead/blob/master/dyhead/dyrelu.py

    Args:
        in_channels (int): Number of input channels.
        out_channels (int): Number of output channels.
        act_cfg (dict, optional): Config dict for activation layer.
            Default: dict(type='HSigmoid', bias=3.0, divisor=6.0).
    """

    def __init__(self,
                 in_channels,
                 out_channels,
                 act_cfg=dict(type='HSigmoid', bias=3.0, divisor=6.0)):
        super().__init__()
        # (offset_x, offset_y, mask) * kernel_size_y * kernel_size_x
        self.offset_and_mask_dim = 3 * 3 * 3
        self.offset_dim = 2 * 3 * 3

        self.spatial_conv_high = DyDCNv2(in_channels, out_channels)
        self.spatial_conv_mid = DyDCNv2(in_channels, out_channels)
        self.spatial_conv_low = DyDCNv2(in_channels, out_channels, stride=2)
        self.spatial_conv_offset = nn.Conv2d(
            in_channels, self.offset_and_mask_dim, 3, padding=1)
        self.scale_attn_conv = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Conv2d(out_channels, 1, 1),
            nn.ReLU(inplace=True))
        self.scale_attn_sigmoid = build_activation_layer(act_cfg)
        self.task_attn_module = DYReLU(out_channels)
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                normal_init(m, 0, 0.01)
        constant_init(self.spatial_conv_offset, 0)

    def forward(self, x):
        """Forward function."""
        outs = []
        for level, mid_feat in enumerate(x):
            # calculate offset and mask of DCNv2 from middle-level feature
            offset_and_mask = self.spatial_conv_offset(mid_feat)
            offset = offset_and_mask[:, :self.offset_dim, :, :]
            mask = offset_and_mask[:, self.offset_dim:, :, :].sigmoid()

            # spatial-aware attention
            mlvl_feats = [self.spatial_conv_mid(mid_feat, offset, mask)]
            if level > 0:
                mlvl_feats.append(
                    self.spatial_conv_low(x[level - 1], offset, mask))
            if level < len(x) - 1:
                # this upsample order is weird, but faster than natural order
                # https://github.com/microsoft/DynamicHead/issues/25
                mlvl_feats.append(
                    F.interpolate(
                        self.spatial_conv_high(x[level + 1], offset, mask),
                        size=mid_feat.shape[-2:],
                        mode='bilinear',
                        align_corners=True))

            # scale-aware attention and task-aware attention
            res_feat = torch.stack(mlvl_feats)
            attn_feats = [self.scale_attn_conv(feat) for feat in mlvl_feats]
            scale_attn = self.scale_attn_sigmoid(torch.stack(attn_feats))
            mean_feat = torch.mean(res_feat * scale_attn, dim=0, keepdim=False)
            outs.append(self.task_attn_module(mean_feat))

        return outs


@NECKS.register_module()
class DyHead(BaseModule):
    """DyHead neck consisting of multiple DyHead Blocks.

    See `Dynamic Head: Unifying Object Detection Heads with Attentions
    <https://arxiv.org/abs/2106.08322>`_ for details.

    Args:
        in_channels (int): Number of input channels.
        out_channels (int): Number of output channels.
        num_blocks (int, optional): number of DyHead Blocks. Default: 6.
        init_cfg (dict or list[dict], optional): Initialization config dict.
            Default: None.
    """

    def __init__(self, in_channels, out_channels, num_blocks=6, init_cfg=None):
        assert init_cfg is None, 'To prevent abnormal initialization ' \
                                 'behavior, init_cfg is not allowed to be set'
        super().__init__(init_cfg=init_cfg)
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.num_blocks = num_blocks

        dyhead_blocks = []
        for i in range(num_blocks):
            in_channels = self.in_channels if i == 0 else self.out_channels
            dyhead_blocks.append(DyHeadBlock(in_channels, self.out_channels))
        self.dyhead_blocks = nn.Sequential(*dyhead_blocks)

    def forward(self, inputs):
        """Forward function."""
        outs = self.dyhead_blocks(inputs)
        return tuple(outs)
