_base_ = [
    './cascade_rcnn_r50_fpn_8x4_sample1e-3_mstrain_v3det_2x.py',
]
# model settings
model = dict(
    backbone=dict(
        _delete_=True,
        type='SwinTransformer',
        embed_dims=128,
        depths=[2, 2, 18, 2],
        num_heads=[4, 8, 16, 32],
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
        init_cfg=dict(type='Pretrained', checkpoint='./swin_base_patch4_window7_224.pth')),
    neck=dict(in_channels=[128, 256, 512, 1024]))