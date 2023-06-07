_base_ = 'mmdet::_base_/default_runtime.py'

custom_imports = dict(
    imports=['projects.XDecoder.xdecoder'], allow_failed_imports=False)

model = dict(
    type='XDecoder',
    data_preprocessor=dict(
        type='DetDataPreprocessor',
        mean=[123.675, 116.28, 103.53],
        std=[58.395, 57.12, 57.375],
        bgr_to_rgb=True,
        pad_size_divisor=32),
    backbone=dict(type='FocalNet'),
    head=dict(
        type='XDecoderUnifiedhead',
        in_channels=(96, 192, 384, 768),
        task='semseg',
        pixel_decoder=dict(type='XTransformerEncoderPixelDecoder'),
        transformer_decoder=dict(type='XDecoderTransformerDecoder'),
    ),
    test_cfg=dict(mask_thr=0.5, use_thr_for_mc=True)  # mc means multi-class
)

val_cfg = dict(type='ValLoop')
test_cfg = dict(type='TestLoop')
