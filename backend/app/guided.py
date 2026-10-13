"""One experiment: ten manual assignments, independent AI, ten assisted, results."""
import os
from pathlib import Path
from threading import Lock
import json
import random
import copy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlmodel import Session, select

from .db import get_session
from .models import Asset, Assignment, ColabJob, Experiment, GuidedRun, Project
from .schemas import StrictModel, Task
from .datasets import import_prepared
from .adapters.datasets import prepare, camera_input
from .adapters.pointpillars import in_evaluation_scope
from .schemas import LabelBundle
from .colab_sync import ModelChoice, JobCreate, export_job
from .colab_google import job_info

router = APIRouter(prefix='/api/guided')
RUN_LOCK = Lock()
DATA_ROOT = Path(os.getenv('M49_TEST20_DIR', str(Path(__file__).resolve().parents[2]/'data/test20')))


def candidate_pool(task='detection_2d'):
    candidates = []
    sources = [
        ('bdd100k', 'bdd100k', DATA_ROOT/'bdd100k/assets', str(DATA_ROOT/'bdd100k/labels.json'), ['car']),
        ('kitti', 'kitti_2d', DATA_ROOT/'kitti/training', '', ['Car']),
    ] if task == 'detection_2d' else [
        ('bdd100k_seg', 'bdd100k_segmentation', DATA_ROOT/'segmentation', '', ['car'])
    ] if task == 'instance_segmentation' else [
        ('kitti', 'kitti_3d', DATA_ROOT/'kitti/training', '', ['Car'])
    ]
    for source, key, root, labels, classes in sources:
        manifest = DATA_ROOT/f"{'segmentation' if task == 'instance_segmentation' else key}_manifest.json"
        if not manifest.is_file():
            continue
        names = json.loads(manifest.read_text(encoding='utf-8'))
        _, files, samples, _ = prepare(key, str(root), labels, classes, names, 20)
        LabelBundle(task=task, name='Candidate validation', samples=samples)
        for path, sample in zip(files, samples, strict=True):
            sample = copy.deepcopy(sample)
            sample['asset_name'] = source+'__'+sample['asset_name']
            for obj in sample['objects']:
                obj['category'] = 'car'
            if task == 'detection_3d':
                camera = camera_input(root,path.name)
                sample['objects'] = [o for o in sample['objects'] if in_evaluation_scope(o['geometry'],camera)]
            candidates.append((path, sample))
    return candidates


@router.get('/catalog')
def catalog():
    rows = []
    for task, model in [('detection_2d','YOLO11'),('instance_segmentation','YOLO11-seg'),('detection_3d','PointPillars · cần GPU Colab')]:
        try:
            count = len(candidate_pool(task))
            reason = f'Chọn 10 trong {count} mẫu có nhãn chuẩn · {model}' if count >= 10 else f'Cần ít nhất 10 mẫu có nhãn chuẩn; hiện có {count}'
        except (ValueError,OSError,KeyError,TypeError) as exc:
            count, reason = 0, f'Không đọc được bộ mẫu: {exc}'
        rows.append(dict(task=task,available=count>=10,reason=reason))
    return rows


class Start(StrictModel):
    task: Task
    annotator: str = Field(min_length=1,max_length=120)


def require_run(key, session):
    run = session.get(GuidedRun,key)
    if run is None:
        raise HTTPException(404,'Không tìm thấy lượt thử')
    return run


def state(run, session):
    exp = session.get(Experiment,run.experiment_id)
    rows = session.exec(select(Assignment).where(Assignment.experiment_id==exp.id, Assignment.annotator==run.annotator)).all()
    manual = sum(r.mode=='manual' and bool(r.final_id) for r in rows)
    assisted = sum(r.mode=='assisted' and bool(r.final_id) for r in rows)
    job = session.get(ColabJob,run.job_id) if run.job_id else None
    phase = 'manual' if manual<10 else 'results' if assisted==10 else 'assisted' if job and job.label_set_id else 'ai'
    mode = 'manual' if phase=='manual' else 'assisted'
    remaining = {r.asset_id:r for r in rows if r.mode==mode and not r.final_id}
    next_row = next((remaining[key] for key in exp.asset_ids if key in remaining),None) if phase in ['manual','assisted'] else None
    return dict(id=run.id, dataset=run.dataset, project=session.get(Project,exp.project_id), experiment_id=exp.id,
                annotator=run.annotator,phase=phase,manual_completed=manual,assisted_completed=assisted,total=10,
                assignment_id=next_row.id if next_row else None,job_id=run.job_id,
                job_status=job.status if job else None,error=job.error if job else None,
                **(job_info(job) if job else dict(colab_url=None, transport=None)))


