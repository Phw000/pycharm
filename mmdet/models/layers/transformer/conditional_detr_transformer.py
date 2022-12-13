# Copyright (c) OpenMMLab. All rights reserved.
import torch
from mmcv.cnn import build_norm_layer
from mmcv.cnn.bricks.transformer import FFN
from torch import Tensor
from torch.nn import ModuleList

from .detr_transformer import (DetrTransformerDecoder,
                               DetrTransformerDecoderLayer)
from .utils import MLP, ConditionalAttention, convert_coordinate_to_encoding


class ConditionalDetrTransformerDecoder(DetrTransformerDecoder):
    """Decoder of Conditional DETR."""

    def _init_layers(self) -> None:
        """Initialize decoder layers and other layers."""
        self.layers = ModuleList([
            ConditionalDetrTransformerDecoderLayer(**self.layer_cfg)
            for _ in range(self.num_layers)
        ])
        self.embed_dims = self.layers[0].embed_dims
        self.post_norm = build_norm_layer(self.post_norm_cfg,
                                          self.embed_dims)[1]
        # conditional detr affline
        self.query_scale = MLP(self.embed_dims, self.embed_dims,
                               self.embed_dims, 2)
        self.ref_point_head = MLP(self.embed_dims, self.embed_dims, 2, 2)
        # we have substitute 'qpos_proj' with 'qpos_sine_proj' except for
        # the first decoder layer), so 'qpos_proj' should be deleted
        # in other layers.
        for layer_id in range(self.num_layers - 1):
            self.layers[layer_id + 1].cross_attn.qpos_proj = None

    def forward(self, query: Tensor, key: Tensor, value: Tensor,
                query_pos: Tensor, key_pos: Tensor, key_padding_mask: Tensor):
        """Forward function of decoder.

        Args:
            query (Tensor): The input query with shape
                (bs, num_queries, dim).
            key (Tensor): The input key with shape (bs, num_keys, dim) If
                `None`, the `query` will be used. Defaults to `None`.
            value (Tensor): The input value with the same shape as
                `key`. If `None`, the `key` will be used. Defaults to `None`.
            query_pos (Tensor): The positional encoding for `query`, with the
                same shape as `query`. If not `None`, it will be added to
                `query` before forward function. Defaults to `None`.
            reg_branches (nn.Module): The regression branch for dynamically
                updating references in each layer.
            key_pos (Tensor): The positional encoding for `key`, with the
                same shape as `key`.
            key_padding_mask (Tensor): ByteTensor with shape (bs, num_keys).
        Returns:
            List[Tensor]: forwarded results with shape (num_decoder_layers,
            bs, num_queries, dim) if `return_intermediate` is True, otherwise
            with shape (1, bs, num_queries, dim). references with shape
            (num_decoder_layers, bs, num_queries, 2).
        """
        reference_unsigmoid = self.ref_point_head(
            query_pos)  # [num_queries, batch_size, 2]
        reference = reference_unsigmoid.sigmoid().transpose(0, 1)
        reference_xy = reference[..., :2].transpose(0, 1)
        intermediate = []
        for layer_id, layer in enumerate(self.layers):
            if layer_id == 0:
                pos_transformation = 1
            else:
                pos_transformation = self.query_scale(query)
            # get sine embedding for the query vector
            ref_sine_embed = convert_coordinate_to_encoding(reference_xy)
            # apply transformation
            ref_sine_embed = ref_sine_embed * pos_transformation
            query = layer(
                query,
                key=key,
                value=value,
                query_pos=query_pos,
                key_pos=key_pos,
                key_padding_mask=key_padding_mask,
                ref_sine_embed=ref_sine_embed,
                is_first=(layer_id == 0))
            if self.return_intermediate:
                intermediate.append(self.post_norm(query))

        if self.return_intermediate:
            return torch.stack(intermediate), reference

        if self.post_norm is not None:
            query = self.post_norm(query)

        return query.unsqueeze(0), reference


class ConditionalDetrTransformerDecoderLayer(DetrTransformerDecoderLayer):
    """Implements decoder layer in Conditional DETR transformer."""

    def _init_layers(self):
        """Initialize self-attention,  cross-attention, FFN, and
        normalization."""
        self.self_attn = ConditionalAttention(**self.self_attn_cfg)
        self.cross_attn = ConditionalAttention(**self.cross_attn_cfg)
        self.embed_dims = self.self_attn.embed_dims
        self.ffn = FFN(**self.ffn_cfg)
        norms_list = [
            build_norm_layer(self.norm_cfg, self.embed_dims)[1]
            for _ in range(3)
        ]
        self.norms = ModuleList(norms_list)

    def forward(self,
                query: Tensor,
                key: Tensor = None,
                value: Tensor = None,
                query_pos: Tensor = None,
                key_pos: Tensor = None,
                self_attn_masks: Tensor = None,
                cross_attn_masks: Tensor = None,
                key_padding_mask: Tensor = None,
                ref_sine_embed: Tensor = None,
                is_first=None):
        """
        Args:
            query (Tensor): The input query, has shape (bs, num_queries, dim)
            key (Tensor, optional): The input key, has shape (bs, num_keys,
                dim). If `None`, the `query` will be used. Defaults to `None`.
            value (Tensor, optional): The input value, has the same shape as
                `key`, as in `nn.MultiheadAttention.forward`. If `None`, the
                `key` will be used. Defaults to `None`.
            query_pos (Tensor, optional): The positional encoding for `query`,
                has the same shape as `query`. If not `None`, it will be
                added to `query` before forward function. Defaults to `None`.
            key_pos (Tensor, optional): The positional encoding for `key`, has
                the same shape as `key`.
            self_attn_masks (Tensor, optional): ByteTensor mask, has shape
                (num_queries, num_keys), Same in `nn.MultiheadAttention.
                forward`. Defaults to None.
            cross_attn_masks (Tensor, optional): ByteTensor mask, has shape
                (num_queries, num_keys), Same in `nn.MultiheadAttention.
                forward`. Defaults to None.
            key_padding_mask (Tensor, optional): The `key_padding_mask` of
                `cross_attn` input. ByteTensor, has shape (bs, num_keys).
            is_first (bool): A indicator to tell whether the current layer
                is the first layer of the decoder.
                Defaults to False.

        Returns:
            Tensor: forwarded results, has shape (bs, num_queries, dim).
        """
        query = self.self_attn(
            query=query,
            key=query,
            query_pos=query_pos,
            key_pos=query_pos,
            attn_mask=self_attn_masks)
        query = self.norms[0](query)
        query = self.cross_attn(
            query=query,
            key=key,
            query_pos=query_pos,
            key_pos=key_pos,
            attn_mask=cross_attn_masks,
            key_padding_mask=key_padding_mask,
            ref_sine_embed=ref_sine_embed,
            is_first=is_first)
        query = self.norms[1](query)
        query = self.ffn(query)
        query = self.norms[2](query)

        return query
