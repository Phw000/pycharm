# Copyright (c) OpenMMLab. All rights reserved.
from typing import List

import torch
import torch.nn as nn
from mmcv.cnn import build_norm_layer
from mmcv.cnn.bricks.transformer import FFN
from mmengine.model import ModuleList
from torch import Tensor

from .detr_transformer import (DetrTransformerDecoder,
                               DetrTransformerDecoderLayer,
                               DetrTransformerEncoder,
                               DetrTransformerEncoderLayer)
from .utils import (MLP, ConditionalAttention, convert_coordinate_to_encoding,
                    inverse_sigmoid)


class DabDetrTransformerDecoderLayer(DetrTransformerDecoderLayer):
    """Implements decoder layer in DAB-DETR transformer."""

    def _init_layers(self):
        """Initialize self-attention, cross-attention, FFN, normalization and
        others."""
        self.self_attn = ConditionalAttention(**self.self_attn_cfg)
        self.cross_attn = ConditionalAttention(**self.cross_attn_cfg)
        self.embed_dims = self.self_attn.embed_dims
        self.ffn = FFN(**self.ffn_cfg)
        norms_list = [
            build_norm_layer(self.norm_cfg, self.embed_dims)[1]
            for _ in range(3)
        ]
        self.norms = ModuleList(norms_list)
        self.keep_query_pos = self.cross_attn.keep_query_pos

    def forward(self,
                query,
                key=None,
                query_pos=None,
                ref_sine_embed=None,
                key_pos=None,
                self_attn_masks=None,
                cross_attn_masks=None,
                key_padding_mask=None,
                is_first=False,
                **kwargs) -> Tensor:
        """
        Args:
            query (Tensor): The input query with shape [bs, num_queries,
                embed_dims].
            key (Tensor): The key tensor with shape [bs, num_keys,
                embed_dims].
                If None, the `query` will be used. Defaults to None.
            query_pos (Tensor): The positional encoding for query in self
                attention, with the same shape as `x`. If not None,
                it will be added to `x` before forward function.
                Defaults to None.
            ref_sine_embed (Tensor): The positional encoding for query in
                cross attention, with the same shape as `x`. If not None,
                it will be added to `x` before forward function.
                Defaults to None.
            key_pos (Tensor): The positional encoding for `key`, with the
                same shape as `key`. Defaults to None. If not None, it will
                be added to `key` before forward function. If None, and
                `query_pos` has the same shape as `key`, then `query_pos`
                will be used for `key_pos`. Defaults to None.
            self_attn_masks (Tensor): ByteTensor mask with shape [num_queries,
                num_keys]. Same in `nn.MultiheadAttention.forward`.
                Defaults to None.
            cross_attn_masks (Tensor): ByteTensor mask with shape [num_queries,
                num_keys]. Same in `nn.MultiheadAttention.forward`.
                Defaults to None.
            key_padding_mask (Tensor): ByteTensor with shape [bs, num_keys].
                Defaults to None.
            is_first (bool): A indicator to tell whether the current layer
                is the first layer of the decoder.
                Defaults to False.

        Returns:
            Tensor: forwarded results with shape
            [bs, num_queries, embed_dims].
        """

        query = self.self_attn(
            query=query,
            key=query,
            query_pos=query_pos,
            key_pos=query_pos,
            attn_mask=self_attn_masks,
            **kwargs)
        query = self.norms[0](query)
        query = self.cross_attn(
            query=query,
            key=key,
            query_pos=query_pos,
            ref_sine_embed=ref_sine_embed,
            key_pos=key_pos,
            attn_mask=cross_attn_masks,
            key_padding_mask=key_padding_mask,
            is_first=is_first,
            **kwargs)
        query = self.norms[1](query)
        query = self.ffn(query)
        query = self.norms[2](query)

        return query


