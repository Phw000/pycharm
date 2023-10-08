# Copyright (c) OpenMMLab. All rights reserved.
from mmengine.config import read_base

with read_base():
    from .mask2former_r50_8xb2_lsj_50e_coco import *

from mmdet.models.backbones.swin import SwinTransformer
from mmdet.models.dense_heads.mask2former_head import Mask2FormerHead
from mmdet.models.detectors.mask2former import Mask2Former

pretrained = 'https://github.com/SwinTransformer/storage/releases/download/v1.0.0/swin_tiny_patch4_window7_224.pth'  # noqa
depths = [2, 2, 6, 2]
model.update(
    dict(
        type=Mask2Former,
        backbone=dict(
            _delete_=True,
            type=SwinTransformer,
            embed_dims=96,
            depths=depths,
            num_heads=[3, 6, 12, 24],
            window_size=7,
            mlp_ratio=4,
            qkv_bias=True,
            qk_scale=None,
            drop_rate=0.,
            attn_drop_rate=0.,
            drop_path_rate=0.3,
            patch_norm=True,
            out_indices=(0, 1, 2, 3),
            with_cp=False,
            convert_weights=True,
            frozen_stages=-1,
            init_cfg=dict(type='Pretrained', checkpoint=pretrained)),
        panoptic_head=dict(
            type=Mask2FormerHead, in_channels=[96, 192, 384, 768]),
        init_cfg=None))

# set all layers in backbone to lr_mult=0.1
# set all norm layers, position_embeding,
# query_embeding, level_embeding to decay_multi=0.0
backbone_norm_multi = dict(lr_mult=0.1, decay_mult=0.0)
backbone_embed_multi = dict(lr_mult=0.1, decay_mult=0.0)
embed_multi.update(dict(lr_mult=1.0, decay_mult=0.0))
custom_keys = {
    'backbone': dict(lr_mult=0.1, decay_mult=1.0),
    'backbone.patch_embed.norm': backbone_norm_multi,
    'backbone.norm': backbone_norm_multi,
    'absolute_pos_embed': backbone_embed_multi,
    'relative_position_bias_table': backbone_embed_multi,
    'query_embed': embed_multi,
    'query_feat': embed_multi,
    'level_embed': embed_multi
}
custom_keys.update({
    f'backbone.stages.{stage_id}.blocks.{block_id}.norm': backbone_norm_multi
    for stage_id, num_blocks in enumerate(depths)
    for block_id in range(num_blocks)
})
custom_keys.update({
    f'backbone.stages.{stage_id}.downsample.norm': backbone_norm_multi
    for stage_id in range(len(depths) - 1)
})
# optimizer
optim_wrapper.update(
    dict(paramwise_cfg=dict(custom_keys=custom_keys, norm_decay_mult=0.0)))