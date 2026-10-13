"""Regenerate the standalone Colab notebook from the 2D pipeline and M49 schema."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = json.loads((ROOT / 'colab/detection_2d.ipynb').read_text(encoding='utf-8'))
schema = (ROOT / 'backend/app/schemas.py').read_text(encoding='utf-8')
polygon_class = next(ast.get_source_segment(schema, n) for n in ast.parse(schema).body
                     if isinstance(n, ast.ClassDef) and n.name == 'Polygon')


def cell(kind, text):
    data = dict(cell_type=kind, metadata={}, source=text.splitlines(keepends=True))
    if kind == 'code':
        data.update(execution_count=None, outputs=[])
    return data


intro = '''# M49 · segmentation polygon trên Colab
YOLO11s-seg → JSON M49. Pipeline đã viết, chưa chạy inference GPU thực tế.
Backend dùng Python 3.14; Colab là môi trường AI riêng. Không cài Torch/YOLO vào backend.

Tạo lượt Colab trong ứng dụng, mount Drive và điền mã lượt vào ROOT (1–20 ảnh).
Kết quả tự ghi vào Drive để backend nhận. Thử 3–5 ảnh pilot trước khi khóa cấu hình.
Mỗi instance phải là một vùng không có lỗ; gặp multipart/holes thì dừng, không bỏ dự đoán.
Polygon là xấp xỉ biên mask mô hình, không phải mask pixel gốc. Ghi rõ khi báo cáo.
Không train và không dùng ground truth để điều chỉnh dự đoán.

Tài liệu: https://docs.ultralytics.com/tasks/segment/ và https://docs.ultralytics.com/models/yolo11/
'''
config = ''.join(base['cells'][2]['source']).replace("'yolo11s.pt'", "'yolo11s-seg.pt'")
config = config.replace("load_drive_job(ROOT, 'detection_2d')", "load_drive_job(ROOT, 'instance_segmentation')")
validation = '''# M49_POLYGON_VALIDATION: generated from backend schema; tested locally.
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

''' + polygon_class + '''

def validate_polygon(points, width, height):
    points = [list(p) for p in points]
    if points and points[0] == points[-1]:
        points.pop()
    polygon = Polygon(kind='polygon', points=points)
    if any(not (0 <= x <= width and 0 <= y <= height) for x,y in polygon.points):
        raise ValueError('Polygon nằm ngoài ảnh gốc')
    return polygon.model_dump(mode='json')['points']
'''
inference = '''import cv2
import numpy as np

start = stamp()
model = YOLO(CHECKPOINT)
load_seconds = stamp() - start
assert model.task == 'segment', 'Cần checkpoint segmentation (-seg.pt)'
CLASS_MAP = {(category if category in model.names.values() else aliases.get(category, category)): category for category in request['classes']}
assert set(CLASS_MAP) <= set(model.names.values()), 'Lớp không có trong checkpoint'
class_ids = [i for i, name in model.names.items() if name in CLASS_MAP]
for path in paths:
    with Image.open(path) as image:
        assert image.width*image.height <= 4_000_000, 'Ảnh vượt ngân sách 4 triệu pixel'
kwargs = dict(imgsz=IMGSZ, conf=CONFIDENCE, classes=class_ids, device=DEVICE,
              max_det=80, retina_masks=True, verbose=False, save=False)
start = stamp()
model.predict(str(paths[0]), **kwargs)
warmup_seconds = stamp() - start
samples, per_image = [], []
for name, path in zip(names, paths):
    with Image.open(path) as image:
        width, height = image.size
    start = stamp()
    result = model.predict(str(path), **kwargs)[0]
    predict_seconds = stamp() - start
    start = stamp()
    objects = []
    boxes = result.boxes
    count = len(boxes) if boxes is not None else 0
    assert count < 80, f'{name}: chạm max_det; chọn pilot ít đối tượng hơn để tránh cắt nhãn'
    assert width*height*count <= 16_000_000, f'{name}: cần giảm mẫu để còn ngân sách chấm ground truth'
    if count:
        assert result.masks is not None and len(result.masks.data)==count
        assert tuple(result.masks.data.shape[1:])==(height,width), 'Mask phải có độ phân giải ảnh gốc'
        polygons = result.masks.xy
        assert len(polygons)==count
        classes, confidences = boxes.cls.cpu().tolist(), boxes.conf.cpu().tolist()
        for index, (polygon, cls, conf) in enumerate(zip(polygons, classes, confidences)):
            mask = (result.masks.data[index].cpu().numpy()>0.5).astype(np.uint8)
            contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if len(contours)!=1 or hierarchy is None or hierarchy[0,0,2]!=-1:
                raise ValueError(f'{name}, instance {index}: mask rỗng, nhiều vùng hoặc có lỗ; M49 chưa hỗ trợ')
            points = validate_polygon(polygon.tolist(),width,height)
            objects.append(dict(id=f'ai-{index}',category=CLASS_MAP[model.names[int(cls)]],
                confidence=float(conf),geometry=dict(kind='polygon',points=points)))
    samples.append(dict(asset_name=name, objects=objects, active_seconds=None))
    per_image.append(dict(asset_name=name,predict_pipeline_seconds=predict_seconds,
        export_conversion_seconds=stamp()-start,stages_ms=result.speed,reached_max_det=False))
print('Đã tạo polygon cho',len(samples),'ảnh; ảnh không có dự đoán vẫn được giữ.')
'''
export = ''.join(base['cells'][4]['source']).replace("task='detection_2d'", "task='instance_segmentation'").replace("name='YOLO11s demo 2D'", "name='YOLO11s-seg polygon demo'")
export = export.replace(" + ' · 2D'", " + ' · segmentation'")
export = export.replace('timing = dict(', "timing = dict(mask_representation='single polygon approximation; multipart/holes rejected', ")
base['cells'] = [cell('markdown', intro), cell('code', '%pip install ultralytics==8.3.203 pydantic==2.14.1\n'),
                 cell('code', config), cell('code', validation), cell('code', inference), cell('code', export)]
(ROOT / 'colab/instance_segmentation.ipynb').write_text(json.dumps(base, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
