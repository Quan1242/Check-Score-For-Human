import copy
from io import BytesIO

from PIL import Image

import pytest

from app import cvat_local
from test_api import client, project, upload_image, import_json, bundle


def assignment(client, task='detection_2d', mode='manual'):
    pid = project(client, task)
    asset = upload_image(client, pid).json()['id']
    data = bundle()
    data['task'] = task
    if task == 'instance_segmentation':
        data['samples'][0]['objects'][0]['geometry'] = dict(kind='polygon', points=[[1,2],[50,2],[50,60],[1,60]])
    truth = import_json(client, pid, 'ground_truth', data).json()['id']
    ai = import_json(client, pid, 'ai', data).json()['id'] if mode == 'assisted' else None
    exp = client.post(f'/api/projects/{pid}/experiments', json=dict(
        name='CVAT', ground_truth_id=truth, asset_ids=[asset])).json()['id']
    row = client.post(f'/api/experiments/{exp}/assignments', json=dict(
        asset_id=asset, annotator='Tester', mode=mode, parent_id=ai)).json()
    return row['id'], exp, ai


def fake_cvat(monkeypatch):
    calls, annotations = [], {'version': 0, 'tags': [], 'tracks': [], 'shapes': []}
    progress = ['finished']
    def remote(config, method, path, value=None, **kwargs):
        calls.append((method, path, copy.deepcopy(value), kwargs))
        if path == 'users/self':
            return {'id': 7}
        if path == 'tasks' and method == 'POST':
            return {'id': 123}
        if path == 'tasks/123/data/':
            assert b'name="client_files[0]"; filename="demo.png"' in kwargs['body']
            return {'rq_id': 'create:task-123'}
        if path.startswith('requests/'):
            return {'status': progress[0]}
        if path == 'tasks/123':
            return {'id': 123, 'size': int(any(p == 'tasks/123/data/' for _, p, _, _ in calls))}
        if path == 'tasks/123/data/meta':
            return dict(size=1, frames=[dict(name='demo.png', width=100, height=80)], deleted_frames=[])
        if path.startswith('labels?'):
            return {'results': [{'id': 9, 'name': 'car'}]}
        if path == 'tasks/123/annotations':
            if method == 'PUT':
                annotations.update(copy.deepcopy(value))
                for i, shape in enumerate(annotations['shapes']):
                    shape['id'] = i+1
            return copy.deepcopy(annotations)
        raise AssertionError((method, path))
    monkeypatch.setattr(cvat_local, 'remote', remote)
    return calls, annotations, progress


def connect(client):
    response = client.post('/api/cvat/connection', json=dict(url='http://localhost:8080/', token='private-token'))
    assert response.status_code == 200, response.text
    assert response.json() == dict(configured=True, url='http://localhost:8080')
    assert 'private-token' not in response.text


@pytest.mark.parametrize('task', ['detection_2d', 'instance_segmentation'])
@pytest.mark.parametrize('mode', ['manual', 'assisted'])
def test_real_cvat_protocol_roundtrip(client, monkeypatch, task, mode):
    calls, annotations, progress = fake_cvat(monkeypatch)
    connect(client)
    key, exp, ai = assignment(client, task, mode)
    original = client.get(f'/api/label-sets/{ai}').json() if ai else None
    progress[0] = 'queued'
    assert client.post(f'/api/cvat/assignments/{key}/open').json()['ready'] is False
    progress[0] = 'finished'
    response = client.post(f'/api/cvat/assignments/{key}/open')
    assert response.status_code == 200, response.text
    assert response.json()['url'] == 'http://localhost:8080/tasks/123'
    assert len(annotations['shapes']) == (1 if ai else 0)
    annotations['shapes'] = [dict(id=1, frame=0, label_id=9, type='rectangle' if task == 'detection_2d' else 'polygon',
        points=[1,2,50,60] if task == 'detection_2d' else [1,2,50,2,50,60,1,60])]
    assert client.post(f'/api/cvat/assignments/{key}/open').status_code == 200
    assert sum(method == 'POST' and path == 'tasks' for method, path, _, _ in calls) == 1
    assert sum(method == 'PUT' for method, _, _, _ in calls) == 1
    response = client.post(f'/api/cvat/assignments/{key}/import', json={'total_seconds': 12})
    assert response.status_code == 200, response.text
    assert response.json()['final_id']
    report = client.get(f'/api/experiments/{exp}/score').json()
    row = next(r for r in report['rows'] if r['source'] == mode)
    assert row['metrics']['f1'] == 1
    assert row['time_source'] == 'declared_cvat_sample'
    assert report['time_comparison'][0]['speedup'] is None
    assert client.post(f'/api/cvat/assignments/{key}/import', json={'total_seconds':12}).status_code == 409
    if ai:
        assert client.get(f'/api/label-sets/{ai}').json() == original


