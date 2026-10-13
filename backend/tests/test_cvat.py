import json
import zipfile
from io import BytesIO

import pytest

from test_api import client, project, upload_image, bundle, import_json


def archive(data):
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('annotations/instances_default.json', json.dumps(data))
    return stream.getvalue()


def coco():
    return dict(images=[dict(id=1, file_name='images/demo.png', width=100, height=80)],
        categories=[dict(id=1, name='car')],
        annotations=[dict(id=1, image_id=1, category_id=1, bbox=[1, 2, 49, 58], iscrowd=0)])


def setup(c):
    pid = project(c)
    asset = upload_image(c, pid).json()
    gt = import_json(c, pid, 'ground_truth', bundle()).json()['id']
    ai = import_json(c, pid, 'ai', bundle()).json()['id']
    response = c.post(f'/api/projects/{pid}/experiments', json=dict(name='CVAT', ground_truth_id=gt, asset_ids=[asset['id']]))
    assert response.status_code == 201
    return pid, response.json()['id'], ai


def submit(c, exp, data=None, **fields):
    return c.post(f'/api/experiments/{exp}/cvat/import',
        files={'file': ('cvat.zip', archive(coco() if data is None else data), 'application/zip')},
        data=dict(mode='manual', annotator='Tester', total_seconds='20', **fields))


def test_roundtrip_and_scoring(client):
    pid, exp, ai = setup(client)
    images = client.get(f'/api/experiments/{exp}/cvat/images.zip')
    assert images.status_code == 200
    with zipfile.ZipFile(BytesIO(images.content)) as z:
        assert set(z.namelist()) == {'images/demo.png', 'classes.txt', 'cvat_raw_labels.json'}
        assert json.loads(z.read('cvat_raw_labels.json'))[0]['name'] == 'car'
    prelabels = client.get(f'/api/experiments/{exp}/cvat/prelabels/{ai}.zip')
    assert prelabels.status_code == 200
    with zipfile.ZipFile(BytesIO(prelabels.content)) as z:
        data = json.loads(z.read('annotations/instances_default.json'))
    assert data['images'][0]['width'] == 100
    assert data['annotations'][0]['bbox'] == [1, 2, 49, 58]
    assert submit(client, exp, data).status_code == 201
    response = client.post(f'/api/experiments/{exp}/cvat/import',
        files={'file': ('cvat.zip', prelabels.content)},
        data=dict(mode='assisted', annotator='Tester', total_seconds='10', parent_id=ai))
    assert response.status_code == 201
    assignments = client.get(f'/api/experiments/{exp}/assignments').json()
    assert len(assignments) == 2 and all(a['final_id'] for a in assignments)
    report = client.get(f'/api/experiments/{exp}/score')
    assert report.status_code == 200, report.text
    assert all(r['metrics']['tp'] == 1 for r in report.json()['rows'])
    assert report.json()['time_comparison'][0]['speedup'] is None
    assert report.json()['time_comparison'][0]['status'] == 'unmeasured'
    assert all(r['time_source'] == 'declared_total_uniformly_distributed' for r in report.json()['rows'] if r['source'] != 'ai')
    csv = client.get(f'/api/experiments/{exp}/results.csv')
    assert csv.status_code == 200 and 'declared_total_uniformly_distributed' in csv.text
    assert submit(client, exp).status_code == 409
    assert len(client.get(f'/api/experiments/{exp}/assignments').json()) == 2


@pytest.mark.parametrize('fault', ['class', 'bounds', 'dimensions', 'duplicate', 'missing', 'crowd', 'reference', 'nan', 'wrong_type'])
def test_invalid_coco_is_atomic(client, fault):
    pid, exp, _ = setup(client)
    data = coco()
    if fault == 'class': data['categories'][0]['name'] = 'bus'
    if fault == 'bounds': data['annotations'][0]['bbox'][2] = 101
    if fault == 'dimensions': data['images'][0]['width'] = 1280
    if fault == 'duplicate': data['images'].append(data['images'][0])
    if fault == 'missing': data['images'] = []
    if fault == 'crowd': data['annotations'][0]['iscrowd'] = 1
    if fault == 'reference': data['annotations'][0]['image_id'] = 20
    if fault == 'nan': data['annotations'][0]['bbox'][0] = float('nan')
    if fault == 'wrong_type': data['annotations'][0]['category_id'] = []
    assert submit(client, exp, data).status_code == 422
    assert client.get(f'/api/experiments/{exp}/assignments').json() == []
    assert len(client.get(f'/api/projects/{pid}/label-sets').json()) == 2


def test_empty_annotations_are_valid_and_wrong_parent_rejected(client):
    _, exp, _ = setup(client)
    _, _, foreign_ai = setup(client)
    response = client.post(f'/api/experiments/{exp}/cvat/import', files={'file': ('x.zip', archive(coco()))},
        data=dict(mode='assisted', annotator='Tester', total_seconds='1', parent_id=foreign_ai))
    assert response.status_code == 422
    data = coco(); data['annotations'] = []
    assert submit(client, exp, data).status_code == 201
    assert client.get(f'/api/experiments/{exp}/score').json()['rows'][0]['metrics']['fn'] == 1


