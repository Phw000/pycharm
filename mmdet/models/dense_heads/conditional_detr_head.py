# Copyright (c) OpenMMLab. All rights reserved.
from typing import Tuple

import torch
import torch.nn as nn
from mmengine.model import bias_init_with_prob
from torch import Tensor

from mmdet.models.layers.transformer import inverse_sigmoid
from mmdet.registry import MODELS
from mmdet.structures import SampleList
from mmdet.utils import InstanceList
from .detr_head import DETRHead


@MODELS.register_module()
class ConditionalDETRHead(DETRHead):
    """Implements the DETR transformer head.

    See `paper: End-to-End Object Detection with Transformers
    <https://arxiv.org/pdf/2005.12872>`_ for details.

    Args:
        TODO
    """

    def init_weights(self):
        """Initialize weights of the transformer head."""
        super().init_weights()
        # The initialization for transformer is important
        if self.loss_cls.use_sigmoid:
            bias_init = bias_init_with_prob(0.01)
            nn.init.constant_(self.fc_cls.bias, bias_init)

    def forward(self, hidden_states: Tensor,
                reference: Tensor) -> Tuple[Tensor, Tensor]:
        """"Forward function.

        Args:
            hidden_states (Tensor): Features from transformer decoder. If
                `return_intermediate_dec` in detr.py is True output has shape
                (num_hidden_states, bs, num_query, dim), else has shape (1,
                bs, num_query, dim) which only contains the last layer outputs.
            reference_points (Tensor) has shape(1,300,2)
        Returns:
            tuple[Tensor]: results of head containing the following tensor.

            - layers_cls_scores (Tensor): Outputs from the classification head,
              shape (num_hidden_states, bs, num_query, cls_out_channels). Note
              cls_out_channels should include background.
            - layers_bbox_preds (Tensor): Sigmoid outputs from the regression
              head with normalized coordinate format (cx, cy, w, h), has shape
              (num_hidden_states, bs, num_query, 4).
        """

        reference_unsigmoid = inverse_sigmoid(reference)
        layers_outputs_coords = []
        for layer_id in range(hidden_states.shape[0]):
            tmp_reg_preds = self.fc_reg(
                self.activate(self.reg_ffn(hidden_states[layer_id])))
            tmp_reg_preds[..., :2] += reference_unsigmoid
            outputs_coord = tmp_reg_preds.sigmoid()
            layers_outputs_coords.append(outputs_coord)
        layers_outputs_coords = torch.stack(layers_outputs_coords)

        layers_cls_scores = self.fc_cls(hidden_states)
        return layers_cls_scores, layers_outputs_coords

    def loss(self, hidden_states: Tensor, reference_points: Tensor,
             batch_data_samples: SampleList) -> dict:
        """Perform forward propagation and loss calculation of the detection
        head on the features of the upstream network.

        Args:
            hidden_states (Tensor): Feature from the transformer decoder, has
                shape (num_decoder_layers, bs, num_query, cls_out_channels) or
                (num_decoder_layers, num_query, bs, cls_out_channels).
            batch_data_samples (List[:obj:`DetDataSample`]): The Data
                Samples. It usually includes information such as
                `gt_instance`, `gt_panoptic_seg` and `gt_sem_seg`.

        Returns:
            dict: A dictionary of loss components.
        """
        batch_gt_instances = []
        batch_img_metas = []
        for data_sample in batch_data_samples:
            batch_img_metas.append(data_sample.metainfo)
            batch_gt_instances.append(data_sample.gt_instances)

        outs = self(hidden_states, reference_points)
        loss_inputs = outs + (batch_gt_instances, batch_img_metas)
        losses = self.loss_by_feat(*loss_inputs)
        return losses

    def loss_and_predict(
            self, hidden_states: Tuple[Tensor], reference_points: Tensor,
            batch_data_samples: SampleList) -> Tuple[dict, InstanceList]:
        """Perform forward propagation of the head, then calculate loss and
        predictions from the features and data samples. Over-write because
        img_metas are needed as inputs for bbox_head.

        Args:
            hidden_states (tuple[Tensor]): Features from FPN.
            batch_data_samples (list[:obj:`DetDataSample`]): Each item contains
                the meta information of each image and corresponding
                annotations.

        Returns:
            tuple: the return value is a tuple contains:

                - losses: (dict[str, Tensor]): A dictionary of loss components.
                - predictions (list[:obj:`InstanceData`]): Detection
                  results of each image after the post process.
        """
        batch_gt_instances = []
        batch_img_metas = []
        for data_sample in batch_data_samples:
            batch_img_metas.append(data_sample.metainfo)
            batch_gt_instances.append(data_sample.gt_instances)

        outs = self(hidden_states, reference_points)
        loss_inputs = outs + (batch_gt_instances, batch_img_metas)
        losses = self.loss_by_feat(*loss_inputs)

        predictions = self.predict_by_feat(
            *outs, batch_img_metas=batch_img_metas)
        return losses, predictions

    def predict(self,
                hidden_states: Tuple[Tensor],
                reference_points: Tensor,
                batch_data_samples: SampleList,
                rescale: bool = True) -> InstanceList:
        """Perform forward propagation of the detection head and predict
        detection results on the features of the upstream network. Over-write
        because img_metas are needed as inputs for bbox_head.

        Args:
            hidden_states (tuple[Tensor]): Multi-level features from the
                upstream network, each is a 4D-tensor.
            batch_data_samples (List[:obj:`DetDataSample`]): The Data
                Samples. It usually includes information such as
                `gt_instance`, `gt_panoptic_seg` and `gt_sem_seg`.
            rescale (bool, optional): Whether to rescale the results.
                Defaults to True.

        Returns:
            list[obj:`InstanceData`]: Detection results of each image
            after the post process.
        """
        batch_img_metas = [
            data_samples.metainfo for data_samples in batch_data_samples
        ]

        last_layer_hidden_state = hidden_states[-1].unsqueeze(0)
        outs = self(last_layer_hidden_state, reference_points)

        predictions = self.predict_by_feat(
            *outs, batch_img_metas=batch_img_metas, rescale=rescale)

        return predictions
