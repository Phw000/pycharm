# MMDetection with OA-Mix

<div align=center>
    <img src="resources/oamix_examples.gif" width="640"/>
</div>

## Introduction

This repository is a fork of the [mmdetection](https://github.com/open-mmlab/mmdetection) toolbox with the implementation of OA-Mix,
a novel data augmentation technique designed to improve domain generalization in single-domain object detection.
OA-Mix is part of the [Object-Aware Domain Generalization (OA-DG)](https://github.com/woojulee24/OA-DG) framework,
introduced in the paper [Object-Aware Domain Generalization for Object Detection](https://ojs.aaai.org/index.php/AAAI/article/view/28076).

This repository has been created to showcase the OA-Mix method.
The method enhances model robustness against domain shifts by generating diverse multi-domain data while preserving object annotations.

For more information on the details of OA-Mix and its use cases,
please refer to the paper [Object-Aware Domain Generalization for Object Detection](https://ojs.aaai.org/index.php/AAAI/article/view/28076), presented at AAAI 2024.

## Example of OA-Mix

Below is an example showing the results of OA-Mix:

<div align=center>
<img src="resources/oamix_examples.png" width="1200"/>
</div>

## Performance Improvement with OA-Mix

Below is a performance comparison between a baseline object detection model and the same model with OA-Mix applied:

|         Model         |   Dataset    | mAP  | Gauss. | Shot | Impulse | Defocus | Glass | Motion | Zoom | Snow | Frost | Fog  | Bright | Contrast | Elastic | Pixel | JPEG | mPC  |
| :-------------------: | :----------: | :--: | :----: | :--: | :-----: | :-----: | :---: | :----: | :--: | :--: | :---: | :--: | :----: | :------: | :-----: | ----- | :--: | :--: |
|     Faster R-CNN      | Cityscapes-C | 42.2 |  0.5   | 1.1  |   1.1   |  17.2   | 16.5  |  18.3  | 2.1  | 2.2  | 12.3  | 29.8 |  32.0  |   24.1   |  40.1   | 18.7  | 15.1 | 15.4 |
| Faster R-CNN + OA-Mix | Cityscapes-C | 42.7 |  7.2   | 9.6  |   7.7   |  22.8   | 18.8  |  21.9  | 5.4  | 5.2  | 23.6  | 37.3 |  38.7  |   31.9   |  40.2   | 22.2  | 20.2 | 20.8 |

## mmdetection Readme

For information on mmdetection please refer to the [mmdetection readme](MMDETECTION_README.md).

## Installation

Please refer to [INSTALL.md](INSTALL.md) for installation and dataset preparation.

## Get Started

Please see [GETTING_STARTED.md](GETTING_STARTED.md) for the basic usage of MMDetection.

## Citation

If you use this toolbox or benchmark in your research, please cite this project.

```
@inproceedings{lee2024object,
  title={Object-Aware Domain Generalization for Object Detection},
  author={Lee, Wooju and Hong, Dasol and Lim, Hyungtae and Myung, Hyun},
  booktitle={Proceedings of the AAAI Conference on Artificial Intelligence},
  volume={38},
  number={4},
  pages={2947--2955},
  year={2024}
}
```

## Contact

This repo is currently maintained by Wooju Lee ([@WoojuLee24](https://github.com/WoojuLee24)) and Dasol Hong ([@dazory](https://github.com/dazory)).

For questions regarding mmdetection please visit the [official repository](https://github.com/open-mmlab/mmdetection).
