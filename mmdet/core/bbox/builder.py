from mmdet.utils import build_from_cfg
from .assigners import BaseAssigner
from .coder import BaseCoder
from .registry import BBOX_ASSIGNERS, BBOX_CODER, BBOX_SAMPLERS
from .samplers import BaseSampler


def build_assigner(cfg, **default_args):
    if isinstance(cfg, BaseAssigner):
        return cfg
    return build_from_cfg(cfg, BBOX_ASSIGNERS, default_args)


def build_sampler(cfg, **default_args):
    if isinstance(cfg, BaseSampler):
        return cfg
    return build_from_cfg(cfg, BBOX_SAMPLERS, default_args)


def build_coder(cfg, **default_args):
    if isinstance(cfg, BaseCoder):
        return cfg
    return build_from_cfg(cfg, BBOX_CODER, default_args)
