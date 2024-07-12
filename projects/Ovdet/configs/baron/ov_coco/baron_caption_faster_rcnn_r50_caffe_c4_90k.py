_base_ = [
    'mmdet::_base_/models/faster-rcnn_r50-caffe-c4.py',
    '../../_base_/datasets/coco_ovd_caption.py',
    '../../_base_/schedules/schedule_90k.py',
    '../../_base_/iter_based_runtime.py'
]

custom_imports = dict(
    imports=['projects.Ovdet.ovdet'], allow_failed_imports=False)

class_weight = [
    1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1,
    0, 1, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 1, 1,
    1, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 1, 1,
    1, 0, 0, 0, 1
] + [0]

reg_layer = [
    dict(type='Linear', in_features=2048, out_features=2048),
    dict(type='ReLU', inplace=True),
    dict(type='Linear', in_features=2048, out_features=4)
]

clip_cfg = dict(  # ViT-B/32
    type='CLIP',
    image_encoder=None,
    text_encoder=dict(
        type='CLIPTextEncoder',
        embed_dim=512,
        context_length=77,
        vocab_size=49408,
        transformer_width=512,  # also the word embedding dim
        transformer_heads=8,
        transformer_layers=12,
        init_cfg=dict(
            type='Pretrained', checkpoint='checkpoints/clip_vitb32.pth')))

ovd_cfg = dict(
    type='BaronCaption',
    loss_weight=10.0,
    norm_temp=30.0,
    max_caps=5,
    num_words=4,
    word_dim=512,
    words_drop_ratio=0.5,
    use_pe=True,
    queue_cfg=dict(
        names=['clip_cap_text_features', 'clip_caption_features'],
        lengths=[1024] * 2,
        emb_dim=512,
        id_length=1),
    sampling_cfg=dict(
        shape_ratio_thr=0.25,
        area_ratio_thr=0.01,
        objectness_thr=0.85,
        nms_thr=0.2,
        max_num=10,
        topk=128,
        max_perms=4))

model = dict(
    type='OVDTwoStageDetector',
    data_preprocessor=dict(
        type='MultiBranchDataPreprocessor',
        _delete_=True,
        data_preprocessor=dict(
            type='DetDataPreprocessor',
            mean=[103.530, 116.280, 123.675],
            std=[1.0, 1.0, 1.0],
            bgr_to_rgb=False,
            pad_size_divisor=32),
    ),
    rpn_head=dict(
        type='CustomRPNHead',
        anchor_generator=dict(
            scale_major=False,  # align with detectron2
        )),
    # backbone=dict(
    #     init_cfg=dict(
    #         checkpoint='checkpoints/resnet50_msra-5891d200.pth')),
    batch2ovd=dict(caption_batch='baron_caption'),
    roi_head=dict(
        type='OVDStandardRoIHead',
        # shared_head=dict(
        #     init_cfg=dict(
        #         checkpoint='checkpoints/resnet50_msra-5891d200.pth')),
        clip_cfg=clip_cfg,
        ovd_cfg=dict(baron_caption=ovd_cfg),
        bbox_head=dict(
            type='BaronBBoxHead',
            reg_predictor_cfg=reg_layer,
            reg_class_agnostic=True,
            cls_bias=-20.0,
            cls_temp=25.0,
            cls_embeddings_path='projects/Ovdet/metadata/' +
            'coco_clip_hand_craft_attn12.npy',
            use_attn12_output=True,
            loss_cls=dict(
                type='CustomCrossEntropyLoss',
                use_sigmoid=True,
                class_weight=class_weight),
        ),
    ),
)

# optimizer
optim_wrapper = dict(
    type='AmpOptimWrapper',  # amp training
    clip_grad=dict(max_norm=35, norm_type=2),
)