@router.get('')
def runs(session: Session=Depends(get_session)):
    return [state(r,session) for r in session.exec(select(GuidedRun).order_by(GuidedRun.created_at.desc())).all()]


@router.post('',status_code=201)
def start(body: Start,session: Session=Depends(get_session)):
    if not body.annotator.strip():
        raise HTTPException(422,'Cần tên người thực hiện')
    try:
        pool = candidate_pool(body.task)
        if len(pool) < 10:
            raise ValueError('Cần ít nhất 10 mẫu có ground truth')
        chosen = random.SystemRandom().sample(pool, 10)
        files, samples = map(list, zip(*chosen))
        inputs = {sample['asset_name']:camera_input(path.parent.parent,path.name) for path,sample in chosen} if body.task == 'detection_3d' else None
        imported = import_prepared('10 mẫu ngẫu nhiên', body.task, ['car'], files, samples, [], session)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    project = imported['project']
    if inputs is not None:
        from .main import STORAGE
        (STORAGE/f'{project.id}-inputs.json').write_text(json.dumps(inputs),encoding='utf-8')
    assets = session.exec(select(Asset).where(Asset.project_id==project.id)).all()
    by_name = {a.name:a.id for a in assets}
    exp = Experiment(project_id=project.id,name='Manual → AI → Assisted',ground_truth_id=imported['ground_truth_id'],asset_ids=[by_name[n] for n in imported['manifest']])
    session.add(exp); session.flush()
    run = GuidedRun(experiment_id=exp.id,dataset='random',annotator=body.annotator.strip())
    session.add(run)
    for asset_id in exp.asset_ids:
        session.add(Assignment(experiment_id=exp.id,asset_id=asset_id,annotator=run.annotator,mode='manual'))
    session.commit(); session.refresh(run)
    return state(run,session)


@router.get('/{key}')
def status(key: str,session: Session=Depends(get_session)):
    return state(require_run(key,session),session)


@router.post('/{key}/ai')
def launch_ai(key: str,body: ModelChoice,session: Session=Depends(get_session)):
    return launch(key, body, session)


@router.post('/{key}/ai/google')
def launch_google_ai(key: str,body: ModelChoice,session: Session=Depends(get_session)):
    try:
        return launch(key, body, session, google=True)
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc


def launch(key, body, session, google=False):
    with RUN_LOCK:
        run = require_run(key,session)
        current = state(run,session)
        if current['manual_completed'] != 10:
            raise HTTPException(409,'Chốt đủ 10 mẫu Manual trước khi chạy AI')
        if run.job_id:
            return current
        exp = session.get(Experiment,run.experiment_id)
        job = export_job(exp.project_id,JobCreate(asset_ids=exp.asset_ids,model=body),session,google=google)
        run.job_id=job['id']; session.add(run); session.commit(); session.refresh(run)
        return state(run,session)


@router.post('/{key}/next')
def next_sample(key: str,session: Session=Depends(get_session)):
    with RUN_LOCK:
        run=require_run(key,session)
        current=state(run,session)
        if current['phase']=='assisted':
            exp=session.get(Experiment,run.experiment_id)
            job=session.get(ColabJob,run.job_id)
            existing={r.asset_id for r in session.exec(select(Assignment).where(Assignment.experiment_id==exp.id,Assignment.mode=='assisted')).all()}
            for asset_id in exp.asset_ids:
                if asset_id not in existing:
                    session.add(Assignment(experiment_id=exp.id,asset_id=asset_id,annotator=run.annotator,mode='assisted',parent_id=job.label_set_id))
            session.commit(); session.refresh(run)
        return state(run,session)
