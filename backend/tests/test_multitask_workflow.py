import copy
import struct

import pytest

from test_api import client, project, upload_image, import_json


@pytest.mark.parametrize('task', ['instance_segmentation', 'detection_3d'])
def test_assisted_draft_revision_finalize_and_score(client, task):
    pid = project(client, task)
    if task == 'detection_3d':
        name = 'cloud.bin'
        asset = client.post(f'/api/projects/{pid}/assets', files={'file': (name, struct.pack('<4f', 1, 2, 3, 1))}).json()['id']
        geometry = dict(kind='cuboid3d', center=[0,0,0], size_lwh=[4,2,2], yaw=0.3, frame='lidar')
    else:
        name = 'demo.png'
        asset = upload_image(client, pid).json()['id']
        geometry = dict(kind='polygon', points=[[10,10],[40,10],[40,40],[10,40]])
    bundle = dict(task=task, name='AI original', samples=[dict(asset_name=name, objects=[
        dict(id='1', category='car', confidence=0.9, geometry=geometry)])])
    truth = import_json(client, pid, 'ground_truth', bundle).json()['id']
    ai = import_json(client, pid, 'ai', bundle).json()['id']
    exp = client.post(f'/api/projects/{pid}/experiments', json=dict(name='Flow', ground_truth_id=truth, asset_ids=[asset])).json()['id']
    row = client.post(f'/api/experiments/{exp}/assignments', json=dict(asset_id=asset, annotator='Tester', mode='assisted', parent_id=ai)).json()
    assignment = row['id']
    editor = client.get(f'/api/assignments/{assignment}/editor').json()
    assert editor['objects'] == bundle['samples'][0]['objects']
    row = client.post(f'/api/assignments/{assignment}/events', json=dict(revision=row['revision'], kind='resume')).json()
    objects = copy.deepcopy(editor['objects'])
    if task == 'detection_3d': objects[0]['geometry']['center'][0] += 0.1
    else: objects[0]['geometry']['points'][0][0] += 1
    revision = row['revision']
    saved = client.post(f'/api/assignments/{assignment}/draft', json=dict(revision=revision, objects=objects))
    assert saved.status_code == 200, saved.text
    row = saved.json()
    assert client.post(f'/api/assignments/{assignment}/draft', json=dict(revision=revision, objects=[])).status_code == 409
    assert client.get(f'/api/assignments/{assignment}/editor').json()['objects'] == objects
    finalized = client.post(f'/api/assignments/{assignment}/finalize', json=dict(revision=row['revision']))
    assert finalized.status_code == 200
    assert client.post(f'/api/assignments/{assignment}/draft', json=dict(revision=finalized.json()['revision'], objects=[])).status_code == 409
    assert client.get(f'/api/label-sets/{ai}').json()['samples'][0]['objects'] == bundle['samples'][0]['objects']
    report = client.get(f'/api/experiments/{exp}/score')
    assert report.status_code == 200, report.text
    human = next(r for r in report.json()['rows'] if r['source'] == 'assisted')
    assert human['completed'] and human['metrics']['tp'] == 1
    assert 0.5 < human['metrics']['mean_iou'] < 1
    assert client.get(f'/api/experiments/{exp}/results.csv').status_code == 200
