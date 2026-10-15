import csv
from datetime import timezone
from io import StringIO
from typing import Literal
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .db import get_session
from .evaluation.metrics import counts, score_sample
from .models import AnnotationEvent, Asset, Assignment, Experiment, LabelSet, Project, now
from .schemas import LabelBundle, ObjectLabel, StrictModel

router = APIRouter(prefix='/api')
SCORE_LOCK = Lock()  # Demo: run exactly one backend worker.
TIMER_LEASE_SECONDS = 30
MAX_DEMO_ASSETS = 20


class ExperimentCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    ground_truth_id: str
    asset_ids: list[str] = Field(min_length=1, max_length=MAX_DEMO_ASSETS)
    iou_threshold: float = Field(default=0.5, gt=0, le=1)


class AssignmentCreate(StrictModel):
    asset_id: str
    annotator: str = Field(min_length=1, max_length=120)
    mode: Literal['manual', 'assisted']
    parent_id: str | None = None


class DraftSave(StrictModel):
    revision: int = Field(ge=0)
    objects: list[ObjectLabel] = Field(max_length=300)


class Revision(StrictModel):
    revision: int = Field(ge=0)


class TimerEvent(Revision):
    kind: Literal['resume', 'pause', 'heartbeat']


def require(session, model, key):
    row = session.get(model, key)
    if row is None:
        raise HTTPException(404, 'Không tìm thấy dữ liệu')
    return row


def sample_of(label, name):
    return next((s for s in label.payload['samples'] if s['asset_name'] == name), None)


def elapsed(row):
    if row.running_since is None:
        return row.active_seconds
    start = row.running_since.replace(tzinfo=timezone.utc) if row.running_since.tzinfo is None else row.running_since
    return row.active_seconds + min(TIMER_LEASE_SECONDS, max(0, (now()-start).total_seconds()))


def timer_running(row):
    if row.running_since is None:
        return False
    start = row.running_since.replace(tzinfo=timezone.utc) if row.running_since.tzinfo is None else row.running_since
    return (now()-start).total_seconds() < TIMER_LEASE_SECONDS


def public_assignment(row):
    remaining = 0
    if row.running_since is not None:
        start = row.running_since.replace(tzinfo=timezone.utc) if row.running_since.tzinfo is None else row.running_since
        remaining = max(0, TIMER_LEASE_SECONDS-max(0, (now()-start).total_seconds()))
    return {**row.model_dump(exclude={'running_since'}), 'active_seconds': elapsed(row),
            'running': remaining > 0, 'timer_remaining_seconds': remaining}


def claim(session, assignment_id, revision):
    # Compare-and-swap prevents stale tabs from overwriting/finalizing a draft.
    result = session.execute(update(Assignment).where(Assignment.id == assignment_id,
        Assignment.revision == revision, Assignment.final_id.is_(None)).values(revision=revision+1),
        execution_options={'synchronize_session': False})
    if result.rowcount != 1:
        session.rollback()
        raise HTTPException(409, 'Nhiệm vụ đã chốt hoặc đã thay đổi ở cửa sổ khác. Tải lại nhiệm vụ.')
    session.expire_all()
    return require(session, Assignment, assignment_id)


def log(session, row, kind):
    session.add(AnnotationEvent(assignment_id=row.id, kind=kind, revision=row.revision))


@router.get('/projects/{project_id}/experiments')
def experiments(project_id: str, session: Session = Depends(get_session)):
    require(session, Project, project_id)
    return session.exec(select(Experiment).where(Experiment.project_id == project_id)).all()


