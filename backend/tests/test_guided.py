import hashlib
import json
import pytest
from datetime import timedelta

from PIL import Image

from app import benchmark, colab_sync, guided, main
from app.db import get_session
from test_api import client


def prepare_ten(tmp_path,monkeypatch):
    root=tmp_path/'test20'
    assets=root/'bdd100k/assets'
    assets.mkdir(parents=True)
    names=[f'{i:02}.png' for i in range(10)]
    for name in names:
        Image.new('RGB',(100,80)).save(assets/name)
    (root/'bdd100k/labels.json').write_text(json.dumps([dict(name=name,labels=[dict(id='car',category='car',box2d=dict(x1=10,y1=10,x2=60,y2=60))]) for name in names]))
    (root/'bdd100k_manifest.json').write_text(json.dumps(names))
    monkeypatch.setattr(guided,'DATA_ROOT',root)
    return names


@pytest.mark.parametrize('google_transport', [False, True])
def test_full_closed_loop_manual_ai_assisted_and_resume(client,tmp_path,monkeypatch,google_transport):
    names=prepare_ten(tmp_path,monkeypatch)
    response=client.post('/api/guided',json=dict(task='detection_2d',annotator='Tester'))
    assert response.status_code==201,response.text
    run=response.json(); key=run['id']
    assert run['phase']=='manual' and run['assignment_id']
    assert client.post(f'/api/guided/{key}/ai',json={}).status_code==409
    assert client.post(f'/api/guided/{key}/ai/google',json={}).status_code==409
    clock=[benchmark.now()]
    monkeypatch.setattr(benchmark,'now',lambda:clock[0])
    objects=[dict(id='car',category='car',geometry=dict(kind='bbox2d',xyxy=[10,10,60,60]))]
    def finish(assignment_id,seconds):
        row=client.get(f'/api/assignments/{assignment_id}/editor').json()['assignment']
        row=client.post(f'/api/assignments/{assignment_id}/events',json=dict(revision=row['revision'],kind='resume')).json()
        clock[0]+=timedelta(seconds=seconds)
        row=client.post(f'/api/assignments/{assignment_id}/draft',json=dict(revision=row['revision'],objects=objects)).json()
        response=client.post(f'/api/assignments/{assignment_id}/finalize',json=dict(revision=row['revision']))
        assert response.status_code==200,response.text
    for i in range(10):
        assert run['manual_completed']==i
        finish(run['assignment_id'],10)
        run=client.post(f'/api/guided/{key}/next',json={}).json()
    assert run['phase']=='ai' and run['assignment_id'] is None
    assert client.get('/api/guided').json()[0]['id']==key
    endpoint = f'/api/guided/{key}/ai'
    if google_transport:
        from test_colab_google import connected, fake_drive
        from app import colab_google
        assert client.post(endpoint+'/google',json={}).status_code==422
        connected()
        remote, _ = fake_drive(monkeypatch)
        drive = colab_google.private_dir()/'jobs'
        endpoint += '/google'
    else:
        drive=tmp_path/'Drive';drive.mkdir()
        assert client.post('/api/colab/config',json=dict(root=str(drive))).status_code==200
    run=client.post(endpoint,json=dict(preset='yolo11n',confidence=0.4)).json()
    assert run['job_id']
    assert client.post(endpoint,json={}).json()['job_id']==run['job_id']
    folder=drive/run['job_id']
    request=json.loads((folder/'request.json').read_text())
    assert request['model']['checkpoint']=='yolo11n.pt' and request['model']['confidence']==0.4
    assert set(p.name for p in folder.iterdir())==({'request.json','assets','google.json'} if google_transport else {'request.json','assets'})
    assert set(request['manifest'])=={'bdd100k__'+name for name in names}
    names=request['manifest']
    predictions=dict(task='detection_2d',name='Fixture AI',run=dict(model='fixture',inference_seconds=2),samples=[dict(asset_name=name,objects=[{**objects[0],'confidence':0.9}]) for name in names])
    raw=json.dumps(predictions).encode()
    receipt=json.dumps(dict(job_id=run['job_id'],sha256=hashlib.sha256(raw).hexdigest())).encode()
    for session in main.app.dependency_overrides[get_session]():
        monkeypatch.setattr(colab_sync,'engine',session.get_bind())
    if google_transport:
        colab_sync.sync_once()
        refreshed=client.get(f'/api/guided/{key}').json()
        assert refreshed['colab_url'] and refreshed['job_status']=='awaiting_colab'
        ids=json.loads((folder/'google.json').read_text())['ids']
        remote[ids['output:predictions.json']]=('predictions.json',raw)
        remote[ids['output:result.ready.json']]=('result.ready.json',receipt)
    else:
        (folder/'predictions.json').write_bytes(raw)
        (folder/'result.ready.json').write_bytes(receipt)
    colab_sync.sync_once()
    run=client.post(f'/api/guided/{key}/next',json={}).json()
    assert run['phase']=='assisted'
    for i in range(10):
        assert run['assisted_completed']==i
        editor=client.get(f"/api/assignments/{run['assignment_id']}/editor").json()
        assert editor['objects'][0]['confidence']==0.9
        finish(run['assignment_id'],5)
        run=client.post(f'/api/guided/{key}/next',json={}).json()
    assert run['phase']=='results'
    assert client.get(f'/api/guided/{key}').json()['phase']=='results'
    report=client.get(f"/api/experiments/{run['experiment_id']}/score").json()
    assert {s['source'] for s in report['summary']}=={'manual','ai','assisted'}
    assert len(report['rows'])==30
    assert report['time_comparison'][0]['speedup']==2
    assert report['time_comparison'][0]['paired']==10


