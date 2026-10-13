"""Local BDD100K detection and KITTI object-training adapters (M49 metrics)."""
import json
import math
from pathlib import Path


def segmentation_objects(record, classes):
    """Read actual Supervisely polygons; companion rectangles are not masks."""
    from ..schemas import Polygon
    for category in classes:
        shapes = [o['geometryType'] for o in record['objects'] if o['classTitle'] == category]
        if shapes.count('rectangle') and shapes.count('rectangle') != shapes.count('polygon'):
            raise ValueError('Có nhãn box thiếu polygon tương ứng; không dùng box làm mask hoặc nhãn rỗng')
    objects = []
    for obj in record['objects']:
        if obj['classTitle'] not in classes or obj['geometryType'] == 'rectangle':
            continue
        if obj['geometryType'] != 'polygon' or obj['points'].get('interior'):
            raise ValueError('Mẫu chứa mask có lỗ hoặc hình học chưa được hỗ trợ')
        points = [tuple(p) for p in obj['points']['exterior']]
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        # Remove only redundant points on straight segments: no mask approximation.
        clean = []
        for p in points:
            if not clean or p != clean[-1]:
                clean.append(p)
        while len(clean) > 3:
            reduced = []
            for i, b in enumerate(clean):
                a, c = clean[i-1], clean[(i+1) % len(clean)]
                cross = (b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
                forward = (b[0]-a[0])*(c[0]-b[0])+(b[1]-a[1])*(c[1]-b[1])
                if cross != 0 or forward <= 0:
                    reduced.append(b)
            if reduced == clean or len(reduced) < 3:
                break
            clean = reduced
        geometry = Polygon(kind='polygon', points=clean)
        size = record['size']
        if any(not (0 <= x <= size['width'] and 0 <= y <= size['height']) for x,y in geometry.points):
            raise ValueError('Polygon nằm ngoài ảnh')
        objects.append(dict(id=str(obj['id']), category=obj['classTitle'], geometry=geometry.model_dump(mode='json')))
    return objects


def child(root: Path, name: str) -> Path:
    if not name or '/' in name or '\\' in name or ':' in name or name in {'.', '..'}:
        raise ValueError('Tên mẫu phải là tên tệp, không chứa đường dẫn')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Tệp nằm ngoài thư mục dữ liệu')
    if not path.is_file():
        raise ValueError(f'Thiếu tệp: {path}')
    return path


def invert3(a):
    x, y, z = a
    cof = [[y[1]*z[2]-y[2]*z[1], y[2]*z[0]-y[0]*z[2], y[0]*z[1]-y[1]*z[0]],
           [z[1]*x[2]-z[2]*x[1], z[2]*x[0]-z[0]*x[2], z[0]*x[1]-z[1]*x[0]],
           [x[1]*y[2]-x[2]*y[1], x[2]*y[0]-x[0]*y[2], x[0]*y[1]-x[1]*y[0]]]
    det = sum(x[i]*cof[0][i] for i in range(3))
    if abs(det) < 1e-8:
        raise ValueError('Calibration không khả nghịch')
    return [[cof[j][i]/det for j in range(3)] for i in range(3)]


def mv(a, v):
    return [sum(x*y for x, y in zip(row, v)) for row in a]


def calibration(path):
    fields = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if ':' in line:
            key, values = line.split(':', 1)
            fields[key] = [float(v) for v in values.split()]
    r, t = fields.get('R0_rect', []), fields.get('Tr_velo_to_cam', [])
    if len(r) != 9 or len(t) != 12 or not all(math.isfinite(v) for v in r+t):
        raise ValueError('Cần R0_rect (9 số) và Tr_velo_to_cam (12 số) trong calibration KITTI')
    r = [r[i:i+3] for i in range(0, 9, 3)]
    rotation = [[sum(r[i][k]*t[k*4+j] for k in range(3)) for j in range(3)] for i in range(3)]
    translation = mv(r, [t[3], t[7], t[11]])
    return invert3(rotation), translation


def camera_input(root, name):
    from PIL import Image
    root = Path(root)
    stem = Path(name).stem
    fields = {}
    for line in child(root/'calib', stem+'.txt').read_text(encoding='utf-8').splitlines():
        if ':' in line:
            key, values = line.split(':',1)
            fields[key] = [float(v) for v in values.split()]
    result = {}
    for key, rows, columns in [('R0_rect',3,3),('Tr_velo_to_cam',3,4),('P2',3,4)]:
        values = fields.get(key,[])
        if len(values) != rows*columns or not all(math.isfinite(v) for v in values):
            raise ValueError(f'Thiếu calibration {key} cho {name}')
        result[key] = [values[i:i+columns] for i in range(0,len(values),columns)]
    with Image.open(child(root/'image_2',stem+'.png')) as image:
        result['image_shape'] = [image.height,image.width]
    return result


def kitti_objects(path, classes, transform=None):
    objects, ignored = [], 0
    for index, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines()):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 15:
            raise ValueError(f'{path.name}:{index+1}: cần 15 trường nhãn ground truth KITTI')
        category = fields[0]
        if category == 'DontCare':
            ignored += 1
            continue
        if category not in classes:
            continue
        values = [float(v) for v in fields[1:]]
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Nhãn KITTI chứa số không hữu hạn')
        if transform is None:
            geometry = dict(kind='bbox2d', xyxy=values[3:7])
        else:
            h, w, length, x, y, z, ry = values[7:14]
            inv, translation = transform
            # KITTI stores bottom-center in rectified camera coordinates.
            center = mv(inv, [x-translation[0], y-h/2-translation[1], z-translation[2]])
            direction = mv(inv, [math.cos(ry), 0, -math.sin(ry)])
            geometry = dict(kind='cuboid3d', center=center, size_lwh=[length, w, h],
                            yaw=math.atan2(direction[1], direction[0]), frame='lidar')
        objects.append(dict(id=str(index), category=category, geometry=geometry))
    return objects, ignored


