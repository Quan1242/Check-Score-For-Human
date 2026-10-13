from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from pydantic import Field
from sqlmodel import Session
from typing import Literal

from .adapters.datasets import prepare
from .db import get_session
from .models import Asset, Project
from .schemas import LabelBundle, ProjectCreate, StrictModel

router = APIRouter(prefix='/api/datasets')


class DatasetImport(StrictModel):
    dataset: Literal['bdd100k', 'bdd100k_segmentation', 'kitti_2d', 'kitti_3d']
    name: str = Field(min_length=1, max_length=120)
    root: str = Field(min_length=1)
    labels_path: str = ''
    classes: list[str] = Field(min_length=1)
    names: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=5, ge=1, le=20)


@router.post('/import', status_code=201)
def import_dataset(body: DatasetImport, session: Session = Depends(get_session)):
    try:
        classes = [c.strip() for c in body.classes]
        task, files, samples, warnings = prepare(body.dataset, body.root, body.labels_path, classes, body.names, body.limit)
        return import_prepared(body.name, task, classes, files, samples, warnings, session)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise HTTPException(422, f'Không nhập được dataset: {exc}') from exc


def import_prepared(name, task, classes, files, samples, warnings, session):
    from .main import STORAGE, MAX_FILE_BYTES, save_bundle
    written = []
    try:
        spec = ProjectCreate(name=name, task=task, classes=classes)
        bundle = LabelBundle(task=task, name=f'{name} ground truth'[:120], samples=samples)
        project = Project(**spec.model_dump())
        session.add(project)
        session.flush()
        total = 0
        for path, sample in zip(files, bundle.samples, strict=True):
            size = path.stat().st_size
            total += size
            if not 0 < size <= MAX_FILE_BYTES or total > 256*1024*1024:
                raise ValueError('Tối đa 32 MiB/tệp và 256 MiB/lượt nhập')
            width = height = None
            kind = 'pointcloud' if task == 'detection_3d' else 'image'
            with path.open('rb') as stream:
                data = stream.read(MAX_FILE_BYTES+1)
            if len(data) != size:
                raise ValueError('Tệp thay đổi trong khi đọc; thử lại khi đồng bộ xong')
            if kind == 'image':
                with Image.open(path) as img:
                    if img.format not in {'JPEG', 'PNG'}:
                        raise ValueError('Chỉ hỗ trợ ảnh JPEG/PNG')
                    width, height = img.size
                    img.verify()
            elif path.suffix.lower() != '.bin' or size % 16:
                raise ValueError('KITTI LiDAR cần BIN float32 x,y,z,intensity')
            storage_name = str(uuid4())+path.suffix.lower()
            target = STORAGE/storage_name
            written.append(target)
            target.write_bytes(data)
            session.add(Asset(project_id=project.id, name=sample.asset_name, kind=kind, storage_name=storage_name,
                              width=width, height=height, size_bytes=size))
        session.flush()
        result = save_bundle(project.id, 'ground_truth', bundle, session, commit=False)
        session.commit()
        session.refresh(project)
        return dict(project=project, ground_truth_id=result['id'], manifest=[s.asset_name for s in bundle.samples], warnings=warnings)
    except Exception as exc:
        session.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, (ValueError, OSError, KeyError, TypeError)):
            raise HTTPException(422, f'Không nhập được dataset: {exc}') from exc
        raise
