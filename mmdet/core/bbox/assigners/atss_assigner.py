import torch

from ..geometry import bbox_overlaps
from .assign_result import AssignResult
from .base_assigner import BaseAssigner


class ATSSAssigner(BaseAssigner):
    """Assign a corresponding gt bbox or background to each bbox.

    Each proposals will be assigned with `0` or a positive integer
    indicating the ground truth index.

    - 0: negative sample, no assigned gt
    - positive integer: positive sample, index (1-based) of assigned gt

    Args:
        topk (float): number of bbox selected in each level
    """

    def __init__(self, topk):
        self.topk = topk


    #modifications with https://github.com/sfzhang15/ATSS/blob/master/atss_core/modeling/rpn/atss/loss.py
    def assign(self, bboxes, num_level_bboxes, gt_bboxes, gt_bboxes_ignore=None, gt_labels=None):
        """Assign gt to bboxes.

        The assignment is done in following steps

        1. compute iou between all bbox and gt
        2. compute center distance between all bbox and gt
        3. on each pyramid level, for each gt, select k bbox whose center are closest to the gt center, 
           so we total select k*l bbox as candidates for each gt
        4. get corresponding iou for the these candidates, and compute the mean and std, 
           set mean + std as the iou threshold
        5. select these candidates whose iou are greater than or equal to the threshold as postive
        6. limit the positive sample's center in gt


        Args:
            bboxes (Tensor): Bounding boxes to be assigned, shape(n, 4).
            num_level_bboxes (List): num of bboxes in each level
            gt_bboxes (Tensor): Groundtruth boxes, shape (k, 4).
            gt_bboxes_ignore (Tensor, optional): Ground truth bboxes that are
                labelled as `ignored`, e.g., crowd boxes in COCO.
            gt_labels (Tensor, optional): Label of gt_bboxes, shape (k, ).

        Returns:
            :obj:`AssignResult`: The assign result.
        """
        if bboxes.shape[0] == 0 or gt_bboxes.shape[0] == 0:
            raise ValueError('No gt or bboxes')
        
        INF = 100000000
        num_gt = gt_bboxes.size(0)
        bboxes = bboxes[:, :4]
        overlaps = bbox_overlaps(bboxes, gt_bboxes) 

        gt_cx = (gt_bboxes[:, 0] + gt_bboxes[:, 2]) / 2.0
        gt_cy = (gt_bboxes[:, 1] + gt_bboxes[:, 3]) / 2.0
        gt_points = torch.stack((gt_cx, gt_cy), dim=1) 

        bboxes_cx = (bboxes[:, 0] + bboxes[:, 2]) / 2.0
        bboxes_cy = (bboxes[:, 1] + bboxes[:, 3]) / 2.0
        bboxes_points = torch.stack((bboxes_cx, bboxes_cy), dim=1)

        distances = (bboxes_points[:, None, :] - gt_points[None, :, :]).pow(2).sum(-1).sqrt() 
        
        candidate_idxs = []
        start_idx = 0
        for level, bboxes_per_level in enumerate(num_level_bboxes):
            end_idx = start_idx + bboxes_per_level
            distances_per_level = distances[start_idx:end_idx, :] 
            _, topk_idxs_per_level = distances_per_level.topk(self.topk, dim=0, largest=False) 
            candidate_idxs.append(topk_idxs_per_level + start_idx)
            start_idx = end_idx
        candidate_idxs = torch.cat(candidate_idxs, dim=0) 

        candidate_overlaps = overlaps[candidate_idxs, torch.arange(num_gt)] 
        overlaps_mean_per_gt = candidate_overlaps.mean(0)
        overlaps_std_per_gt = candidate_overlaps.std(0)
        overlaps_thr_per_gt = overlaps_mean_per_gt + overlaps_std_per_gt 

        is_pos = candidate_overlaps >= overlaps_thr_per_gt[None, :] 
        
        num_bboxes = bboxes.size(0)
        for gt_idx in range(num_gt):
            candidate_idxs[:, gt_idx] += gt_idx * num_bboxes
        expand_bboxes_cx = bboxes_cx.view(1, -1).expand(num_gt, num_bboxes).contiguous().view(-1) 
        expand_bboxes_cy = bboxes_cy.view(1, -1).expand(num_gt, num_bboxes).contiguous().view(-1)
        candidate_idxs = candidate_idxs.view(-1) 

        l = expand_bboxes_cx[candidate_idxs].view(-1, num_gt) - gt_bboxes[:, 0] 
        t = expand_bboxes_cy[candidate_idxs].view(-1, num_gt) - gt_bboxes[:, 1]
        r = gt_bboxes[:, 2] - expand_bboxes_cx[candidate_idxs].view(-1, num_gt)
        b = gt_bboxes[:, 3] - expand_bboxes_cy[candidate_idxs].view(-1, num_gt)
        is_in_gts = torch.stack([l, t, r, b], dim=1).min(dim=1)[0] > 0.01
        is_pos = is_pos & is_in_gts 

        overlaps_inf = torch.full_like(overlaps, -INF).t().contiguous().view(-1) 
        index = candidate_idxs.view(-1)[is_pos.view(-1)]
        overlaps_inf[index] = overlaps.t().contiguous().view(-1)[index] 
        overlaps_inf = overlaps_inf.view(num_gt, -1).t()

        max_overlaps, argmax_overlaps = overlaps_inf.max(dim=1)
        assigned_gt_inds = overlaps.new_full((num_bboxes, ), 0, dtype=torch.long)
        assigned_gt_inds[max_overlaps != -INF] = argmax_overlaps[max_overlaps != -INF] + 1
        

        if gt_labels is not None:
            assigned_labels = assigned_gt_inds.new_zeros((num_bboxes, ))
            pos_inds = torch.nonzero(assigned_gt_inds > 0).squeeze()
            if pos_inds.numel() > 0:
                assigned_labels[pos_inds] = gt_labels[assigned_gt_inds[pos_inds] - 1]
        else: 
            assigned_labels = None
        return AssignResult(num_gt, assigned_gt_inds, max_overlaps, labels=assigned_labels)

        