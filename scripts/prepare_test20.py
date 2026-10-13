"""Prepare the requested 10 BDD + 10 KITTI scenes from verified local downloads.

Selection was reviewed using source annotations and contact sheets, before AI.
Difficulty is relative annotation workload for car/Car, not official KITTI tiers.
"""
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.adapters.datasets import prepare
from app.schemas import LabelBundle

BDD = {
    'easy': ['b1ca8418-84a133a0.jpg'],
    'medium': ['b1cd1e94-549d0bfe.jpg', 'b1ceb32e-3f481b43.jpg', 'b1ceb32e-51852abe.jpg',
               'b1d0091f-75824d0d.jpg', 'b1d0a191-03dcecc2.jpg', 'b1d0a191-2ed2269e.jpg', 'b1d10d08-ec660956.jpg'],
    'hard': ['b1d10d08-c35503b8.jpg', 'b1d22449-15fb948f.jpg'],
}
KITTI = {'easy': ['000003', '000020'],
         'medium': ['000006', '000007', '000009', '000011', '000016', '000019', '000025'],
         'hard': ['000010']}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_checked(source, target, expected):
    if sha(source) != expected:
        raise ValueError(f'Checksum mismatch: {source}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    assert sha(target) == expected


def main():
    out = ROOT/'data/test20'
    if out.exists():
        raise SystemExit('data/test20 already exists; refusing to overwrite a frozen selection')
    bdd = ROOT/'data/bdd100k_2d_pilot'
    kitti = ROOT/'data/kitti_pilot'
    bdd_manifest = json.loads((bdd/'manifest.json').read_text(encoding='utf-8'))
    bdd_files = {f['name']: f for f in bdd_manifest['files']}
    rows = json.loads((bdd/'source_annotations.json').read_text(encoding='utf-8'))['samples']
    records = {Path(r['filepath']).name: r for r in rows}
    kitti_manifest = json.loads((kitti/'manifest.json').read_text(encoding='utf-8'))
    kitti_files = {s['id']: s for s in kitti_manifest['samples']}
    strata, scalabel, originals = [], [], []
    for difficulty, names in BDD.items():
        for name in names:
            record = records[name]
            target = out/'bdd100k/assets'/name
            copy_checked(bdd/'assets'/name, target, bdd_files[name]['sha256'])
            with Image.open(target) as image:
                width, height = image.size
                image.verify()
            assert (width,height) == (record['metadata']['width'],record['metadata']['height'])
            labels, count, occluded, small, clipped = [], 0, 0, 0, 0
            for index, d in enumerate(record['detections']['detections']):
                # Source mirror uses normalized top-left xywh; preserve all source classes.
                x,y,w,h = d['bounding_box']
                raw = [x*width,y*height,(x+w)*width,(y+h)*height]
                box = [max(0,min(width,raw[0])),max(0,min(height,raw[1])),max(0,min(width,raw[2])),max(0,min(height,raw[3]))]
                assert box[2] > box[0] and box[3] > box[1]
                clipped += int(any(abs(a-b)>1e-6 for a,b in zip(raw,box)))
                labels.append(dict(id=str(index), category=d['label'], box2d=dict(zip(['x1','y1','x2','y2'],box)),
                                   attributes=dict(occluded=d.get('occluded',False),truncated=d.get('truncated',False))))
                if d['label'] == 'car':
                    count += 1; occluded += bool(d.get('occluded')); small += h*height < 40
            scalabel.append(dict(name=name, attributes={k:record[k]['label'] for k in ['weather','timeofday','scene']}, labels=labels))
            originals.append(record)
            strata.append(dict(dataset='BDD100K', asset_name=name, difficulty=difficulty, car_count=count,
                               occluded_cars=occluded, cars_under_40px_height=small, clipped_source_boxes=clipped,
                               timeofday=record['timeofday']['label'], weather=record['weather']['label'],
                               sha256=sha(target), source=bdd_files[name]['source']))
    write_json(out/'bdd100k/labels.json',scalabel)
    write_json(out/'bdd100k/source_annotations.json',dict(samples=originals))
    for difficulty, names in KITTI.items():
        for name in names:
            checksums = {}
            for kind in ['image_2','label_2','calib','velodyne']:
                item = kitti_files[name][kind]
                source = kitti/item['path']; target = out/'kitti'/item['path']
                copy_checked(source,target,item['sha256']); checksums[kind] = item['sha256']
                if kind == 'image_2':
                    with Image.open(target) as image: image.verify()
                if kind == 'velodyne': assert target.stat().st_size % 16 == 0
            labels = [line.split() for line in (out/f'kitti/training/label_2/{name}.txt').read_text().splitlines() if line.startswith('Car ')]
            strata.append(dict(dataset='KITTI',asset_name=name+'.png',difficulty=difficulty,car_count=len(labels),
                               occluded_cars=sum(int(d[2])>0 for d in labels), cars_under_40px_height=sum(float(d[7])-float(d[5])<40 for d in labels),
                               sha256=checksums,source=kitti_manifest['download_base']))
    counts = Counter(s['difficulty'] for s in strata)
    assert counts == {'easy':3,'medium':14,'hard':3} and len(strata) == 20
    requests = []
    for dataset, root, labels, classes in [
        ('bdd100k',out/'bdd100k/assets',str(out/'bdd100k/labels.json'),['car']),
        ('kitti_2d',out/'kitti/training','',['Car']),
        ('kitti_3d',out/'kitti/training','',['Car']),
    ]:
        task, files, samples, warnings = prepare(dataset,str(root),labels,classes,[],10)
        bundle = LabelBundle(task=task,name=f'Test20 {dataset} ground truth',samples=samples)
        if task == 'detection_2d':
            for path,sample in zip(files,bundle.samples):
                with Image.open(path) as image:
                    for obj in sample.objects:
                        assert obj.geometry.xyxy[2] <= image.width and obj.geometry.xyxy[3] <= image.height
        write_json(out/f'{dataset}_ground_truth_m49.json',bundle.model_dump(mode='json'))
        requests.append(dict(dataset=dataset,name=f'Test20 {dataset}',root=str(root),labels_path=labels,classes=classes,names=[p.name for p in files],limit=10))
        write_json(out/f'{dataset}_manifest.json',[p.name for p in files])
    write_json(out/'import_requests.json',requests)
    write_json(out/'selection.json',dict(total_images=20,counts=dict(counts),classes=['car (BDD100K)','Car (KITTI)'],
        classification='Manually reviewed annotation workload relative to this pilot pool; not official dataset difficulty.',
        notes=['Selected before AI inference from an existing 30-scene pool per dataset; not a representative random benchmark.',
               'BDD100K annotations from pinned dgural/bdd100k mirror; original release version not independently verified.',
               'KITTI LiDAR/calibration correspond to the same 10 image scenes; no extra images.'],samples=strata))
    readme = '''# Bộ test 20 ảnh

Đã chọn và kiểm tra checksum từ các tệp tải sẵn. Tổng **20 ảnh**: 10 BDD100K + 10 KITTI.

- BDD100K: 7 thường, 2 khó, 1 dễ.
- KITTI: 7 thường, 1 khó, 2 dễ.
- Tổng: **14 thường, 3 khó, 3 dễ**. Tác vụ gán nhãn xe `car`/`Car`.

Độ khó là ước lượng công gán nhãn trong bộ thử này, dựa trên số xe, xe nhỏ (<40 px chiều cao), che khuất và quan sát ảnh. Dễ: ít xe, biên xe tương đối rõ; thường: mật độ/mức che khuất vừa so với bộ ứng viên; khó: rất nhiều xe hoặc xe rất nhỏ trong cảnh tối. Không phải mức Easy/Moderate/Hard chính thức của KITTI và chưa phải tập đánh giá đại diện. `selection.json` ghi số liệu từng ảnh và nguồn/checksum. Chưa dùng dự đoán AI để chọn mẫu.

BDD100K dễ là cảnh đêm có 2 xe tương đối lớn, ít công vẽ hơn các ứng viên; không có nghĩa model chắc chắn nhận diện tốt. Hai ảnh khó gồm cảnh 21 xe và cảnh đêm có 9 xe nhỏ/che khuất. KITTI dễ: 000003, 000020 (mỗi ảnh 1 xe rõ); khó: 000010 (8 xe, 4 bị che khuất).

## Dùng trong ứng dụng

Tab Dữ liệu → Nhập BDD100K / KITTI:

1. BDD100K: root = thư mục `bdd100k/assets` trong bộ này; labels_path = `bdd100k/labels.json`; lớp `car`; 10 mẫu.
2. KITTI 2D hoặc 3D: root = thư mục `kitti/training`; lớp `Car`; 10 mẫu.
3. `import_requests.json` chứa đường dẫn tuyệt đối và payload chính xác cho `/api/datasets/import`.

Đã xuất ground truth M49 và manifest cho cả 3 tác vụ nhập. KITTI 3D dùng cùng 10 cảnh, có BIN và calibration, không thêm ảnh mới. Chọn cùng manifest cho Manual/AI/Assisted. Không dùng `scripts/prepare_demo.py` mặc định vì script cũ chọn tỷ lệ khác.

## Nguồn

BDD100K validation: https://huggingface.co/datasets/dgural/bdd100k/tree/c2e7f266756bcd07b87f1a45a35937c8eac20241
Ảnh và nhãn mirror được giữ nguồn; phiên bản phát hành nhãn gốc chưa xác minh độc lập. `labels.json` chuyển bounding box normalized xywh sang pixel xyxy; giữ nhãn nguồn trong `source_annotations.json`. Việc clip biên nếu có được đếm trong selection.json.

KITTI training: https://www.cvlibs.net/datasets/kitti/eval_object.php
Tệp nguồn từ https://s3.eu-central-1.amazonaws.com/avg-kitti/ (data_object_image_2.zip, data_object_label_2.zip, data_object_calib.zip, data_object_velodyne.zip).

Thư mục này thuộc data/ đã được gitignore. Không xóa các bộ pilot nguồn. AI chưa chạy; đây là dữ liệu và ground truth.
'''
    (out/'README.md').write_text(readme,encoding='utf-8')
    print(json.dumps(dict(output=str(out),counts=dict(counts),images=20,total_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())),ensure_ascii=False))


if __name__ == '__main__':
    main()