@router.post('/projects/{project_id}/experiments', status_code=201)
def create_experiment(project_id: str, body: ExperimentCreate, session: Session = Depends(get_session)):
    require(session, Project, project_id)
    truth = require(session, LabelSet, body.ground_truth_id)
    if truth.project_id != project_id or truth.source != 'ground_truth':
        raise HTTPException(422, 'Cần ground truth của cùng dự án')
    if not body.name.strip() or len(body.asset_ids) != len(set(body.asset_ids)):
        raise HTTPException(422, 'Tên rỗng hoặc danh sách mẫu bị trùng')
    for key in body.asset_ids:
        asset = require(session, Asset, key)
        if asset.project_id != project_id or sample_of(truth, asset.name) is None:
            raise HTTPException(422, 'Mỗi mẫu phải thuộc dự án và có ground truth, kể cả objects rỗng')
    row = Experiment(project_id=project_id, **body.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get('/experiments/{experiment_id}/assignments')
def assignments(experiment_id: str, session: Session = Depends(get_session)):
    require(session, Experiment, experiment_id)
    return [public_assignment(a) for a in session.exec(select(Assignment).where(Assignment.experiment_id == experiment_id)).all()]


@router.post('/experiments/{experiment_id}/assignments', status_code=201)
def create_assignment(experiment_id: str, body: AssignmentCreate, session: Session = Depends(get_session)):
    exp = require(session, Experiment, experiment_id)
    if body.asset_id not in exp.asset_ids or not body.annotator.strip():
        raise HTTPException(422, 'Mẫu ngoài thử nghiệm hoặc thiếu tên người thực hiện')
    asset = require(session, Asset, body.asset_id)
    if body.mode == 'assisted':
        parent = require(session, LabelSet, body.parent_id) if body.parent_id else None
        if not parent or parent.project_id != exp.project_id or parent.source != 'ai' or sample_of(parent, asset.name) is None:
            raise HTTPException(422, 'Cần bản AI cùng dự án có kết quả cho mẫu này')
    elif body.parent_id is not None:
        raise HTTPException(422, 'Manual không có parent_id')
    row = Assignment(experiment_id=experiment_id, **{**body.model_dump(), 'annotator': body.annotator.strip()})
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, 'Người này đã có nhiệm vụ cho cùng mẫu và chế độ trong thử nghiệm')
    session.refresh(row)
    return public_assignment(row)


@router.get('/assignments/{assignment_id}/editor')
def editor(assignment_id: str, session: Session = Depends(get_session)):
    row = require(session, Assignment, assignment_id)
    asset = require(session, Asset, row.asset_id)
    label_id = row.final_id or row.draft_id or row.parent_id
    objects = []
    if label_id:
        label = require(session, LabelSet, label_id)
        if label.source == 'ground_truth':
            raise HTTPException(409, 'Nguồn nhãn không hợp lệ cho editor')
        sample = sample_of(label, asset.name)
        objects = sample['objects'] if sample is not None else []
    return dict(assignment=public_assignment(row), objects=objects,
                asset={**asset.model_dump(exclude={'storage_name'}), 'url': f'/api/assets/{asset.id}/file'})


@router.post('/assignments/{assignment_id}/draft')
def save_draft(assignment_id: str, body: DraftSave, session: Session = Depends(get_session)):
    from .main import save_bundle
    row = claim(session, assignment_id, body.revision)
    exp = require(session, Experiment, row.experiment_id)
    asset = require(session, Asset, row.asset_id)
    project = require(session, Project, exp.project_id)
    bundle = LabelBundle(task=project.task, name=f'{row.mode} · {asset.name}'[:120],
        annotator=row.annotator, parent_id=row.parent_id,
        samples=[dict(asset_name=asset.name, objects=body.objects, active_seconds=elapsed(row))])
    saved = save_bundle(exp.project_id, row.mode, bundle, session, commit=False)
    row.draft_id = saved['id']
    log(session, row, 'save')
    session.add(row)
    session.commit()
    session.refresh(row)
    return public_assignment(row)


@router.post('/assignments/{assignment_id}/finalize')
def finalize(assignment_id: str, body: Revision, session: Session = Depends(get_session)):
    row = claim(session, assignment_id, body.revision)
    if not row.draft_id:
        raise HTTPException(422, 'Lưu bản nháp trước khi chốt, kể cả mẫu không có đối tượng')
    row.active_seconds, row.running_since = elapsed(row), None
    row.final_id = row.draft_id
    log(session, row, 'finalize')
    session.add(row)
    session.commit()
    session.refresh(row)
    return public_assignment(row)


