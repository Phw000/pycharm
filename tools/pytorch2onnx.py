# Modified from https://github.com/facebookresearch/detectron2/blob/master/detectron2/export/api.py # noqa
import argparse
import io

import mmcv
import onnx
import torch
from mmcv.runner import load_checkpoint
from onnx import optimizer
from torch.onnx import OperatorExportTypes

from mmdet.models import build_detector


def export_onnx_model(model, inputs):
    """
    Trace and export a model to onnx format.

    Args:
        model (nn.Module):
        inputs (tuple[args]): the model will be called by `model(*inputs)`

    Returns:
        an onnx model
    """
    assert isinstance(model, torch.nn.Module)

    # make sure all modules are in eval mode, onnx may change the training
    # state of the module if the states are not consistent
    def _check_eval(module):
        assert not module.training

    model.apply(_check_eval)

    # Export the model to ONNX
    with torch.no_grad():
        with io.BytesIO() as f:
            torch.onnx.export(
                model,
                inputs,
                f,
                operator_export_type=OperatorExportTypes.ONNX_ATEN_FALLBACK,
                # verbose=True,  # NOTE: uncomment this for debugging
                # export_params=True,
            )
            onnx_model = onnx.load_from_string(f.getvalue())

    # Apply ONNX's Optimization
    all_passes = optimizer.get_available_passes()
    passes = ['fuse_bn_into_conv']
    assert all(p in all_passes for p in passes)
    onnx_model = optimizer.optimize(onnx_model, passes)
    return onnx_model


def parse_args():
    parser = argparse.ArgumentParser(
        description='MMDet test (and eval) a model')
    parser.add_argument('config', help='test config file path')
    parser.add_argument('checkpoint', help='checkpoint file')
    parser.add_argument(
        '--out', type=str, required=True, help='output ONNX filename')
    parser.add_argument(
        '--shape',
        type=int,
        nargs='+',
        default=[1280, 800],
        help='input image size')
    args = parser.parse_args()
    return args


def main():
    args = parse_args()

    if not args.out.endswith('.onnx'):
        raise ValueError('The output file must be a onnx file.')

    if len(args.shape) == 1:
        input_shape = (3, args.shape[0], args.shape[0])
    elif len(args.shape) == 2:
        input_shape = (3, ) + tuple(args.shape)
    else:
        raise ValueError('invalid input shape')

    cfg = mmcv.Config.fromfile(args.config)
    cfg.model.pretrained = None

    # build the model and load checkpoint
    model = build_detector(cfg.model, train_cfg=None, test_cfg=cfg.test_cfg)
    load_checkpoint(model, args.checkpoint, map_location='cpu')
    # Only support CPU mode
    model.cpu().eval()
    # TODO: a better way to override forward function
    if hasattr(model, 'forward_dummy'):
        model.forward = model.forward_dummy
    else:
        raise NotImplementedError(
            'ONNX conversion is currently not currently supported with '
            '{}'.format(model.__class__.__name__))

    input_data = torch.ones(()).new_empty(
        (1, *input_shape),
        dtype=next(model.parameters()).dtype,
        device=next(model.parameters()).device)

    onnx_model = export_onnx_model(model, (input_data, ))
    # Print a human readable representation of the graph
    onnx.helper.printable_graph(onnx_model.graph)
    print('saving model in {}'.format(args.out))
    onnx.save(onnx_model, args.out)


if __name__ == '__main__':
    main()