class DabDetrTransformerDecoder(DetrTransformerDecoder):
    """Decoder of DAB-DETR.

    Args:
        query_dim (int): The last dimension of query pos,
            4 for anchor format, 2 for point format.
            Defaults to 4.
        query_scale_type (str): Type of transformation applied
            to content query. Defaults to `cond_elewise`.
        with_modulated_hw_attn (bool): Whether to inject h&w info
            during cross conditional attention. Defaults to True.
    """

    def __init__(self,
                 *args,
                 query_dim=4,
                 query_scale_type='cond_elewise',
                 with_modulated_hw_attn=True,
                 **kwargs):

        self.query_dim = query_dim
        self.query_scale_type = query_scale_type
        self.with_modulated_hw_attn = with_modulated_hw_attn

        super().__init__(*args, **kwargs)

    def _init_layers(self):
        """Initialize decoder layers and other layers."""
        assert self.query_dim in [2, 4], \
            f'{"dab-detr only supports anchor prior or reference point prior"}'
        assert self.query_scale_type in [
            'cond_elewise', 'cond_scalar', 'fix_elewise'
        ]

        self.layers = ModuleList([
            DabDetrTransformerDecoderLayer(**self.layer_cfg)
            for _ in range(self.num_layers)
        ])

        embed_dims = self.layers[0].embed_dims
        self.embed_dims = embed_dims

        self.post_norm = build_norm_layer(self.post_norm_cfg, embed_dims)[1]
        if self.query_scale_type == 'cond_elewise':
            self.query_scale = MLP(embed_dims, embed_dims, embed_dims, 2)
        elif self.query_scale_type == 'cond_scalar':
            self.query_scale = MLP(embed_dims, embed_dims, 1, 2)
        elif self.query_scale_type == 'fix_elewise':
            self.query_scale = nn.Embedding(self.num_layers, embed_dims)
        else:
            raise NotImplementedError('Unknown query_scale_type: {}'.format(
                self.query_scale_type))

        self.ref_point_head = MLP(self.query_dim // 2 * embed_dims, embed_dims,
                                  embed_dims, 2)

        if self.with_modulated_hw_attn and self.query_dim == 4:
            self.ref_anchor_head = MLP(embed_dims, embed_dims, 2, 2)

        self.keep_query_pos = self.layers[0].keep_query_pos
        if not self.keep_query_pos:
            for layer_id in range(self.num_layers - 1):
                self.layers[layer_id + 1].cross_attn.qpos_proj = None

    def forward(self,
                query,
                key,
                query_pos,
                reg_branches,
                key_pos=None,
                key_padding_mask=None,
                **kwargs) -> List[Tensor]:
        """Forward function of decoder.

        Args:
            query (Tensor): The input query with shape (bs, num_queries, dim).
            key (Tensor): The input key with shape (bs, num_keys, dim) If
                `None`, the `query` will be used. Defaults to `None`.
            query_pos (Tensor): The positional encoding for `query`, with the
                same shape as `query`. If not `None`, it will be added to
                `query` before forward function. Defaults to `None`.
            reg_branches (nn.Module): The regression branch for dynamically
                updating references in each layer.
            key_pos (Tensor): The positional encoding for `key`, with the
                same shape as `key`. If not `None`, it will be added to
                `key` before forward function. If `None`, and `query_pos`
                has the same shape as `key`, then `query_pos` will be used
                as `key_pos`. Defaults to `None`.
            key_padding_mask (Tensor): ByteTensor with shape (bs, num_keys).
                Defaults to `None`.

        Returns:
            List[Tensor]: forwarded results with shape (num_decoder_layers,
            bs, num_queries, dim) if `return_intermediate` is True, otherwise
            with shape (1, bs, num_queries, dim). references with shape
            (num_decoder_layers, bs, num_queries, 2/4) if `reg_branches`
            is not None, otherwise with shape (1, bs, num_queries, 2/4).
        """
        output = query
        reference_unsigmoid = query_pos

        reference = reference_unsigmoid.sigmoid()
        ref = [reference]

        intermediate = []
        for layer_id, layer in enumerate(self.layers):
            obj_center = reference[..., :self.query_dim]
            ref_sine_embed = convert_coordinate_to_encoding(
                pos_tensor=obj_center, num_feats=self.embed_dims // 2)
            query_pos = self.ref_point_head(
                ref_sine_embed)  # [bs, nq, 2c] -> [bs, nq, c]
            # For the first decoder layer, do not apply transformation
            if self.query_scale_type != 'fix_elewise':
                if layer_id == 0:
                    pos_transformation = 1
                else:
                    pos_transformation = self.query_scale(output)
            else:
                pos_transformation = self.query_scale.weight[layer_id]
            # apply transformation
            ref_sine_embed = ref_sine_embed[
                ..., :self.embed_dims] * pos_transformation
            # modulated height and weight attention
            if self.with_modulated_hw_attn:
                assert obj_center.size(-1) == 4
                ref_hw = self.ref_anchor_head(output).sigmoid()
                ref_sine_embed[..., self.embed_dims // 2:] *= \
                    (ref_hw[..., 0] / obj_center[..., 2]).unsqueeze(-1)
                ref_sine_embed[..., : self.embed_dims // 2] *= \
                    (ref_hw[..., 1] / obj_center[..., 3]).unsqueeze(-1)

            output = layer(
                output,
                key,
                query_pos=query_pos,
                ref_sine_embed=ref_sine_embed,
                key_pos=key_pos,
                key_padding_mask=key_padding_mask,
                is_first=(layer_id == 0),
                **kwargs)
            # iter update
            tmp = reg_branches(output)
            tmp[..., :self.query_dim] += inverse_sigmoid(reference)
            new_reference = tmp[..., :self.query_dim].sigmoid()
            if layer_id != self.num_layers - 1:
                ref.append(new_reference)
            reference = new_reference.detach()

            if self.return_intermediate:
                if self.post_norm is not None:
                    intermediate.append(self.post_norm(output))
                else:
                    intermediate.append(output)

        if self.post_norm is not None:
            output = self.post_norm(output)

        if self.return_intermediate:
            return [
                torch.stack(intermediate),
                torch.stack(ref),
            ]
        else:
            return [output.unsqueeze(0), torch.stack(ref)]


class DabDetrTransformerEncoder(DetrTransformerEncoder):
    """Encoder of DAB-DETR."""

    def _init_layers(self):
        """Initialize encoder layers."""
        self.layers = ModuleList([
            DetrTransformerEncoderLayer(**self.layer_cfg)
            for _ in range(self.num_layers)
        ])
        embed_dims = self.layers[0].embed_dims
        self.embed_dims = embed_dims
        self.query_scale = MLP(embed_dims, embed_dims, embed_dims, 2)

    def forward(self,
                query,
                query_pos=None,
                query_key_padding_mask=None,
                **kwargs):
        """Forward function of encoder.

        Args:
            query (Tensor): Input queries of encoder, has shape
                (bs, num_queries, dim).
            query_pos (Tensor): The positional embeddings of the queries, has
                shape (bs, num_feat_points, dim).
            query_key_padding_mask (Tensor): ByteTensor, the key padding mask
                of the queries, has shape (bs, num_feat_points).

        Returns:
            Tensor: With shape (num_queries, bs, dim).
        """

        for layer in self.layers:
            pos_scales = self.query_scale(query)
            query = layer(
                query,
                query_pos=query_pos * pos_scales,
                query_key_padding_mask=query_key_padding_mask,
                **kwargs)

        return query