@router.post('/assignments/{assignment_id}/events')
def timer(assignment_id: str, body: TimerEvent, session: Session = Depends(get_session)):
    row = claim(session, assignment_id, body.revision)
    if body.kind == 'pause':
        row.active_seconds, row.running_since = elapsed(row), None
    else:
        was_running = timer_running(row)
        row.active_seconds = elapsed(row)
        row.running_since = now() if body.kind == 'resume' or was_running else None
    if body.kind != 'heartbeat':
        log(session, row, body.kind)
    session.add(row)
    session.commit()
    session.refresh(row)
    return public_assignment(row)


@router.get('/assignments/{assignment_id}/events')
def events(assignment_id: str, session: Session = Depends(get_session)):
    require(session, Assignment, assignment_id)
    return session.exec(select(AnnotationEvent).where(AnnotationEvent.assignment_id == assignment_id)
                        .order_by(AnnotationEvent.revision)).all()


def experiment_scores(exp, session):
    if len(exp.asset_ids) > MAX_DEMO_ASSETS:
        raise ValueError('Demo chỉ chấm tối đa 20 mẫu/thử nghiệm. Tạo thử nghiệm nhỏ hơn.')
    truth = require(session, LabelSet, exp.ground_truth_id)
    project = require(session, Project, exp.project_id)
    assets = {key: require(session, Asset, key) for key in exp.asset_ids}
    rows = []
    assignments = session.exec(select(Assignment).where(Assignment.experiment_id == exp.id).limit(41)).all()
    imported_ids = set(session.exec(select(AnnotationEvent.assignment_id).where(
        AnnotationEvent.assignment_id.in_([a.id for a in assignments]),
        AnnotationEvent.kind == 'cvat_import_declared_time')).all())
    cvat_sample_ids = set(session.exec(select(AnnotationEvent.assignment_id).where(
        AnnotationEvent.assignment_id.in_([a.id for a in assignments]),
        AnnotationEvent.kind == 'cvat_import_declared_sample_time')).all())
    ai_ids = session.exec(select(LabelSet.id).where(LabelSet.project_id == exp.project_id, LabelSet.source == 'ai').limit(4)).all()
    if len(assignments) > 40 or len(ai_ids) > 3:
        raise ValueError('Demo giới hạn 40 nhiệm vụ và 3 bản AI/dự án. Dùng dự án demo riêng.')
    for row in assignments:
        label = require(session, LabelSet, row.final_id) if row.final_id else None
        asset = assets[row.asset_id]
        sample = sample_of(label, asset.name) if label else None
        rows.append(dict(assignment_id=row.id, label_set_id=row.final_id, asset_name=asset.name,
            source=row.mode, annotator=row.annotator, active_seconds=elapsed(row), completed=sample is not None,
            time_source='declared_cvat_sample' if row.id in cvat_sample_ids else
                'declared_total_uniformly_distributed' if row.id in imported_ids else 'server_timer',
            metrics=score_sample(sample['objects'], sample_of(truth, asset.name)['objects'], project.classes,
                exp.iou_threshold, (asset.width, asset.height) if asset.width else None) if sample else None))
    for label_id in ai_ids:
        label = require(session, LabelSet, label_id)
        for asset in assets.values():
            sample = sample_of(label, asset.name)
            rows.append(dict(assignment_id=None, label_set_id=label.id, asset_name=asset.name,
                source='ai', annotator=label.name, active_seconds=None, completed=sample is not None, time_source=None,
                metrics=score_sample(sample['objects'], sample_of(truth, asset.name)['objects'], project.classes,
                    exp.iou_threshold, (asset.width, asset.height) if asset.width else None) if sample else None))
    groups = {}
    for row in rows:
        key = (row['source'], row['annotator'], row['label_set_id'] if row['source'] == 'ai' else None)
        groups.setdefault(key, []).append(row)
    summary = []
    for (source, annotator, run_id), group in groups.items():
        completed = [r for r in group if r['completed']]
        metrics = [r['metrics'] for r in completed]
        total = counts(sum(m['tp'] for m in metrics), sum(m['fp'] for m in metrics),
                       sum(m['fn'] for m in metrics), sum((m['mean_iou'] or 0)*m['tp'] for m in metrics))
        summary.append(dict(source=source, annotator=annotator, run_id=run_id, assigned=len(group),
            expected=len(assets), completed=len(completed),
            completion_rate=len(completed)/len(assets), **total))
    return dict(experiment_id=exp.id, task=project.task, ground_truth_id=exp.ground_truth_id,
        iou_threshold=exp.iou_threshold, missing_policy='exclude_from_metrics_report_completion', rows=rows, summary=summary,
        time_comparison=compare_times(rows, len(assets)),
        ai_runs=[dict(id=key, name=require(session, LabelSet, key).name,
                      **require(session, LabelSet, key).payload.get('run', {})) for key in ai_ids])


