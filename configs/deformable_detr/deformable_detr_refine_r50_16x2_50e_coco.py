_base_ = 'deformable_detr_r50_16x2_50e_coco.py'
model = dict(bbox_head=dict(with_box_refine=True))

# NOTE: This variable is for automatically scaling LR,
# USER SHOULD NOT CHANGE THIS VALUE.
default_batch_size = 32  # (16 GPUs) x (2 samples per GPU)