def test_unavailable_task_is_rejected_without_creating_project(client,tmp_path,monkeypatch):
    prepare_ten(tmp_path,monkeypatch)
    for task in ['instance_segmentation','detection_3d']:
        response=client.post('/api/guided',json=dict(task=task,annotator='A'))
        assert response.status_code==422
    assert client.get('/api/projects').json()==[]


def test_random_pool_mixes_sources_and_freezes_selection(client,tmp_path,monkeypatch):
    names=prepare_ten(tmp_path,monkeypatch)
    root=guided.DATA_ROOT
    images=root/'kitti/training/image_2'; images.mkdir(parents=True)
    labels=root/'kitti/training/label_2'; labels.mkdir()
    for name in names:
        Image.new('RGB',(100,80)).save(images/name)
        (labels/(name.removesuffix('.png')+'.txt')).write_text('Car 0 0 0 10 10 60 60 2 2 4 0 0 10 0\n')
    (root/'kitti_2d_manifest.json').write_text(json.dumps(names))
    class Sampler:
        calls=0
        def sample(self,pool,count):
            self.calls+=1
            assert len(pool)==20 and count==10
            return pool[::2]
    sampler=Sampler()
    monkeypatch.setattr(guided.random,'SystemRandom',lambda:sampler)
    run=client.post('/api/guided',json=dict(task='detection_2d',annotator='Random')).json()
    pid=run['project']['id']
    assets=client.get(f'/api/projects/{pid}/assets').json()
    selected={a['name'] for a in assets}
    assert len(selected)==10
    assert sum(n.startswith('bdd100k__') for n in selected)==5
    assert sum(n.startswith('kitti__') for n in selected)==5
    assert run['project']['classes']==['car']
    exp=client.get(f'/api/projects/{pid}/experiments').json()[0]
    truth=client.get(f"/api/label-sets/{exp['ground_truth_id']}").json()
    assert {s['asset_name'] for s in truth['samples']}==selected
    assert {o['category'] for s in truth['samples'] for o in s['objects']}=={'car'}
    for _ in range(2):
        resumed=client.post(f"/api/guided/{run['id']}/next",json={}).json()
        assert resumed['assignment_id']==run['assignment_id']
    assert sampler.calls==1


def test_model_upload_and_path_validation(client,tmp_path):
    from app.colab_sync import ModelChoice,model_config
    from fastapi import HTTPException
    import pytest
    drive=tmp_path/'Drive';drive.mkdir()
    client.post('/api/colab/config',json=dict(root=str(drive)))
    assert client.post('/api/colab/checkpoints',files={'file':('model.exe',b'opaque')}).status_code==422
    response=client.post('/api/colab/checkpoints',files={'file':('my-model.pt',b'opaque test checkpoint')})
    assert response.status_code==201
    choice=ModelChoice(preset='custom',checkpoint=response.json()['checkpoint'])
    selected=model_config(choice,'detection_2d',drive)
    assert selected['sha256']==hashlib.sha256(b'opaque test checkpoint').hexdigest()
    assert model_config(ModelChoice(),'instance_segmentation',drive)['checkpoint']=='yolo11s-seg.pt'
    with pytest.raises(HTTPException):
        model_config(ModelChoice(preset='custom',checkpoint='models/../../outside.pt'),'detection_2d',drive)