def prepare(dataset, root, labels_path, classes, names, limit):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('Thư mục dữ liệu không tồn tại')
    if not classes or len(classes) != len(set(classes)):
        raise ValueError('Cần danh sách lớp không trùng')
    warnings = []
    if dataset == 'bdd100k_segmentation':
        folder = root/'assets'
        names = names or sorted(p.name.removesuffix('.json') for p in (root/'source_annotations').glob('*.json'))[:limit]
        if not names or len(names) > 20 or len(names) != len(set(names)):
            raise ValueError('Chọn từ 1–20 tên mẫu không trùng')
        files, samples = [], []
        for name in names:
            files.append(child(folder, name))
            record = json.loads(child(root/'source_annotations', name+'.json').read_text(encoding='utf-8'))
            samples.append(dict(asset_name=name, objects=segmentation_objects(record, classes)))
        return 'instance_segmentation', files, samples, ['BDD100K polygon từ bản chuyển đổi Supervisely; điểm M49, không phải COCO mask AP.']
    if dataset == 'bdd100k':
        path = Path(labels_path).expanduser()
        if not path.is_file() or path.stat().st_size > 512*1024*1024:
            raise ValueError('Chọn JSON nhãn BDD100K, tối đa 512 MiB')
        records = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(records, list):
            raise ValueError('BDD100K cần JSON danh sách frame')
        indexed = {}
        for record in records:
            name = record['name']
            if name in indexed:
                raise ValueError(f'Tên ảnh trùng: {name}')
            indexed[name] = record
        names = names or sorted(n for n in indexed if (root/n).is_file())[:limit]
        task, folder = 'detection_2d', root
    else:
        task = 'detection_3d' if dataset == 'kitti_3d' else 'detection_2d'
        folder = root / ('velodyne' if task == 'detection_3d' else 'image_2')
        suffix = '.bin' if task == 'detection_3d' else '.png'
        names = names or sorted(p.name for p in folder.glob('*'+suffix))[:limit]
        warnings.append('KITTI: bỏ DontCare và lớp ngoài lựa chọn; điểm M49 không phải KITTI AP chính thức.')
        if task == 'detection_3d':
            warnings.append('Cuboid M49 chỉ có yaw: tâm dùng calibration đầy đủ, hướng chiếu lên XY, bỏ roll/pitch nhỏ của camera.')
    if not names or len(names) > 20 or len(names) != len(set(names)):
        raise ValueError('Chọn từ 1–20 tên mẫu không trùng')
    samples, files, ignored = [], [], 0
    for name in names:
        files.append(child(folder, name))
        if dataset == 'bdd100k':
            record = indexed.get(name)
            if record is None or not isinstance(record.get('labels'), list):
                raise ValueError(f'Thiếu nhãn cho {name}; dùng split train/val có ground truth')
            objects = []
            for label in record['labels']:
                if label['category'] not in classes:
                    continue
                b = label['box2d']
                objects.append(dict(id=str(label['id']), category=label['category'],
                                    geometry=dict(kind='bbox2d', xyxy=[b['x1'], b['y1'], b['x2'], b['y2']])))
        else:
            stem = Path(name).stem
            transform = calibration(child(root/'calib', stem+'.txt')) if task == 'detection_3d' else None
            objects, count = kitti_objects(child(root/'label_2', stem+'.txt'), classes, transform)
            ignored += count
        samples.append(dict(asset_name=name, objects=objects))
    if ignored:
        warnings.append(f'Đã bỏ {ignored} vùng DontCare.')
    return task, files, samples, warnings
