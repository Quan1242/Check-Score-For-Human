"""PointPillars (zhulf0804) output convention -> M49; also embedded in Colab.

Upstream boxes are [x,y,bottom_z,width,length,height,rotation_y]. Its corner
routine rotates local coordinates clockwise; length lies on local Y.
M49 uses geometric center, [length,width,height], counterclockwise length yaw.
"""
import math


def pointpillars_geometry(box):
    if len(box) != 7 or not all(math.isfinite(float(v)) for v in box):
        raise ValueError('PointPillars box must contain seven finite values')
    x,y,z,width,length,height,angle = map(float,box)
    if min(width,length,height) <= 0:
        raise ValueError('PointPillars box dimensions must be positive')
    yaw = (math.pi/2-angle+math.pi) % (2*math.pi)-math.pi
    return dict(kind='cuboid3d',center=[x,y,z+height/2],size_lwh=[length,width,height],yaw=yaw,frame='lidar')


def in_evaluation_scope(geometry, camera):
    """Same center-based forward range and camera FOV for GT and predictions."""
    x,y,z = geometry['center']
    if not (0 <= x < 69.12 and -39.68 <= y < 39.68):
        return False
    p = [x,y,z,1]
    cam = [sum(row[j]*p[j] for j in range(4)) for row in camera['Tr_velo_to_cam']]
    rect = [sum(row[j]*cam[j] for j in range(3)) for row in camera['R0_rect']]+[1]
    projected = [sum(row[j]*rect[j] for j in range(4)) for row in camera['P2']]
    h,w = camera['image_shape']
    return projected[2] > 0 and 0 <= projected[0]/projected[2] < w and 0 <= projected[1]/projected[2] < h


def pointpillars_objects(result, confidence, camera):
    boxes, labels, scores = result['lidar_bboxes'], result['labels'], result['scores']
    if len(boxes) != len(labels) or len(labels) != len(scores):
        raise ValueError('PointPillars output lengths differ')
    objects = []
    for index, (box, label, score) in enumerate(zip(boxes,labels,scores)):
        score = float(score)
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError('Invalid confidence from PointPillars')
        if int(label) != 2 or score < confidence:  # Upstream label 2 = Car.
            continue
        geometry = pointpillars_geometry(box)
        if in_evaluation_scope(geometry,camera):
            objects.append(dict(id=str(index),category='car',confidence=score,geometry=geometry))
    return objects
