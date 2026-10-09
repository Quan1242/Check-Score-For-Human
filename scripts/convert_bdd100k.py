"""Convert BDD100K image labels (box2d) to a ground-truth M49 bundle.

Only explicitly selected files/classes are included. Missing input labels are
errors, not empty predictions. This converter does not create AI confidence.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True, help='JSON list of exact image filenames')
    parser.add_argument('--classes', required=True, help='Comma-separated original BDD class names')
    parser.add_argument('--class-map', type=Path, help='Optional JSON original class -> M49 class')
    args = parser.parse_args()
    names = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
        parser.error('Manifest phải là danh sách tên ảnh không rỗng, không trùng')
    records = json.loads(args.input.read_text(encoding='utf-8-sig'))
    if not isinstance(records, list):
        parser.error('Input cần danh sách BDD100K image labels')
    indexed = {}
    for record in records:
        name = record['name']
        if name in indexed:
            parser.error(f'Tên ảnh trùng trong input: {name}')
        indexed[name] = record
    classes = {c.strip() for c in args.classes.split(',') if c.strip()}
    mapping = json.loads(args.class_map.read_text(encoding='utf-8-sig')) if args.class_map else {}
    if not classes or not isinstance(mapping, dict) or any(not isinstance(v, str) or not v.strip() for v in mapping.values()):
        parser.error('Danh sách lớp hoặc class map không hợp lệ')
    samples = []
    for name in names:
        if name not in indexed or 'labels' not in indexed[name]:
            parser.error(f'Thiếu nhãn cho {name}')
        objects = []
        for label in indexed[name]['labels']:
            category = label['category']
            if category not in classes:
                continue
            if 'box2d' not in label:
                parser.error(f'{name}: đối tượng {label.get("id")} thuộc lớp được chọn nhưng thiếu box2d')
            box = label['box2d']
            objects.append(dict(id=str(label['id']), category=mapping.get(category, category),
                geometry=dict(kind='bbox2d', xyxy=[box['x1'], box['y1'], box['x2'], box['y2']]), confidence=None))
        samples.append(dict(asset_name=name, objects=objects, active_seconds=None))
    bundle = dict(schema_version='1.0', task='detection_2d', name=args.input.stem[:120], samples=samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error('Output đã tồn tại; chọn tên mới để giữ bản cũ')
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Đã chuyển {len(samples)} mẫu. API sẽ kiểm tra lớp, tọa độ và kích thước ảnh khi nhập.')


if __name__ == '__main__':
    main()
