import copy
import hashlib
import json
import math
from pathlib import Path
import struct

import pytest
from PIL import Image

from app import guided, colab_sync, colab_google
from app.adapters.datasets import segmentation_objects
from app.adapters.pointpillars import pointpillars_geometry, pointpillars_objects, in_evaluation_scope
from app.colab_sync import ModelChoice, model_config
from app.schemas import LabelBundle
from test_api import client
from test_datasets_sync import db_session
from test_colab_google import connected, fake_drive


def prepared_task(tmp_path, monkeypatch, task):
    root=tmp_path/'multitask'
    monkeypatch.setattr(guided,'DATA_ROOT',root)
    names=[]
    for i in range(10):
        stem=f'{i:06}'
        if task=='instance_segmentation':
            folder=root/'segmentation'
            (folder/'assets').mkdir(parents=True,exist_ok=True)
            (folder/'source_annotations').mkdir(exist_ok=True)
            name=stem+'.png'
            Image.new('RGB',(100,80)).save(folder/'assets'/name)
            record=dict(size=dict(width=100,height=80),objects=[dict(id=1,classTitle='car',geometryType='polygon',points=dict(exterior=[[10,10],[40,10],[40,40],[10,40]],interior=[]))])
            (folder/'source_annotations'/(name+'.json')).write_text(json.dumps(record))
        else:
            folder=root/'kitti/training'
            for sub in ['image_2','velodyne','calib','label_2']:
                (folder/sub).mkdir(parents=True,exist_ok=True)
            name=stem+'.bin'
            Image.new('RGB',(100,80)).save(folder/'image_2'/(stem+'.png'))
            (folder/'velodyne'/name).write_bytes(struct.pack('<4f',10,0,0,0.5))
            (folder/'calib'/(stem+'.txt')).write_text('R0_rect: 1 0 0 0 1 0 0 0 1\nTr_velo_to_cam: 0 -1 0 0 0 0 -1 0 1 0 0 0\nP2: 100 0 50 0 0 100 40 0 0 0 1 0\n')
            (folder/'label_2'/(stem+'.txt')).write_text('Car 0 0 0 10 10 40 40 2 2 4 0 1 10 0\n')
        names.append(name)
    manifest='segmentation' if task=='instance_segmentation' else 'kitti_3d'
    (root/(manifest+'_manifest.json')).write_text(json.dumps(names))


@pytest.mark.parametrize('task',['instance_segmentation','detection_3d'])
def test_full_new_task_google_workflow(client,tmp_path,monkeypatch,task):
    prepared_task(tmp_path,monkeypatch,task)
    catalog=client.get('/api/guided/catalog').json()
    assert next(r for r in catalog if r['task']==task)['available']
    result=client.post('/api/guided',json=dict(task=task,annotator='Tester'))
    assert result.status_code==201,result.text
    run=result.json();key=run['id'];pid=run['project']['id']
    exp=client.get(f'/api/projects/{pid}/experiments').json()[0]
    truth=client.get(f"/api/label-sets/{exp['ground_truth_id']}").json()
    objects={s['asset_name']:s['objects'] for s in truth['samples']}
    assert len(objects)==10
    expected_kind='polygon' if task=='instance_segmentation' else 'cuboid3d'
    assert all(len(row)==1 and row[0]['geometry']['kind']==expected_kind for row in objects.values())
    def finish(run):
        editor=client.get(f"/api/assignments/{run['assignment_id']}/editor").json()
        assert 'ground_truth' not in editor
        row=editor['assignment'];name=editor['asset']['name']
        row=client.post(f"/api/assignments/{row['id']}/events",json=dict(revision=row['revision'],kind='resume')).json()
        saved=client.post(f"/api/assignments/{row['id']}/draft",json=dict(revision=row['revision'],objects=objects[name]))
        assert saved.status_code==200,saved.text
        response=client.post(f"/api/assignments/{row['id']}/finalize",json=dict(revision=saved.json()['revision']))
        assert response.status_code==200,response.text
        return client.post(f'/api/guided/{key}/next',json={}).json()
    for _ in range(10):run=finish(run)
    connected();remote,_=fake_drive(monkeypatch)
    response=client.post(f'/api/guided/{key}/ai/google',json={})
    assert response.status_code==200,response.text
    run=response.json()
    folder=colab_google.private_dir()/'jobs'/run['job_id']
    request=json.loads((folder/'request.json').read_text())
    assert request['task']==task and 'ground_truth' not in request
    if task=='detection_3d':
        assert request['model']['pipeline']=='pointpillars_kitti'
        assert set(request['inputs'])==set(objects)
        assert all(set(v)=={'R0_rect','Tr_velo_to_cam','P2','image_shape'} for v in request['inputs'].values())
    else:
        assert request['model']['checkpoint']=='yolo11s-seg.pt'
    for session in db_session():monkeypatch.setattr(colab_sync,'engine',session.get_bind())
    colab_sync.sync_once()
    refreshed=client.get(f'/api/guided/{key}').json()
    assert refreshed['colab_url'],refreshed['error']
    state=json.loads((folder/'google.json').read_text());ids=state['ids']
    notebook=json.loads(remote[ids['notebook']][1])
    for cell in notebook['cells']:
        source=''.join(cell['source'])
        if cell['cell_type']=='code' and not source.startswith('%'):
            compile(source,'generated.ipynb','exec')
    payload=dict(task=task,name='fixture AI',run=dict(model='fixture',inference_seconds=1),samples=copy.deepcopy(truth['samples']))
    for sample in payload['samples']:
        for obj in sample['objects']:obj['confidence']=0.9
    raw=json.dumps(payload).encode()
    remote[ids['output:predictions.json']]=('predictions.json',raw)
    remote[ids['output:result.ready.json']]=('result.ready.json',json.dumps(dict(job_id=run['job_id'],sha256=hashlib.sha256(raw).hexdigest())).encode())
    colab_sync.sync_once();colab_sync.sync_once()
    run=client.post(f'/api/guided/{key}/next',json={}).json()
    assert run['phase']=='assisted'
    for _ in range(10):run=finish(run)
    assert run['phase']=='results'
    report=client.get(f"/api/experiments/{run['experiment_id']}/score")
    assert report.status_code==200,report.text
    assert {s['source'] for s in report.json()['summary']}=={'manual','ai','assisted'}
    assert all(s['f1']==1 for s in report.json()['summary'])