def test_malformed_zip_and_declared_limits(client, monkeypatch):
    from app.adapters import cvat
    _, exp, _ = setup(client)
    response = client.post(f'/api/experiments/{exp}/cvat/import', files={'file': ('x.zip', b'bad')},
        data=dict(mode='manual', annotator='Tester', total_seconds='1'))
    assert response.status_code == 422
    monkeypatch.setattr(cvat, 'MAX_JSON_BYTES', 10)
    assert submit(client, exp).status_code == 422
    for seconds in ['nan', 'inf', '-1', '0']:
        response = client.post(f'/api/experiments/{exp}/cvat/import', files={'file': ('x.zip', archive(coco()))},
            data=dict(mode='manual', annotator='Tester', total_seconds=seconds))
        assert response.status_code == 422


def test_multi_image_import_keeps_every_sample(client):
    from PIL import Image
    pid = project(client)
    first = upload_image(client, pid).json()['id']
    image = BytesIO(); Image.new('RGB', (100, 80)).save(image, format='PNG')
    second = client.post(f'/api/projects/{pid}/assets', files={'file': ('second.png', image.getvalue())}).json()['id']
    truth = bundle()
    truth['samples'].append(dict(asset_name='second.png', objects=[]))
    gt = import_json(client, pid, 'ground_truth', truth).json()['id']
    exp = client.post(f'/api/projects/{pid}/experiments', json=dict(name='Two images', ground_truth_id=gt, asset_ids=[first, second])).json()['id']
    assert submit(client, exp).status_code == 422  # Missing image is not an empty annotation.
    data = coco(); data['images'].append(dict(id=2, file_name='second.png', width=100, height=80))
    assert submit(client, exp, data).status_code == 201
    report = client.get(f'/api/experiments/{exp}/score').json()
    assert len(report['rows']) == 2
    assert {r['asset_name'] for r in report['rows']} == {'demo.png', 'second.png'}
    assert sum(r['active_seconds'] for r in report['rows']) == 20
    assert report['summary'][0]['tp'] == 1


def segmentation_setup(c):
    pid = project(c, 'instance_segmentation')
    asset = upload_image(c, pid).json()['id']
    data = dict(task='instance_segmentation', name='Polygon AI', samples=[dict(asset_name='demo.png', objects=[
        dict(id='poly', category='car', confidence=0.9, geometry=dict(kind='polygon', points=[[10,10],[30,10],[30,30],[10,30]]))])])
    gt = import_json(c, pid, 'ground_truth', data).json()['id']
    ai = import_json(c, pid, 'ai', data).json()['id']
    exp = c.post(f'/api/projects/{pid}/experiments', json=dict(name='Segmentation', ground_truth_id=gt, asset_ids=[asset])).json()['id']
    return pid, exp, ai


def test_segmentation_coco_roundtrip(client):
    _, exp, ai = segmentation_setup(client)
    with zipfile.ZipFile(BytesIO(client.get(f'/api/experiments/{exp}/cvat/images.zip').content)) as z:
        assert json.loads(z.read('cvat_raw_labels.json'))[0]['type'] == 'polygon'
    response = client.get(f'/api/experiments/{exp}/cvat/prelabels/{ai}.zip')
    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content)) as z:
        data = json.loads(z.read('annotations/instances_default.json'))
    assert data['annotations'][0]['segmentation'] == [[10,10,30,10,30,30,10,30]]
    assert data['annotations'][0]['area'] == 400
    data['annotations'][0]['segmentation'][0] += [10,10]  # Accept repeated closing vertex.
    result = client.post(f'/api/experiments/{exp}/cvat/import', files={'file': ('seg.zip', archive(data))},
        data=dict(mode='assisted', annotator='Tester', total_seconds='10', parent_id=ai))
    assert result.status_code == 201, result.text
    report = client.get(f'/api/experiments/{exp}/score').json()
    human = next(row for row in report['rows'] if row['source'] == 'assisted')
    assert human['metrics']['pairs'][0]['dice'] == 1
    assert human['metrics']['mean_iou'] == 1
    original = client.get(f'/api/label-sets/{ai}').json()
    assert len(original['samples'][0]['objects'][0]['geometry']['points']) == 4


@pytest.mark.parametrize('polygon', [None, {'counts': [10,20], 'size': [80,100]},
    [[10,10,30,10,30,30],[40,40,50,40,50,50]], [[1,2,3]],
    [[10,10,30,30,10,30,30,10]], [[10,10,200,10,30,30]], [[0,0,float('nan'),0,10,10]]])
def test_invalid_segmentation_is_not_replaced_by_box(client, polygon):
    pid, exp, _ = segmentation_setup(client)
    data = coco(); data['annotations'][0]['segmentation'] = polygon
    assert submit(client, exp, data).status_code == 422
    assert client.get(f'/api/experiments/{exp}/assignments').json() == []
    assert len(client.get(f'/api/projects/{pid}/label-sets').json()) == 2
