"""CVAT COCO box exchange, adapted to M49's validated experiment workflow."""
import json
import math
import zipfile
from io import BytesIO

from ..schemas import LabelBundle

MAX_JSON_BYTES = 32 * 1024 * 1024


def parse_coco(data: bytes, assets: dict, *, annotator: str, parent_id=None, task='detection_2d'):
    if task not in {'detection_2d', 'instance_segmentation'}:
        raise ValueError('COCO chỉ hỗ trợ box 2D hoặc polygon segmentation.')
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            candidates = [i for i in archive.infolist() if not i.is_dir()
                          and i.filename.lower().endswith('.json')
                          and not i.filename.startswith('__MACOSX/')]
            preferred = [i for i in candidates if i.filename.rsplit('/', 1)[-1].startswith('instances')]
            candidates = preferred or candidates
            if len(candidates) != 1:
                raise ValueError('ZIP cần đúng một tệp nhãn COCO (instances*.json).')
            info = candidates[0]
            if info.file_size > MAX_JSON_BYTES:
                raise ValueError('JSON giải nén tối đa 32 MiB.')
            with archive.open(info) as stream:
                raw = stream.read(MAX_JSON_BYTES + 1)
            if len(raw) > MAX_JSON_BYTES:
                raise ValueError('JSON giải nén quá lớn.')
            coco = json.loads(raw)
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError, RuntimeError, NotImplementedError) as exc:
        raise ValueError('Không đọc được ZIP/JSON COCO.') from exc
    if not isinstance(coco, dict) or any(not isinstance(coco.get(k), list) for k in ('images', 'categories', 'annotations')):
        raise ValueError('COCO cần images, categories và annotations dạng danh sách.')

    def indexed(rows, label):
        result = {}
        for row in rows:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] in result:
                raise ValueError(f'{label}: ID phải là số nguyên duy nhất.')
            result[row['id']] = row
        return result

    images = indexed(coco['images'], 'Ảnh')
    categories = indexed(coco['categories'], 'Lớp')
    annotations = indexed(coco['annotations'], 'Đối tượng')
    samples = {}
    seen = set()
    for image_id, img in images.items():
        filename = img.get('file_name')
        if not isinstance(filename, str):
            raise ValueError('Thiếu tên ảnh COCO.')
        name = filename.replace('\\', '/').rsplit('/', 1)[-1]
        if name not in assets or name in seen:
            raise ValueError(f'Ảnh không thuộc thử nghiệm hoặc trùng tên: {name}')
        asset = assets[name]
        if img.get('width') != asset.width or img.get('height') != asset.height:
            raise ValueError(f'Kích thước COCO khác ảnh gốc: {name}')
        seen.add(name)
        samples[image_id] = dict(asset_name=name, objects=[])
    if seen != set(assets):
        raise ValueError('COCO phải chứa đầy đủ ảnh của thử nghiệm, kể cả ảnh không có đối tượng.')
    for annotation_id, ann in annotations.items():
        image_id, category_id = ann.get('image_id'), ann.get('category_id')
        if type(image_id) is not int or type(category_id) is not int or image_id not in samples or category_id not in categories:
            raise ValueError('Annotation tham chiếu ảnh/lớp không tồn tại.')
        if ann.get('iscrowd', 0) != 0:
            raise ValueError('Chưa hỗ trợ COCO iscrowd; không tự bỏ qua đối tượng.')
        if task == 'instance_segmentation':
            rings = ann.get('segmentation')
            if not isinstance(rings, list) or len(rings) != 1 or not isinstance(rings[0], list):
                raise ValueError('Mỗi instance cần một polygon đơn; chưa hỗ trợ RLE, holes hoặc multipart. Không chuyển mask thành box.')
            coords = rings[0]
            if len(coords) < 6 or len(coords) > 2002 or len(coords) % 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in coords):
                raise ValueError('Polygon cần 3–1000 đỉnh với tọa độ hữu hạn x,y.')
            points = list(zip(coords[::2], coords[1::2]))
            if points[0] == points[-1]:
                points.pop()  # COCO exporters may repeat the closing vertex.
            geometry = dict(kind='polygon', points=points)
        else:
            box = ann.get('bbox')
            if not isinstance(box, list) or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
                raise ValueError('COCO bbox cần bốn số hữu hạn [x,y,width,height].')
            x, y, w, h = box
            geometry = dict(kind='bbox2d', xyxy=[x, y, x+w, y+h])
        samples[image_id]['objects'].append(dict(id=str(annotation_id), category=categories[category_id].get('name'),
            geometry=geometry))
    return LabelBundle(task=task, name='CVAT COCO import', annotator=annotator,
                       parent_id=parent_id, samples=list(samples.values()))


def coco_export(assets, classes, samples):
    categories = [{'id': i+1, 'name': name} for i, name in enumerate(classes)]
    category_ids = {c['name']: c['id'] for c in categories}
    images, annotations = [], []
    for image_id, asset in enumerate(assets, 1):
        images.append(dict(id=image_id, file_name=asset.name, width=asset.width, height=asset.height))
        for obj in samples[asset.name]['objects']:
            geom = obj['geometry']
            segmentation = None
            if geom['kind'] == 'polygon':
                points = geom['points']
                xs, ys = zip(*points)
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                area = abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(points, points[1:]+points[:1]))) / 2
                segmentation = [[v for point in points for v in point]]
            else:
                x1, y1, x2, y2 = geom['xyxy']
                area = (x2-x1)*(y2-y1)
            annotation = dict(id=len(annotations)+1, image_id=image_id, category_id=category_ids[obj['category']],
                bbox=[x1, y1, x2-x1, y2-y1], area=area, iscrowd=0, score=obj['confidence'])
            if segmentation is not None:
                annotation['segmentation'] = segmentation
            annotations.append(annotation)
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('annotations/instances_default.json', json.dumps(dict(images=images, categories=categories, annotations=annotations), ensure_ascii=False))
    return output.getvalue()
