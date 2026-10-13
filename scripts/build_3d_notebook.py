"""Build the Colab PointPillars notebook, sharing the validated transport helpers."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '620e6b0d07e4cb37b7b0114f26b934e8be92a0ba'
CHECKSUM = '482dfcf63b932cc5ccf012b4bbdad52aa51aa33becf87d0a39d61c39b377b5b1'


def cell(kind, source):
    value = dict(cell_type=kind, metadata={}, source=source.splitlines(keepends=True))
    if kind == 'code':
        value.update(execution_count=None,outputs=[])
    return value


install = '''import os, sys, subprocess
from pathlib import Path
import torch
if not torch.cuda.is_available():
    raise RuntimeError('Chọn Runtime → Change runtime type → GPU, rồi Run all. PointPillars cần CUDA.')
if subprocess.run(['which','nvcc'],capture_output=True).returncode:
    raise RuntimeError('Runtime cần CUDA toolkit (nvcc) để cài PointPillars.')
subprocess.check_call([sys.executable,'-m','pip','install','--quiet',
    'ninja==1.11.1.4','numba==0.61.2','open3d==0.19.0','opencv-python-headless==4.11.0.86','PyYAML==6.0.2'])
REPO = Path('/content/m49_pointpillars')
COMMIT = 'COMMIT_VALUE'
if not REPO.exists():
    subprocess.check_call(['git','init',str(REPO)])
    subprocess.check_call(['git','-C',str(REPO),'remote','add','origin','https://github.com/zhulf0804/PointPillars.git'])
    subprocess.check_call(['git','-C',str(REPO),'fetch','--depth','1','origin',COMMIT])
    subprocess.check_call(['git','-C',str(REPO),'checkout','--detach','FETCH_HEAD'])
if subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip() != COMMIT:
    raise RuntimeError('Thư mục PointPillars không đúng phiên bản; dùng runtime Colab mới.')
# Build against the CUDA/PyTorch supplied by Colab; do not install upstream's old Torch 1.8 requirements.
subprocess.check_call([sys.executable,'setup.py','build_ext','--inplace'],cwd=REPO,env={**os.environ,'MAX_JOBS':'2'})
sys.path.insert(0,str(REPO))
print('PointPillars ready:',COMMIT,'Torch:',torch.__version__,'CUDA:',torch.version.cuda)
'''.replace('COMMIT_VALUE',COMMIT)

config = '''import json, time, hashlib, subprocess, sys
from pathlib import Path
import numpy as np
import torch
from pointpillars.model import PointPillars
''' + (ROOT/'colab/drive_transport.py').read_text(encoding='utf-8') + '''
from google.colab import drive
drive.mount('/content/drive')
ROOT = Path('/content/drive/MyDrive/M49/PASTE_JOB_ID')
request = load_drive_job(ROOT, 'detection_3d')
assert request['classes'] == ['car'], 'Pipeline này dùng lớp car của KITTI'
model_spec = request['model']
assert model_spec.get('pipeline') == 'pointpillars_kitti', 'Sai pipeline 3D'
assert set(request['inputs']) == set(request['manifest']), 'Thiếu calibration theo mẫu'
CHECKPOINT = REPO/'pretrained/epoch_160.pth'
assert hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest() == 'CHECKSUM_VALUE', 'Checkpoint không đúng bản đã khóa'
CONFIDENCE = model_spec['confidence']
model = PointPillars(nclasses=3).cuda()
model.load_state_dict(torch.load(CHECKPOINT,map_location='cpu',weights_only=True))
model.score_thr = min(0.1,CONFIDENCE)
model.eval()
''' .replace('CHECKSUM_VALUE',CHECKSUM) + '\n' + (ROOT/'backend/app/adapters/pointpillars.py').read_text(encoding='utf-8')

inference = '''def stamp():
    torch.cuda.synchronize()
    return time.perf_counter()

samples, per_sample = [], []
for name in request['manifest']:
    # File I/O and network/model setup are outside the measured inference interval.
    points = np.fromfile(ROOT/'assets'/name,dtype='<f4')
    if not points.size or points.size % 4:
        raise ValueError('LiDAR phải là BIN x,y,z,intensity không rỗng')
    points = points.reshape(-1,4)
    if not np.isfinite(points).all():
        raise ValueError('LiDAR chứa NaN/Inf')
    started = stamp()
    lower = np.array([0,-39.68,-3],dtype=np.float32)
    upper = np.array([69.12,39.68,1],dtype=np.float32)
    points = points[((points[:,:3] > lower) & (points[:,:3] < upper)).all(axis=1)]
    if not len(points):
        raise ValueError('Không có điểm trong phạm vi PointPillars; không xuất dự đoán giả')
    with torch.inference_mode():
        result = model(batched_pts=[torch.from_numpy(points).cuda()],mode='test')[0]
    # Upstream returns [] if no anchor passes its score threshold.
    objects = [] if isinstance(result,list) and not result else pointpillars_objects(result,CONFIDENCE,request['inputs'][name])
    seconds = stamp()-started
    samples.append(dict(asset_name=name,objects=objects))
    per_sample.append(dict(asset_name=name,inference_seconds=seconds))
    print(name,len(objects),'cars',round(seconds,3),'s')
INFERENCE_SECONDS = sum(row['inference_seconds'] for row in per_sample)
'''

export = '''bundle = dict(schema_version='1.0',task='detection_3d',name='PointPillars KITTI',
    run=dict(model='PointPillars (zhulf0804)',checkpoint='epoch_160.pth sha256:CHECKSUM_VALUE',
             gpu=torch.cuda.get_device_name(0),library_version='PointPillars COMMIT_VALUE; torch '+torch.__version__,
             inference_seconds=INFERENCE_SECONDS),samples=samples)
timing = dict(inference_seconds=INFERENCE_SECONDS,per_sample=per_sample,
              includes='point range filter, CPU-GPU transfer, model, NMS, conversion/FOV filter; excludes download, installation, file IO')
environment = subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
publish_drive_result(ROOT,request,bundle,timing,environment)
print('Đã gửi kết quả 3D. Quay lại M49 để sửa nhãn AI.')
'''.replace('CHECKSUM_VALUE',CHECKSUM).replace('COMMIT_VALUE',COMMIT)

notebook = dict(nbformat=4,nbformat_minor=5,metadata=dict(accelerator='GPU',kernelspec=dict(display_name='Python 3',language='python',name='python3')),
    cells=[cell('markdown','''# M49 · PointPillars KITTI LiDAR
Chọn GPU rồi Run all. Lần đầu biên dịch CUDA có thể mất vài phút.
Model/checkpoint: https://github.com/zhulf0804/PointPillars
Chỉ nhận point cloud và calibration, không đọc ground truth hoặc Manual.
Đánh giá car với tâm hộp trong FOV camera và vùng x [0,69.12), y [-39.68,39.68).
Đây là pilot M49, không phải KITTI AP hoặc phép đánh giá model trên tập giữ riêng.
Pipeline CUDA/PyTorch cần được kiểm chứng trong runtime Colab thực tế.
'''),cell('code',install),cell('code',config),cell('code',inference),cell('code',export)])
(ROOT/'colab/detection_3d.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
