_base_ = 'deformable_detr_refine_r50_16x2_50e_coco.py'
model = dict(bbox_head=dict(as_two_stage=True))

# NOTE: This is for automatically scaling LR, USER SHOULD NOT CHANGE THIS VALUE.
default_batch_size = 32  # (16 GPUs) x (2 samples per GPU)
