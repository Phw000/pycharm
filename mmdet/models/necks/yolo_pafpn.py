import torch
import torch.nn as nn
from mmcv.runner import BaseModule
from mmcv.cnn import ConvModule, DepthwiseSeparableConvModule

from ..utils import CSPLayer
from ..builder import NECKS


@NECKS.register_module()
class YOLOXPAFPN(BaseModule):
    """
    Path Aggregation Network used in YOLOX
    """

    def __init__(self,
                 deepen_factor=1.0,
                 in_channels=[256, 512, 1024],
                 out_channels=256,
                 upsample_cfg=dict(mode='nearest'),
                 depthwise=False,
                 conv_cfg=None,
                 norm_cfg=dict(type='BN', momentum=0.03, eps=0.001),
                 act_cfg=dict(type='Swish'),
                 init_cfg=None
                 ):
        super(YOLOXPAFPN, self).__init__(init_cfg)
        self.in_channels = in_channels
        self.out_channels = out_channels

        conv = DepthwiseSeparableConvModule if depthwise else ConvModule

        # build top-down blocks
        self.upsample = nn.Upsample(scale_factor=2, mode="nearest")
        self.reduce_layers = nn.ModuleList()
        self.top_down_blocks = nn.ModuleList()
        for idx in range(len(in_channels)-1, 0, -1):
            self.reduce_layers.append(
                ConvModule(in_channels[idx], in_channels[idx-1], 1,
                           conv_cfg=conv_cfg, norm_cfg=norm_cfg, act_cfg=act_cfg)
            )
            self.top_down_blocks.append(
                CSPLayer(in_channels[idx-1]*2, in_channels[idx-1],
                         num_blocks=round(3 * deepen_factor),
                         with_res_shortcut=False,
                         use_depthwise=depthwise,
                         conv_cfg=conv_cfg, norm_cfg=norm_cfg,
                         act_cfg=act_cfg)
            )

        # build bottom-up blocks
        self.downsamples = nn.ModuleList()
        self.bottom_up_blocks = nn.ModuleList()
        for idx in range(len(in_channels)-1):
            self.downsamples.append(
                conv(in_channels[idx],
                     in_channels[idx],
                     3,
                     stride=2,
                     padding=1,
                     conv_cfg=conv_cfg,
                     norm_cfg=norm_cfg,
                     act_cfg=act_cfg)
            )
            self.bottom_up_blocks.append(
                CSPLayer(
                    in_channels[idx]*2,
                    in_channels[idx+1],
                    num_blocks=round(3 * deepen_factor),
                    with_res_shortcut=False,
                    use_depthwise=depthwise,
                    conv_cfg=conv_cfg,
                    norm_cfg=norm_cfg,
                    act_cfg=act_cfg
                )
            )

        self.stems = nn.ModuleList()
        for i in range(len(in_channels)):
            self.stems.append(
                ConvModule(
                    in_channels[i],
                    out_channels,
                    1,
                    conv_cfg=conv_cfg,
                    norm_cfg=norm_cfg,
                    act_cfg=act_cfg
                ))

    def forward(self, inputs):
        """
        Args:
            inputs: input images.

        Returns:
            Tuple[Tensor]: FPN feature.
        """
        assert len(inputs) == len(self.in_channels)

        # top-down path
        inner_outs = [inputs[-1]]
        for idx in range(len(self.in_channels)-1, 0, -1):
            feat_heigh = inner_outs[0]
            feat_low = inputs[idx-1]
            feat_heigh = self.reduce_layers[
                len(self.in_channels)-1-idx](feat_heigh)
            inner_outs[0] = feat_heigh

            upsample_feat = self.upsample(feat_heigh)

            inner_out = self.top_down_blocks[
                len(self.in_channels)-1-idx](
                torch.cat([upsample_feat, feat_low], 1))
            inner_outs.insert(0, inner_out)

        # bottom-up path
        outs = [inner_outs[0]]
        for idx in range(len(self.in_channels) - 1):
            feat_low = outs[-1]
            feat_height = inner_outs[idx + 1]
            downsample_feat = self.downsamples[idx](feat_low)
            out = self.bottom_up_blocks[idx](
                torch.cat([downsample_feat, feat_height], 1))
            outs.append(out)

        # out convs
        for idx, stem in enumerate(self.stems):
            outs[idx] = stem(outs[idx])

        return tuple(outs)
