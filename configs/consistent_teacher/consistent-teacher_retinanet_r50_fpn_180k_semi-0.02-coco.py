_base_ = ['./consistent-teacher_retinanet_r50_fpn_180k_semi-0.1-coco.py']

# 2% coco train2017 is set as labeled dataset
labeled_dataset = _base_.labeled_dataset
unlabeled_dataset = _base_.unlabeled_dataset
labeled_dataset.ann_file = 'semi_anns/instances_train2017.1@2.json'
unlabeled_dataset.ann_file = 'semi_anns/' \
                             'instances_train2017.1@2-unlabeled.json'
train_dataloader = dict(
    dataset=dict(datasets=[labeled_dataset, unlabeled_dataset]))