def test_segmentation_does_not_invent_masks_or_remove_holes():
    record=dict(size=dict(width=100,height=100),objects=[dict(id=1,classTitle='car',geometryType='polygon',points=dict(exterior=[[0,0],[5,0],[10,0],[10,10],[0,10],[0,0]],interior=[]))])
    result=segmentation_objects(record,['car'])
    assert result[0]['geometry']['points']==[[0.,0.],[10.,0.],[10.,10.],[0.,10.]]
    record['objects'][0]['points']['interior']=[[[1,1],[2,1],[1,2]]]
    with pytest.raises(ValueError,match='lỗ'):
        segmentation_objects(record,['car'])
    record['objects'][0]['geometryType']='rectangle'
    with pytest.raises(ValueError,match='thiếu polygon'):
        segmentation_objects(record,['car'])


@pytest.mark.parametrize('angle',[0,0.3,-math.pi/2,math.pi])
def test_pointpillars_corners_match_m49_convention(angle):
    geometry=pointpillars_geometry([10,2,-1,2,4,2,angle])
    # Compare physical corner sets with upstream's clockwise [width,length,height] convention.
    upstream=[];converted=[]
    yaw=geometry['yaw']
    for x in [-1,1]:
        for y in [-2,2]:
            upstream.append((round(10+x*math.cos(angle)+y*math.sin(angle),6),round(2-x*math.sin(angle)+y*math.cos(angle),6)))
    for x in [-2,2]:
        for y in [-1,1]:
            converted.append((round(10+x*math.cos(yaw)-y*math.sin(yaw),6),round(2+x*math.sin(yaw)+y*math.cos(yaw),6)))
    assert set(upstream)==set(converted)
    assert geometry['center']==[10,2,0]
    LabelBundle(task='detection_3d',name='converted',samples=[dict(asset_name='cloud.bin',objects=[dict(id='1',category='car',geometry=geometry)])])


def test_pointpillars_filters_classes_confidence_and_scope(tmp_path):
    from fastapi import HTTPException
    camera=dict(Tr_velo_to_cam=[[0,-1,0,0],[0,0,-1,0],[1,0,0,0]],R0_rect=[[1,0,0],[0,1,0],[0,0,1]],P2=[[100,0,50,0],[0,100,40,0],[0,0,1,0]],image_shape=[80,100])
    result=dict(lidar_bboxes=[[10,0,-1,2,4,2,0],[10,0,-1,2,4,2,0],[10,0,-1,2,4,2,0],[10,30,-1,2,4,2,0]],labels=[2,0,2,2],scores=[0.9,0.9,0.1,0.9])
    objects=pointpillars_objects(result,0.25,camera)
    assert len(objects)==1 and objects[0]['category']=='car'
    assert in_evaluation_scope(objects[0]['geometry'],camera)
    with pytest.raises(HTTPException):model_config(ModelChoice(preset='yolo11s'),'detection_3d',tmp_path)
    with pytest.raises(HTTPException):model_config(ModelChoice(preset='pointpillars'),'detection_2d',tmp_path)
