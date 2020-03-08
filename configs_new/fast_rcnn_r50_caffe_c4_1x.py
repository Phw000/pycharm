_base_ = [
    'component/fast_rcnn_r50_caffe_c4.py',
    'component/coco_proposal_detection_caffe.py', 'component/schedule_1x.py',
    'component/default_runtime.py'
]
# optimizer
optimizer = dict(type='SGD', lr=0.01, momentum=0.9, weight_decay=0.0001)
work_dir = './work_dirs/fast_rcnn_r50_caffe_c4_1x'