def test_cvat_rejects_stale_local_draft(client, monkeypatch):
    fake_cvat(monkeypatch)
    connect(client)
    key, _, _ = assignment(client)
    assert client.post(f'/api/cvat/assignments/{key}/open').status_code == 200
    revision = client.get(f'/api/assignments/{key}/editor').json()['assignment']['revision']
    assert client.post(f'/api/assignments/{key}/draft', json={'revision':revision,'objects':[]}).status_code == 200
    assert client.post(f'/api/cvat/assignments/{key}/import', json={'total_seconds':12}).status_code == 409


@pytest.mark.parametrize('fault', ['rotation', 'frame', 'type', 'unknown_label', 'tracks', 'outside', 'bounds'])
def test_cvat_rejects_incompatible_labels(client, monkeypatch, fault):
    _, annotations, _ = fake_cvat(monkeypatch)
    connect(client)
    key, _, _ = assignment(client)
    assert client.post(f'/api/cvat/assignments/{key}/open').status_code == 200
    shape = dict(id=1, frame=0, label_id=9, type='rectangle', points=[1,2,50,60])
    if fault == 'rotation': shape['rotation'] = 30
    if fault == 'frame': shape['frame'] = 1
    if fault == 'type': shape['type'] = 'mask'
    if fault == 'unknown_label': shape['label_id'] = 22
    if fault == 'outside': shape['outside'] = True
    if fault == 'bounds': shape['points'][2] = 101
    if fault == 'tracks': annotations['tracks'] = [shape]
    annotations['shapes'] = [shape]
    assert client.post(f'/api/cvat/assignments/{key}/import', json={'total_seconds':12}).status_code == 422
    assert client.get(f'/api/assignments/{key}/editor').json()['assignment']['final_id'] is None


def test_connection_local_only_and_cross_origin(client):
    for url in ['http://example.com', 'http://localhost:8080/path', 'http://user:password@localhost', 'file:///tmp']:
        assert client.post('/api/cvat/connection', json={'url':url, 'token':'secret'}).status_code == 422
    assert client.post('/api/cvat/connection', json={'token':'secret'},
        headers={'Origin':'https://other.invalid'}).status_code == 403


def batch_assignments(client, task='detection_2d', mode='manual'):
    pid = project(client, task)
    assets, samples = [], []
    for i in range(10):
        name = f'image-{i:02}.png'
        stream = BytesIO()
        Image.new('RGB', (100, 80), (i * 20, 80, 120)).save(stream, format='PNG')
        response = client.post(f'/api/projects/{pid}/assets', files={'file': (name, stream.getvalue(), 'image/png')})
        assert response.status_code == 201, response.text
        assets.append(response.json()['id'])
        sample = copy.deepcopy(bundle()['samples'][0])
        sample['asset_name'] = name
        sample['objects'][0]['geometry'] = (dict(kind='bbox2d', xyxy=[i, 2, 50, 60]) if task == 'detection_2d'
            else dict(kind='polygon', points=[[i, 2], [50, 2], [50, 60], [i, 60]]))
        samples.append(sample)
    payload = dict(task=task, name='Batch', samples=samples)
    truth = import_json(client, pid, 'ground_truth', payload).json()['id']
    ai = import_json(client, pid, 'ai', payload).json()['id'] if mode == 'assisted' else None
    exp = client.post(f'/api/projects/{pid}/experiments', json=dict(name='Batch', ground_truth_id=truth, asset_ids=assets)).json()['id']
    keys = [client.post(f'/api/experiments/{exp}/assignments', json=dict(asset_id=a, annotator='Batch tester', mode=mode, parent_id=ai)).json()['id'] for a in assets]
    return keys, exp


def fake_batch(monkeypatch):
    calls, annotations, progress = fake_cvat(monkeypatch)
    original = cvat_local.remote
    # Reverse the order to verify that we use CVAT metadata, not upload order.
    names = [f'image-{i:02}.png' for i in reversed(range(10))]
    uploaded = []
    def remote(config, method, path, value=None, **kwargs):
        if path == 'tasks/123/data/':
            calls.append((method, path, value, kwargs))
            for i in range(10):
                assert f'name="client_files[{i}]"'.encode() in kwargs['body']
                assert f'filename="image-{i:02}.png"'.encode() in kwargs['body']
            uploaded.append(True)
            return {'rq_id': 'batch'}
        if path == 'tasks/123':
            return dict(id=123, size=10 if uploaded else 0)
        if path == 'tasks/123/data/meta':
            return dict(size=10, frames=[dict(name=n, width=100, height=80) for n in names], deleted_frames=[])
        return original(config, method, path, value, **kwargs)
    monkeypatch.setattr(cvat_local, 'remote', remote)
    return calls, annotations, names


