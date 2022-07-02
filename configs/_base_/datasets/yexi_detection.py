# dataset settings
dataset_type = 'CocoDataset'
data_root = 'd:/mmdetection/data/yexi/'
classes = (
    'RaggedBeggar', 'DwarfClown', 'LongLeggedClown', 'DartsClown', 'Truffe', 'LightDwarf',
    'BallClown', 'NakedElderly', 'ChangeClown', 'HostWhite', 'HostBlack', 'StormRider',
    'Gold', 'Door', 'Close',
)
img_norm_cfg = dict(
    mean=[123.675, 116.28, 103.53], std=[58.395, 57.12, 57.375], to_rgb=True)
train_pipeline = [
    dict(type='LoadImageFromFile'),
    dict(type='LoadAnnotations', with_bbox=True),
    dict(type='Resize', img_scale=(640, 640), keep_ratio=True),
    dict(type='RandomFlip', flip_ratio=0.5),
    dict(type='Normalize', **img_norm_cfg),
    dict(type='Pad', size_divisor=32),
    dict(type='DefaultFormatBundle'),
    dict(type='Collect', keys=['img', 'gt_bboxes', 'gt_labels']),
]
test_pipeline = [
    dict(type='LoadImageFromFile'),
    dict(
        type='MultiScaleFlipAug',
        img_scale=(640, 640),
        flip=False,
        transforms=[
            dict(type='Resize', keep_ratio=True),
            dict(type='RandomFlip'),
            dict(type='Normalize', **img_norm_cfg),
            dict(type='Pad', size_divisor=32),
            dict(type='ImageToTensor', keys=['img']),
            dict(type='Collect', keys=['img']),
        ])
]
data = dict(
    samples_per_gpu=2,
    workers_per_gpu=2,
    train=dict(
        type=dataset_type,
        ann_file=data_root + 'yexi_train.json',
        img_prefix=data_root + 'images/',
        classes=classes,
        pipeline=train_pipeline),
    val=dict(
        type=dataset_type,
        ann_file=data_root + 'yexi_val.json',
        img_prefix=data_root + 'images/',
        classes=classes,
        pipeline=test_pipeline),
    test=dict(
        type=dataset_type,
        ann_file=data_root + 'yexi_test.json',
        img_prefix=data_root + 'images/',
        classes=classes,
        pipeline=test_pipeline))
evaluation = dict(interval=1, metric='bbox')
