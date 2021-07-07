import copy

from mmdet.core import bbox2result
from ..builder import DETECTORS, build_backbone, build_head, build_neck
from .base import BaseDetector


@DETECTORS.register_module()
class SingleStageInstanceSegmentor(BaseDetector):
    """Base class for single-stage instance segmentors."""

    def __init__(self,
                 backbone,
                 neck=None,
                 bbox_head=None,
                 mask_head=None,
                 train_cfg=None,
                 test_cfg=None,
                 init_cfg=None):
        super(SingleStageInstanceSegmentor, self).__init__(init_cfg)
        self.backbone = build_backbone(backbone)
        if neck is not None:
            self.neck = build_neck(neck)
        else:
            self.neck = None

        if bbox_head is not None:
            bbox_head.update(train_cfg=copy.deepcopy(train_cfg))
            bbox_head.update(test_cfg=copy.deepcopy(test_cfg))
            self.bbox_head = build_head(bbox_head)
        else:
            self.bbox_head = None

        assert mask_head, f'`mask_head` must ' \
                          f'be implemented in {self.__class__.__name__}'
        mask_head.update(train_cfg=copy.deepcopy(train_cfg))
        mask_head.update(test_cfg=copy.deepcopy(test_cfg))
        self.mask_head = build_head(mask_head)

        self.train_cfg = train_cfg
        self.test_cfg = test_cfg

    def extract_feat(self, img):
        """Directly extract features from the backbone+neck."""
        x = self.backbone(img)
        if self.with_neck:
            x = self.neck(x)
        return x

    def forward_dummy(self, img):
        """Used for computing network flops.

        See `mmdetection/tools/get_flops.py`
        """
        raise NotImplementedError(
            f'`forward_dummy` is not implemented in {self.__class__.__name__}')

    def forward_train(self,
                      img,
                      img_metas,
                      gt_bboxes,
                      gt_labels,
                      gt_bboxes_ignore=None,
                      gt_masks=None,
                      **kwargs):
        """
        Args:
            img (Tensor): Input images of shape (N, C, H, W).
                Typically these should be mean centered and std scaled.
            img_metas (list[dict]): A List of image info dict where each dict
                has: 'img_shape', 'scale_factor', 'flip', and may also contain
                'filename', 'ori_shape', 'pad_shape', and 'img_norm_cfg'.
                For details on the values of these keys see
                :class:`mmdet.datasets.pipelines.Collect`.
            gt_bboxes (list[Tensor]): Each item are the truth boxes for each
                image in [tl_x, tl_y, br_x, br_y] format.
            gt_labels (list[Tensor]): Class indices corresponding to each box
            gt_bboxes_ignore (None | list[Tensor]): Specify which bounding
                boxes can be ignored when computing the loss.
            gt_masks (None | Tensor) : true segmentation masks for each box
                used if the architecture supports a segmentation task.

        Returns:
            dict[str, Tensor]: A dictionary of loss components.
        """
        x = self.extract_feat(img)
        losses = dict()

        # CondInst, yolact
        if self.bbox_head:
            # bbox_head_results is a tuple
            bbox_head_preds = self.bbox_head(x)
            # positive_infos is a obj:`InstanceResults`
            # It contains the information about the positive samples
            # CondInst, Yolact
            det_losses, positive_infos = self.bbox_head.loss(
                *bbox_head_preds,
                gt_bboxes=gt_bboxes,
                gt_labels=gt_labels,
                img_metas=img_metas,
                gt_bboxes_ignore=gt_bboxes_ignore)
            losses.update(det_losses)
        else:
            positive_infos = None

        mask_head_inputs = (x, gt_labels, gt_masks, img_metas)

        # when no positive_infos add gt bbox
        mask_loss = self.mask_head.forward_train(
            *mask_head_inputs,
            positive_infos=positive_infos,
            gt_bboxes=gt_bboxes,
            gt_bboxes_ignore=gt_bboxes_ignore)
        # avoid loss override
        assert not set(mask_loss.keys()) & set(losses.keys())

        losses.update(mask_loss)
        return losses

    def simple_test(self, img, img_metas, rescale=False):
        """Test function without test-time augmentation."""
        feat = self.extract_feat(img)
        if self.bbox_head:
            # det_results is a obj:`InstanceResults`
            outs = self.bbox_head(feat)
            det_results = self.bbox_head.get_bboxes(
                *outs, img_metas=img_metas, cfg=self.test_cfg, rescale=rescale)
            bbox_results = [
                bbox2result(det_bbox, det_label, self.bbox_head.num_classes)
                for det_bbox, det_label in zip(det_results.det_bboxes,
                                               det_results.det_labels)
            ]
        else:
            det_results = None
            bbox_results = [None for _ in range(len(img_metas))]

        segm_results = self.mask_head.simple_test(
            feat, img_metas, rescale=rescale, det_results=det_results)

        return list(zip(bbox_results, segm_results))

    def aug_test(self, imgs, img_metas, rescale=False):
        raise NotImplementedError
