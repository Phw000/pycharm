_base_ = [
    '../_base_/models/retinanet_r50_fpn.py',
    '../_base_/datasets/openimages_detection.py',
    '../_base_/schedules/schedule_1x.py', '../_base_/default_runtime.py'
]

model = dict(bbox_head=dict(num_classes=601))

optimizer = dict(type='SGD', lr=0.08, momentum=0.9, weight_decay=0.0001)
optimizer_config = dict(
    _delete_=True, grad_clip=dict(max_norm=35, norm_type=2))
lr_config = dict(
    policy='step',
    warmup='linear',
    warmup_iters=26000,
    warmup_ratio=1.0 / 64,
    step=[8, 11])

# NOTE: This is for automatically scaling LR, USER SHOULD NOT CHANGE THIS VALUE.
default_batch_size = 64  # (32 GPUs) x (2 samples per GPU)
