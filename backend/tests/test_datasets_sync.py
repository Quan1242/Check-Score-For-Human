import copy
import hashlib
import importlib.util
import json
import math
import struct
from datetime import timedelta
from pathlib import Path

import pytest
from PIL import Image
from sqlmodel import Session, select

from app import benchmark, colab_sync
from app.adapters.datasets import calibration, kitti_objects
from app.db import get_session
from app.models import ColabJob, LabelSet
from test_api import client, project, upload_image, bundle, import_json


def db_session():
    from app.main import app
    return app.dependency_overrides[get_session]()


def dataset_body(tmp_path, dataset='bdd100k'):
    images = tmp_path/'images'
    images.mkdir()
    Image.new('RGB', (100, 80)).save(images/'demo.png')
    labels = tmp_path/'labels.json'
    labels.write_text(json.dumps([dict(name='demo.png', labels=[dict(id=1, category='car', box2d=dict(x1=1, y1=2, x2=50, y2=60))])]))
    return dict(dataset=dataset, name='Real format fixture', root=str(images), labels_path=str(labels), classes=['car'])


def test_bdd_import_and_atomic_validation(client, tmp_path):
    body = dataset_body(tmp_path)
    result = client.post('/api/datasets/import', json=body)
    assert result.status_code == 201, result.text
    assert result.json()['manifest'] == ['demo.png']
    pid = result.json()['project']['id']
    assert client.get(f'/api/projects/{pid}/assets').json()[0]['width'] == 100
    labels = Path(body['labels_path'])
    records = json.loads(labels.read_text())
    records[0]['labels'][0]['box2d']['x2'] = 200
    labels.write_text(json.dumps(records))
    before = set(tmp_path.glob('*.png'))
    assert client.post('/api/datasets/import', json=body).status_code == 422
    assert len(client.get('/api/projects').json()) == 1
    assert set(tmp_path.glob('*.png')) == before
    body['names'] = ['../demo.png']
    assert client.post('/api/datasets/import', json=body).status_code == 422


def test_kitti_calibration_center_yaw_and_import(client, tmp_path):
    for name in ['velodyne', 'calib', 'label_2']:
        (tmp_path/name).mkdir()
    (tmp_path/'velodyne/000000.bin').write_bytes(struct.pack('<4f', 1, 2, 3, 1))
    calib = tmp_path/'calib/000000.txt'
    # camera = [-lidar_y+1, -lidar_z+2, lidar_x+3]
    calib.write_text('R0_rect: 1 0 0 0 1 0 0 0 1\nTr_velo_to_cam: 0 -1 0 1 0 0 -1 2 1 0 0 3\n')
    label = tmp_path/'label_2/000000.txt'
    label.write_text('Car 0 0 0 1 2 50 60 2 2 4 5 3 13 0\nDontCare -1 -1 -10 0 0 1 1 -1 -1 -1 -1000 -1000 -1000 -10\n')
    objects, ignored = kitti_objects(label, ['Car'], calibration(calib))
    assert ignored == 1
    assert objects[0]['geometry']['center'] == pytest.approx([10, -4, 0])
    assert objects[0]['geometry']['yaw'] == pytest.approx(-math.pi/2)
    assert objects[0]['geometry']['size_lwh'] == [4, 2, 2]
    response = client.post('/api/datasets/import', json=dict(dataset='kitti_3d', name='KITTI', root=str(tmp_path), classes=['Car']))
    assert response.status_code == 201, response.text
    assert response.json()['manifest'] == ['000000.bin']
    calib.unlink()
    assert client.post('/api/datasets/import', json=dict(dataset='kitti_3d', name='Missing calib', root=str(tmp_path), classes=['Car'])).status_code == 422


def test_kitti_2d_uses_image_and_selected_classes(client, tmp_path):
    (tmp_path/'image_2').mkdir()
    (tmp_path/'label_2').mkdir()
    Image.new('RGB', (100, 80)).save(tmp_path/'image_2/000001.png')
    (tmp_path/'label_2/000001.txt').write_text('Car 0 0 0 1 2 50 60 2 2 4 5 3 13 0\nPedestrian 0 0 0 3 4 5 6 2 1 1 0 0 10 0\n')
    result = client.post('/api/datasets/import', json=dict(dataset='kitti_2d', name='KITTI 2D', root=str(tmp_path), classes=['Car']))
    assert result.status_code == 201, result.text
    truth = client.get(f"/api/label-sets/{result.json()['ground_truth_id']}").json()
    assert len(truth['samples'][0]['objects']) == 1
    assert truth['samples'][0]['objects'][0]['geometry']['xyxy'] == [1, 2, 50, 60]


def test_kitti_rectification_rotation_is_used(tmp_path):
    phi = 0.2
    c, s = math.cos(phi), math.sin(phi)
    calib = tmp_path/'calib.txt'
    calib.write_text(f'R0_rect: {c} 0 {s} 0 1 0 {-s} 0 {c}\nTr_velo_to_cam: 0 -1 0 0 0 0 -1 0 1 0 0 0\n')
    label = tmp_path/'labels.txt'
    label.write_text(f'Car 0 0 0 1 2 3 4 2 2 4 {10*s} 1 {10*c} 0\n')
    objects, _ = kitti_objects(label, ['Car'], calibration(calib))
    geometry = objects[0]['geometry']
    assert geometry['center'] == pytest.approx([10, 0, 0])
    assert geometry['yaw'] == pytest.approx(phi-math.pi/2)


