_base_ = './faster_rcnn_r50_lka_fpn_1x_TinyPerson640_newData.py'
optimizer = dict(type='SGD', lr=0.04, momentum=0.9, weight_decay=0.0001)  # 8GPU
model = dict(
    neck=dict(
        type='lka_FPN',
        in_channels=[256, 512, 1024, 2048],
        out_channels=256,
        num_outs=5,
        with_aem=False,
        with_ffm=False,
        att_kernel_size=7,
        att_kernel_dilation=2)
)