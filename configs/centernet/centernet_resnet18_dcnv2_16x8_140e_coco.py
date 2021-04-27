_base_ = [
    '../_base_/datasets/coco_detection.py', '../_base_/default_runtime.py'
]
optimizer = dict(type='Adam', lr=5e-4)
optimizer_config = dict(grad_clip=None)
lr_config = dict(
    policy='step',
    warmup='linear',
    warmup_iters=100,
    warmup_ratio=1.,
    step=[90, 120])
total_epochs = 140

model = dict(
    type='CenterNet',
    pretrained='torchvision://resnet18',
    backbone=dict(type='ResNet', depth=18, norm_cfg=dict(type='BN')),
    neck=dict(
        type='CT_ResNeck',
        in_channels=512,
        num_filters=[256, 128, 64],
        num_kernels=[4, 4, 4]),
    bbox_head=dict(
        type='CenterHead',
        num_classes=80,
        feat_channels=64,
        in_channels=64,
        loss_center=dict(type='GaussianFocalLoss', loss_weight=1.0),
        loss_wh=dict(type='L1Loss', loss_weight=0.1),
        loss_offset=dict(type='L1Loss', loss_weight=1.0)))

img_norm_cfg = dict(
    mean=[104.01362025, 114.03422265, 119.9165958],
    std=[73.6027665, 69.89082075, 70.9150767],
    to_rgb=False)

train_pipeline = [
    dict(type='LoadImageFromFile', to_float32=True, color_type='color'),
    dict(type='LoadAnnotations', with_bbox=True),
    dict(
        type='PhotoMetricDistortion',
        brightness_delta=32,
        contrast_range=(0.5, 1.5),
        saturation_range=(0.5, 1.5),
        hue_delta=18),
    dict(
        type='RandomCenterCropPad',
        crop_size=(512, 512),
        ratios=(0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3),
        mean=[0, 0, 0],
        std=[1, 1, 1],
        to_rgb=False,
        test_mode=False,
        test_pad_mode=None),
    dict(type='Resize', img_scale=(512, 512), keep_ratio=True),
    dict(type='RandomFlip', flip_ratio=0.5),
    dict(type='Normalize', **img_norm_cfg),
    dict(type='DefaultFormatBundle'),
    dict(type='Collect', keys=['img', 'gt_bboxes', 'gt_labels'])
]
test_pipeline = [
    dict(type='LoadImageFromFile', to_float32=True),
    dict(
        type='MultiScaleFlipAug',
        scale_factor=1.0,
        flip=False,
        transforms=[
            dict(type='Resize', keep_ratio=True),
            dict(
                type='RandomCenterCropPad',
                crop_size=None,
                ratios=None,
                border=None,
                test_mode=True,
                mean=[0, 0, 0],
                std=[1, 1, 1],
                to_rgb=False,
                test_pad_mode=['logical_or', 31],
                test_pad_add_pix=1),
            dict(type='RandomFlip'),
            dict(type='Normalize', **img_norm_cfg),
            dict(type='ImageToTensor', keys=['img']),
            dict(
                type='Collect',
                meta_keys=('filename', 'ori_shape', 'img_shape', 'pad_shape',
                           'scale_factor', 'flip', 'img_norm_cfg', 'border'),
                keys=['img'])
        ])
]
data = dict(
    samples_per_gpu=32,
    workers_per_gpu=8,
    train=dict(pipeline=train_pipeline),
    val=dict(pipeline=test_pipeline),
    test=dict(pipeline=test_pipeline))
train_cfg = None
test_cfg = dict(
    topK=100,
    nms_cfg=dict(type='soft_nms', iou_threshold=0.5),
    max_per_img=100)