def drive_job(client, tmp_path):
    pid = project(client)
    asset = upload_image(client, pid).json()['id']
    drive = tmp_path/'drive'
    drive.mkdir()
    assert client.post('/api/colab/config', json={'root': str(drive)}).status_code == 200
    result = client.post(f'/api/projects/{pid}/colab/jobs', json={'asset_ids': [asset]})
    assert result.status_code == 201, result.text
    return pid, result.json()['id'], drive/result.json()['id']


def write_result(folder, job_id, payload):
    raw = json.dumps(payload).encode()
    (folder/'predictions.json').write_bytes(raw)
    (folder/'result.ready.json').write_text(json.dumps(dict(job_id=job_id, sha256=hashlib.sha256(raw).hexdigest())))


def test_sync_checks_manifest_then_imports_once_and_recovers(client, tmp_path, monkeypatch):
    pid, job_id, folder = drive_job(client, tmp_path)
    request = json.loads((folder/'request.json').read_text())
    assert set(request) == {'job_id', 'project_id', 'task', 'classes', 'manifest', 'sha256', 'model'}
    assert list((folder/'assets').iterdir())[0].name == 'demo.png'
    data = bundle()
    data['run'] = dict(model='fixture', inference_seconds=1.25, gpu='fixture CPU')
    bad = copy.deepcopy(data)
    bad['samples'][0]['asset_name'] = 'other.png'
    write_result(folder, job_id, bad)
    for session in db_session():
        monkeypatch.setattr(colab_sync, 'engine', session.get_bind())
    colab_sync.sync_once()
    assert client.get(f'/api/projects/{pid}/colab/jobs').json()[0]['status'] == 'error'
    assert client.get(f'/api/projects/{pid}/label-sets').json() == []
    write_result(folder, job_id, data)
    colab_sync.sync_once()
    colab_sync.sync_once()
    rows = client.get(f'/api/projects/{pid}/label-sets').json()
    assert len(rows) == 1
    assert client.get(f'/api/projects/{pid}/colab/jobs').json()[0]['label_set_id'] == rows[0]['id']
    assert client.get(f"/api/label-sets/{rows[0]['id']}").json()['run']['inference_seconds'] == 1.25


def test_sync_does_not_read_partial_or_forged_timing(client, tmp_path):
    _, job_id, folder = drive_job(client, tmp_path)
    data = bundle()
    data['run'] = dict(model='fixture', inference_seconds=0)
    write_result(folder, job_id, data)
    (folder/'predictions.json').write_text('{}')
    for session in db_session():
        job = session.get(ColabJob, job_id)
        with pytest.raises(ValueError, match='checksum'):
            colab_sync.import_ready(job, session)
        data['samples'][0]['active_seconds'] = 42
        write_result(folder, job_id, data)
        with pytest.raises(ValueError, match='editor'):
            colab_sync.import_ready(job, session)
        assert session.exec(select(LabelSet)).all() == []


def test_notebook_drive_transport_roundtrip_and_checksum(client, tmp_path):
    _, job_id, folder = drive_job(client, tmp_path)
    path = Path(__file__).resolve().parents[2]/'colab/drive_transport.py'
    spec = importlib.util.spec_from_file_location('drive_transport', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    request = module.load_drive_job(folder, 'detection_2d')
    data = bundle()
    data['run'] = dict(model='fixture', inference_seconds=1)
    module.publish_drive_result(folder, request, data, {'per_image': []}, 'test environment')
    for session in db_session():
        colab_sync.import_ready(session.get(ColabJob, job_id), session)
    with pytest.raises(ValueError, match='đã xuất'):
        module.publish_drive_result(folder, request, data, {}, '')
    (folder/'assets/demo.png').write_bytes(b'partial sync')
    with pytest.raises(ValueError, match='đồng bộ'):
        module.load_drive_job(folder, 'detection_2d')


def test_timer_measures_work_pause_and_caps_disconnect(client, monkeypatch):
    pid = project(client)
    asset = upload_image(client, pid).json()['id']
    truth = import_json(client, pid, 'ground_truth', bundle()).json()['id']
    exp = client.post(f'/api/projects/{pid}/experiments', json=dict(name='Timer', ground_truth_id=truth, asset_ids=[asset])).json()['id']
    row = client.post(f'/api/experiments/{exp}/assignments', json=dict(asset_id=asset, annotator='A', mode='manual')).json()
    clock = [benchmark.now()]
    monkeypatch.setattr(benchmark, 'now', lambda: clock[0])
    def event(kind):
        nonlocal row
        response = client.post(f"/api/assignments/{row['id']}/events", json=dict(revision=row['revision'], kind=kind))
        assert response.status_code == 200
        row = response.json()
    event('resume')
    clock[0] += timedelta(seconds=10)
    event('heartbeat')
    clock[0] += timedelta(seconds=7)
    event('pause')
    assert row['active_seconds'] == 17
    clock[0] += timedelta(seconds=100)
    event('resume')
    assert row['active_seconds'] == 17
    clock[0] += timedelta(seconds=100)
    event('heartbeat')
    assert row['active_seconds'] == 47 and not row['running']
    assert client.post(f"/api/assignments/{row['id']}/events", json=dict(revision=row['revision'], kind='resume', active_seconds=999)).status_code == 422
