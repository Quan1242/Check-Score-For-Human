"""Update existing 2D notebook to Drive transport, then regenerate segmentation."""
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
path = ROOT/'colab/detection_2d.ipynb'
notebook = json.loads(path.read_text(encoding='utf-8'))
config = ''.join(notebook['cells'][2]['source'])
if '# M49_DRIVE_TRANSPORT' not in config:
    helper = (ROOT/'colab/drive_transport.py').read_text(encoding='utf-8')
    config = config.replace("ROOT = Path('/content/demo')", """# M49_DRIVE_TRANSPORT
"""+helper+"""
from google.colab import drive
drive.mount('/content/drive')
# Copy the job ID displayed in the app. This is the Colab path, not the Windows path.
ROOT = Path('/content/drive/MyDrive/M49/PASTE_JOB_ID')
request = load_drive_job(ROOT, 'detection_2d')
""")
    config = config.replace("CLASS_MAP = {'car': 'car', 'truck': 'truck', 'person': 'pedestrian'}", """# Exact semantic aliases only; Cyclist/rider cannot be replaced by a person box.
aliases = {'pedestrian': 'person', 'Car': 'car', 'Pedestrian': 'person', 'Truck': 'truck', 'Tram': 'train'}
CLASS_MAP = {aliases.get(category, category): category for category in request['classes']}
assert len(CLASS_MAP) == len(request['classes']), 'Hai lớp dự án trùng một lớp model'
""")
    config = config.replace("names = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8-sig'))", "names = request['manifest']")
    notebook['cells'][2]['source'] = config.splitlines(keepends=True)
    export = ''.join(notebook['cells'][4]['source'])
    export = export[:export.index('for filename, value in')]+"""environment = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
publish_drive_result(ROOT, request, bundle, timing, environment)
print('Đã ghi kết quả lên Drive. Backend đang chạy sẽ tự nhập sau khi Drive đồng bộ.')
"""
    notebook['cells'][4]['source'] = export.splitlines(keepends=True)
    notebook['cells'][0]['source'] = """# M49 · detection 2D trên Colab qua Google Drive
Trong ứng dụng, nhập BDD100K/KITTI 2D và tạo lượt Colab. Mount Drive, điền mã lượt vào ROOT rồi chạy các cell.
Notebook kiểm tra checksum ảnh và tự ghi dự đoán/thời gian/model vào Drive. Backend tự nhận, không tải JSON bằng tay.
YOLO11s dùng lớp COCO: mặc định thử car/Car. Các lớp không tương ứng (rider, Cyclist, traffic sign…) cần checkpoint phù hợp, không đổi tên để giả lập.
Pipeline cần kiểm chứng trên Colab/GPU trước khi thu số liệu chính thức.
Tài liệu: https://docs.ultralytics.com/models/yolo11/
""".splitlines(keepends=True)
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
notebook = json.loads(path.read_text(encoding='utf-8'))
config = ''.join(notebook['cells'][2]['source'])
if '# M49_MODEL_SELECTION' not in config:
    config = config.replace("CHECKPOINT = 'yolo11s.pt'", """# M49_MODEL_SELECTION
model_spec = request.get('model', {})
CHECKPOINT = model_spec.get('checkpoint', 'yolo11s.pt')
if model_spec.get('custom'):
    model_path = (ROOT.parent / CHECKPOINT).resolve()
    assert model_path.is_relative_to((ROOT.parent / 'models').resolve()), 'Checkpoint ngoài thư mục models'
    assert model_path.is_file(), 'Chờ Drive đồng bộ checkpoint'
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == model_spec['sha256'], 'Checkpoint chưa đồng bộ đủ'
    CHECKPOINT = str(model_path)
""")
    config = config.replace('CONFIDENCE = 0.25', "CONFIDENCE = model_spec.get('confidence', 0.25)")
    notebook['cells'][2]['source'] = config.splitlines(keepends=True)
    inference = ''.join(notebook['cells'][3]['source'])
    inference = inference.replace("assert set(CLASS_MAP) <= set(model.names.values())", "CLASS_MAP = {(category if category in model.names.values() else aliases.get(category, category)): category for category in request['classes']}\nassert set(CLASS_MAP) <= set(model.names.values())")
    notebook['cells'][3]['source'] = inference.splitlines(keepends=True)
    export = ''.join(notebook['cells'][4]['source']).replace("name='YOLO11s demo 2D'", "name=(Path(CHECKPOINT).name + ' · 2D')[:120]")
    notebook['cells'][4]['source'] = export.splitlines(keepends=True)
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
runpy.run_path(str(ROOT/'scripts/build_segmentation_notebook.py'), run_name='__main__')

# Keep the 3D template's transport automatic too; model inference remains explicit TODO.
path = ROOT/'colab/detection_3d.ipynb'
notebook = json.loads(path.read_text(encoding='utf-8'))
setup = ''.join(notebook['cells'][1]['source'])
if '# M49_DRIVE_TRANSPORT' not in setup:
    setup = '# M49_DRIVE_TRANSPORT\n'+(ROOT/'colab/drive_transport.py').read_text(encoding='utf-8')+"""
import subprocess, sys
from google.colab import drive
drive.mount('/content/drive')
ROOT = Path('/content/drive/MyDrive/M49/PASTE_JOB_ID')
request = load_drive_job(ROOT, 'detection_3d')
names = request['manifest']
paths = [ROOT/'assets'/name for name in names]
"""
    notebook['cells'][1]['source'] = setup.splitlines(keepends=True)
    export = ''.join(notebook['cells'][5]['source'])
    export = export[:export.index('output = Path')]+"""assert INFERENCE_SECONDS is not None, 'Đo inference bằng timer trong pipeline model'
environment = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
publish_drive_result(ROOT, request, bundle, {'inference_seconds': INFERENCE_SECONDS}, environment)
print('Đã xuất kết quả qua Drive; backend sẽ tự nhận.')
"""
    notebook['cells'][5]['source'] = export.splitlines(keepends=True)
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
