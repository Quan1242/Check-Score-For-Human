import math

import pytest

from app.evaluation.metrics import geometry_iou, score_sample


def label(identifier, geometry, category='car'):
    return dict(id=identifier, category=category, geometry=geometry)


def test_polygon_pixel_masks_iou_and_dice():
    # Two 4x4 masks overlap in 2x4 pixels: IoU=8/24 and Dice=16/32.
    truth = label('gt', dict(kind='polygon', points=[(0, 0), (4, 0), (4, 4), (0, 4)]))
    pred = label('pred', dict(kind='polygon', points=[(2, 0), (6, 0), (6, 4), (2, 4)]))
    report = score_sample([pred], [truth], ['car'], 0.3, (10, 10))
    assert report['tp'] == 1
    assert report['mean_iou'] == pytest.approx(1/3)
    assert report['pairs'][0]['dice'] == pytest.approx(0.5)


def test_cuboid_rotation_and_height_overlap():
    box = dict(kind='cuboid3d', center=[0, 0, 0], size_lwh=[4, 2, 2], yaw=0, frame='lidar')
    rotated = {**box, 'yaw': math.pi/2}
    assert geometry_iou(box, rotated) == pytest.approx(1/3)
    raised = {**box, 'center': [0, 0, 1]}
    assert geometry_iou(box, raised) == pytest.approx(1/3)


def test_wrong_class_is_not_a_true_positive():
    box = dict(kind='bbox2d', xyxy=[0, 0, 10, 10])
    report = score_sample([label('pred', box, 'bus')], [label('gt', box)], ['car', 'bus'], 0.5)
    assert (report['tp'], report['fp'], report['fn']) == (0, 1, 1)