@pytest.mark.parametrize('task', ['detection_2d', 'instance_segmentation'])
@pytest.mark.parametrize('mode', ['manual', 'assisted'])
def test_ten_images_one_task_roundtrip(client, monkeypatch, task, mode):
    calls, annotations, names = fake_batch(monkeypatch)
    connect(client)
    keys, exp = batch_assignments(client, task, mode)
    opened = client.post(f'/api/cvat/assignments/{keys[0]}/open')
    assert opened.status_code == 200, opened.text
    assert len(opened.json()['samples']) == 10
    assert len(annotations['shapes']) == (10 if mode == 'assisted' else 0)
    if mode == 'assisted':
        for shape in annotations['shapes']:
            assert shape['points'][0] == int(names[shape['frame']][6:8])
    for key in keys:
        assert client.post(f'/api/cvat/assignments/{key}/open').json()['task_id'] == 123
    assert sum(method == 'POST' and path == 'tasks' for method, path, _, _ in calls) == 1
    assert sum(method == 'PUT' for method, _, _, _ in calls) == 1
    annotations['shapes'] = [dict(id=frame+1, frame=frame, label_id=9,
        type='rectangle' if task == 'detection_2d' else 'polygon',
        points=[9-frame, 2, 50, 60] if task == 'detection_2d' else [9-frame, 2, 50, 2, 50, 60, 9-frame, 60]) for frame in range(10)]
    response = client.post(f'/api/cvat/assignments/{keys[0]}/import-batch', json={
        'samples': {k: {'total_seconds': i+1} for i, k in enumerate(keys)}})
    assert response.status_code == 200, response.text
    assert len(response.json()['assignments']) == 10
    for i, key in enumerate(keys):
        data = client.get(f'/api/assignments/{key}/editor').json()
        assert data['assignment']['final_id']
        assert data['assignment']['active_seconds'] == i+1
        geom = data['objects'][0]['geometry']
        assert (geom['xyxy'][0] if task == 'detection_2d' else geom['points'][0][0]) == i
    report = client.get(f'/api/experiments/{exp}/score').json()
    assert all(row['metrics']['f1'] == 1 for row in report['rows'] if row['source'] == mode)


@pytest.mark.parametrize('fault', ['stale', 'bounds', 'missing_time', 'wrong_image'])
def test_batch_failure_does_not_finalize_any_image(client, monkeypatch, fault):
    _, annotations, names = fake_batch(monkeypatch)
    connect(client)
    keys, _ = batch_assignments(client)
    assert client.post(f'/api/cvat/assignments/{keys[0]}/open').status_code == 200
    last = sorted(keys)[-1]
    if fault == 'stale':
        rev = client.get(f'/api/assignments/{last}/editor').json()['assignment']['revision']
        assert client.post(f'/api/assignments/{last}/draft', json=dict(revision=rev, objects=[])).status_code == 200
    if fault == 'bounds':
        annotations['shapes'] = [dict(id=1, frame=9-keys.index(last), label_id=9, type='rectangle', points=[1, 2, 101, 60])]
    if fault == 'wrong_image':
        names[0] = 'different.png'
    times = {k: {'total_seconds': 2} for k in keys}
    if fault == 'missing_time':
        del times[last]
    response = client.post(f'/api/cvat/assignments/{keys[0]}/import-batch', json={'samples': times})
    assert response.status_code in (409, 422), response.text
    assert all(client.get(f'/api/assignments/{k}/editor').json()['assignment']['final_id'] is None for k in keys)


def test_batch_can_finish_remaining_images_after_individual_import(client, monkeypatch):
    fake_batch(monkeypatch)
    connect(client)
    keys, _ = batch_assignments(client)
    assert client.post(f'/api/cvat/assignments/{keys[0]}/open').status_code == 200
    assert client.post(f'/api/cvat/assignments/{keys[0]}/import', json={'total_seconds': 3}).status_code == 200
    opened = client.post(f'/api/cvat/assignments/{keys[1]}/open').json()
    assert sum(s['finalized'] for s in opened['samples']) == 1
    response = client.post(f'/api/cvat/assignments/{keys[1]}/import-batch', json={
        'samples': {k: {'total_seconds': 4} for k in keys[1:]}})
    assert response.status_code == 200, response.text
    assert len(response.json()['assignments']) == 9


def test_legacy_single_image_binding_remains_usable(client, monkeypatch):
    fake_cvat(monkeypatch)
    connect(client)
    key, _, _ = assignment(client)
    assert client.post(f'/api/cvat/assignments/{key}/open').status_code == 200
    path, state = cvat_local.binding(key, cvat_local.settings())
    member = state.pop('members')[0]
    state.update(revision=member['revision'], objects=member['objects'])
    cvat_local.write_json(cvat_local.folder()/(key+'.json'), state)
    response = client.post(f'/api/cvat/assignments/{key}/open')
    assert response.status_code == 200, response.text
    assert len(response.json()['samples']) == 1
    response = client.post(f'/api/cvat/assignments/{key}/import-batch', json={
        'samples': {key: {'total_seconds': 3}}})
    assert response.status_code == 200, response.text
