_base_ = './mask_rcnn_regnetx-3GF_fpn_1x_coco.py'
model = dict(
    pretrained='open-mmlab://regnetx_4.0gf',
    backbone=dict(
        _delete_=True,
        type='RegNet',
        arch_parameter='regnetx_4.0gf',
        out_indices=(0, 1, 2, 3),
        frozen_stages=1,
        norm_cfg=dict(type='BN', requires_grad=True),
        norm_eval=True,
        style='pytorch'),
    neck=dict(
        type='FPN',
        in_channels=[80, 240, 560, 1360],
        out_channels=256,
        num_outs=5))