def compare_times(rows, expected):
    comparisons = []
    people = sorted({r['annotator'] for r in rows if r['source'] in ('manual', 'assisted')})
    for person in people:
        modes = {mode: {r['asset_name']: r for r in rows if r['source'] == mode and
                 r['annotator'] == person and r['completed']} for mode in ('manual', 'assisted')}
        names = sorted(modes['manual'].keys() & modes['assisted'].keys())
        pairs = [(modes['manual'][n], modes['assisted'][n]) for n in names]
        manual = sum(m['active_seconds'] for m, _ in pairs)
        assisted = sum(a['active_seconds'] for _, a in pairs)
        measured = bool(pairs) and all(m['active_seconds'] > 0 and a['active_seconds'] > 0 and
            m['time_source'] == a['time_source'] == 'server_timer' for m, a in pairs)
        quality = all(m['metrics']['f1'] is not None and a['metrics']['f1'] is not None and
                      a['metrics']['f1'] >= m['metrics']['f1'] for m, a in pairs) if pairs else False
        complete = len(pairs) == expected
        comparisons.append(dict(annotator=person, paired=len(pairs), expected=expected,
            manual_seconds=manual, assisted_seconds=assisted,
            saved_seconds=manual-assisted if measured else None,
            speedup=manual/assisted if measured else None,
            reduction=1-assisted/manual if measured else None,
            quality_not_lower=quality, status='incomplete' if not complete else 'unmeasured' if not measured else
            'passed' if assisted < manual and quality else 'not_met'))
    return comparisons


@router.get('/experiments/{experiment_id}/score')
def score(experiment_id: str, session: Session = Depends(get_session)):
    if not SCORE_LOCK.acquire(blocking=False):
        raise HTTPException(429, 'Đang chấm một yêu cầu khác. Chờ hoàn tất rồi thử lại.')
    try:
        return experiment_scores(require(session, Experiment, experiment_id), session)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    finally:
        SCORE_LOCK.release()


@router.get('/experiments/{experiment_id}/results.csv')
def export_csv(experiment_id: str, session: Session = Depends(get_session)):
    report = score(experiment_id, session)
    output = StringIO()
    fields = ['experiment_id', 'task', 'ground_truth_id', 'iou_threshold', 'missing_policy',
              'source', 'annotator', 'label_set_id', 'assignment_id', 'asset_name', 'completed',
              'active_seconds', 'time_source', 'tp', 'fp', 'fn', 'precision', 'recall', 'f1', 'mean_iou',
              'paired_samples', 'manual_paired_seconds', 'assisted_paired_seconds', 'saved_seconds', 'speedup', 'time_goal']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in report['rows']:
        values = {**report, **row, **(row['metrics'] or {})}
        comparison = next((c for c in report['time_comparison'] if c['annotator'] == row['annotator']), None) if row['source'] != 'ai' else None
        if comparison:
            values.update(paired_samples=comparison['paired'], manual_paired_seconds=comparison['manual_seconds'],
                assisted_paired_seconds=comparison['assisted_seconds'], saved_seconds=comparison['saved_seconds'],
                speedup=comparison['speedup'], time_goal=comparison['status'])
        values = {key: values.get(key) for key in fields}
        # Prevent spreadsheet formula evaluation of user-provided names.
        values = {k: ("'"+v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
                  for k, v in values.items()}
        writer.writerow(values)
    return Response('\ufeff'+output.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="m49-{experiment_id}.csv"'})
