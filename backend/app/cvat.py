import json
import zipfile
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .adapters.cvat import coco_export, parse_coco
from .benchmark import require, sample_of
from .db import get_session
from .models import AnnotationEvent, Asset, Assignment, Experiment, LabelSet, Project

router = APIRouter(prefix='/api/experiments')


def context(experiment_id, session):
    exp = require(session, Experiment, experiment_id)
    project = require(session, Project, exp.project_id)
    if project.task not in {'detection_2d', 'instance_segmentation'}:
        raise HTTPException(422, 'Trao đổi CVAT COCO hỗ trợ box 2D và polygon segmentation; không hỗ trợ 3D.')
    assets = [require(session, Asset, key) for key in exp.asset_ids]
    return exp, project, assets


def ai_samples(parent_id, project_id, assets, session):
    parent = require(session, LabelSet, parent_id)
    if parent.project_id != project_id or parent.source != 'ai':
        raise HTTPException(422, 'Chọn bản AI của cùng dự án.')
    samples = {a.name: sample_of(parent, a.name) for a in assets}
    if any(s is None for s in samples.values()):
        raise HTTPException(422, 'Bản AI phải có đủ ảnh của thử nghiệm.')
    return samples


def zip_response(data, filename):
    return Response(data, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.get('/{experiment_id}/cvat/images.zip')
def export_images(experiment_id: str, session: Session = Depends(get_session)):
    from .main import STORAGE
    exp, project, assets = context(experiment_id, session)
    if sum(a.size_bytes for a in assets) > 256 * 1024 * 1024:
        raise HTTPException(413, 'Gói ảnh tối đa 256 MiB; tạo thử nghiệm nhỏ hơn.')
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for asset in assets:
            path = STORAGE / asset.storage_name
            if not path.is_file():
                raise HTTPException(404, f'Thiếu tệp ảnh: {asset.name}')
            archive.write(path, arcname='images/' + asset.name)
        archive.writestr('classes.txt', '\n'.join(project.classes) + '\n')
        shape = 'polygon' if project.task == 'instance_segmentation' else 'rectangle'
        archive.writestr('cvat_raw_labels.json', json.dumps([dict(name=c, type=shape, attributes=[]) for c in project.classes], ensure_ascii=False))
    return zip_response(output.getvalue(), f'cvat-images-{exp.id}.zip')


@router.get('/{experiment_id}/cvat/prelabels/{parent_id}.zip')
def export_prelabels(experiment_id: str, parent_id: str, session: Session = Depends(get_session)):
    exp, project, assets = context(experiment_id, session)
    samples = ai_samples(parent_id, project.id, assets, session)
    return zip_response(coco_export(assets, project.classes, samples), f'cvat-ai-{parent_id}.zip')


@router.post('/{experiment_id}/cvat/import', status_code=201)
async def import_annotations(experiment_id: str, file: UploadFile = File(...),
        mode: Literal['manual', 'assisted'] = Form(...), annotator: str = Form(..., min_length=1, max_length=120),
        total_seconds: float = Form(..., gt=0, allow_inf_nan=False), parent_id: str | None = Form(None),
        session: Session = Depends(get_session)):
    from .main import read_limited, save_bundle
    exp, project, assets = context(experiment_id, session)
    annotator = annotator.strip()
    if not annotator:
        raise HTTPException(422, 'Cần tên người gán nhãn.')
    if mode == 'assisted':
        if not parent_id:
            raise HTTPException(422, 'Assisted cần bản AI gốc.')
        ai_samples(parent_id, project.id, assets, session)
    elif parent_id:
        raise HTTPException(422, 'Manual không có bản AI gốc.')
    data = await read_limited(file)
    try:
        bundle = parse_coco(data, {a.name: a for a in assets}, annotator=annotator, parent_id=parent_id, task=project.task)
    except (ValueError, OSError, EOFError) as exc:
        raise HTTPException(422, str(exc))
    existing = session.exec(select(Assignment).where(Assignment.experiment_id == exp.id,
        Assignment.annotator == annotator, Assignment.mode == mode)).first()
    if existing:
        raise HTTPException(409, 'Đã có nhiệm vụ cho người/chế độ này; tạo thử nghiệm khác để nhập lại, tránh ghi đè.')
    # Imported time is a declared total, distributed uniformly; never a server measurement.
    for sample in bundle.samples:
        sample.active_seconds = total_seconds / len(bundle.samples)
    try:
        saved = save_bundle(project.id, mode, bundle, session, commit=False)
        for asset in assets:
            row = Assignment(experiment_id=exp.id, asset_id=asset.id, annotator=annotator, mode=mode,
                parent_id=parent_id, draft_id=saved['id'], final_id=saved['id'], revision=1,
                active_seconds=total_seconds / len(assets))
            session.add(row)
            session.flush()
            session.add(AnnotationEvent(assignment_id=row.id, kind='cvat_import_declared_time', revision=1))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, 'Nhiệm vụ đã tồn tại; không ghi đè dữ liệu.')
    except Exception:
        session.rollback()
        raise
    return dict(**saved, assignments=len(assets), time_source='declared_total_uniformly_distributed')
