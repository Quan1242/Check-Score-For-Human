"""Stage Colab jobs and import results from Drive Desktop or Google API transport."""
import hashlib
import json
import logging
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from typing import Literal
from uuid import uuid4
from pydantic import Field
from sqlmodel import Session, select

from .db import engine, get_session
from .models import Asset, ColabJob, LabelSet, Project
from .schemas import LabelBundle, StrictModel

router = APIRouter(prefix='/api')
SYNC_LOCK = Lock()
MAX_CHECKPOINT_BYTES = 512*1024*1024


@router.get('/colab/notebooks/{task}')
def download_notebook(task: Literal['detection_2d','instance_segmentation','detection_3d']):
    path = Path(__file__).resolve().parents[2]/'colab'/f'{task}.ipynb'
    if not path.is_file():
        raise HTTPException(404, 'Notebook chưa được đóng gói trên backend này')
    return FileResponse(path,filename=path.name,media_type='application/x-ipynb+json')


def config_path():
    from .main import STORAGE
    return STORAGE / 'colab-sync.json'


def config():
    path = config_path()
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'root': ''}


class SyncConfig(StrictModel):
    root: str = Field(min_length=1)


class ModelChoice(StrictModel):
    preset: Literal['auto', 'yolo11n', 'yolo11s', 'yolo11m', 'pointpillars', 'custom'] = 'auto'
    checkpoint: str | None = None
    confidence: float = Field(default=0.25, ge=0.01, le=1)


def model_config(choice, task, root):
    if task == 'detection_3d':
        if choice.preset in ('auto','pointpillars') and choice.checkpoint is None:
            return dict(checkpoint='epoch_160.pth', custom=False, pipeline='pointpillars_kitti', confidence=choice.confidence)
        raise HTTPException(422, '3D dùng PointPillars KITTI; không dùng checkpoint YOLO cho LiDAR')
    if choice.preset == 'pointpillars':
        raise HTTPException(422, 'PointPillars chỉ dùng cho LiDAR 3D')
    if choice.preset == 'custom':
        name = choice.checkpoint or ''
        if not name.startswith('models/') or Path(name).suffix != '.pt' or '\\' in name:
            raise HTTPException(422, 'Chọn checkpoint .pt đã tải lên trong ứng dụng')
        path = (root/name).resolve()
        if not path.is_relative_to((root/'models').resolve()) or not path.is_file():
            raise HTTPException(422, 'Không tìm thấy checkpoint đã tải lên')
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        return dict(checkpoint=name, custom=True, sha256=checksum, confidence=choice.confidence)
    if choice.checkpoint is not None:
        raise HTTPException(422, 'Checkpoint riêng chỉ dùng với lựa chọn custom')
    preset = 'yolo11s' if choice.preset == 'auto' else choice.preset
    return dict(checkpoint=preset+('-seg.pt' if task == 'instance_segmentation' else '.pt'), custom=False, confidence=choice.confidence)


@router.post('/colab/checkpoints', status_code=201)
async def upload_checkpoint(file: UploadFile = File(...)):
    value = config()
    root = Path(value['root'])
    if not value['root'] or not root.is_dir():
        raise HTTPException(422, 'Lưu kết nối thư mục Drive trước khi tải checkpoint')
    return await store_checkpoint(file, root)


async def store_checkpoint(file, root):
    if Path(file.filename or '').suffix.lower() != '.pt':
        await file.close()
        raise HTTPException(422, 'Notebook hiện hỗ trợ checkpoint Ultralytics .pt')
    folder = root/'models'
    folder.mkdir(exist_ok=True)
    path = folder/(str(uuid4())+'.pt')
    temporary = path.with_suffix('.tmp')
    size, digest = 0, hashlib.sha256()
    try:
        with temporary.open('xb') as stream:
            while chunk := await file.read(1024*1024):
                size += len(chunk)
                if size > MAX_CHECKPOINT_BYTES:
                    raise HTTPException(413, 'Checkpoint tối đa 512 MiB')
                digest.update(chunk)
                stream.write(chunk)
        if not size:
            raise HTTPException(422, 'Checkpoint rỗng')
        temporary.replace(path)
    finally:
        await file.close()
        temporary.unlink(missing_ok=True)
    return dict(checkpoint='models/'+path.name, sha256=digest.hexdigest(), bytes=size)


class JobCreate(StrictModel):
    asset_ids: list[str] = Field(min_length=1, max_length=20)
    model: ModelChoice = Field(default_factory=ModelChoice)


@router.get('/colab/config')
def get_config():
    value = config()
    return {**value, 'available': bool(value['root']) and Path(value['root']).is_dir()}


@router.post('/colab/config')
def set_config(body: SyncConfig):
    root = Path(body.root).expanduser().resolve()
    if not root.is_dir():
        raise HTTPException(422, 'Chọn thư mục M49 đã tạo trong Google Drive đồng bộ trên máy')
    value = {'root': str(root)}
    path = config_path()
    temporary = path.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(value), encoding='utf-8')
        temporary.replace(path)
    except OSError as exc:
        raise HTTPException(422, f'Không lưu được cấu hình: {exc}') from exc
    return value


def public_job(job):
    return job.model_dump(exclude={'root'})


@router.get('/projects/{project_id}/colab/jobs')
def list_jobs(project_id: str, session: Session = Depends(get_session)):
    return [public_job(j) for j in session.exec(select(ColabJob).where(ColabJob.project_id == project_id)
                                              .order_by(ColabJob.created_at.desc())).all()]


@router.post('/projects/{project_id}/colab/jobs', status_code=201)
def create_job(project_id: str, body: JobCreate, session: Session = Depends(get_session)):
    return export_job(project_id, body, session)


def export_job(project_id, body, session, google=False):
    from .main import STORAGE, MAX_FILE_BYTES
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, 'Không tìm thấy dự án')
    runs = session.exec(select(LabelSet.id).where(LabelSet.project_id == project_id, LabelSet.source == 'ai')).all()
    pending = session.exec(select(ColabJob.id).where(ColabJob.project_id == project_id, ColabJob.status != 'imported')).all()
    if len(runs)+len(pending) >= 3:
        raise HTTPException(422, 'Demo tối đa 3 lượt AI/dự án, kể cả lượt đang chờ. Tạo dự án khác cho thí nghiệm mới.')
    if google:
        from .colab_google import private_dir, credentials
        credentials()
        root = private_dir()/'jobs'
        root.mkdir(exist_ok=True)
        value = {'root': str(root)}
    else:
        value = config()
    root = Path(value['root'])
    if not value['root'] or not root.is_dir():
        raise HTTPException(422, 'Chưa cấu hình thư mục Drive hoặc ổ Drive đang ngắt kết nối')
    model = model_config(body.model, project.task, root)
    if len(body.asset_ids) != len(set(body.asset_ids)):
        raise HTTPException(422, 'Danh sách mẫu bị trùng')
    assets = [session.get(Asset, key) for key in body.asset_ids]
    expected_kind = 'pointcloud' if project.task == 'detection_3d' else 'image'
    if any(a is None or a.project_id != project_id or a.kind != expected_kind for a in assets):
        raise HTTPException(422, 'Mẫu phải cùng dự án và đúng tác vụ')
    if sum(a.size_bytes for a in assets) > 256*1024*1024:
        raise HTTPException(422, 'Gói Colab tối đa 256 MiB')
    job = ColabJob(project_id=project_id, root=str(root), manifest=[a.name for a in assets])
    folder = root/job.id
    written = []
    try:
        (folder/'assets').mkdir(parents=True, exist_ok=False)
        hashes = {}
        for asset in assets:
            if Path(asset.name).name != asset.name or '\\' in asset.name or ':' in asset.name:
                raise ValueError('Tên mẫu không an toàn để xuất')
            with (STORAGE/asset.storage_name).open('rb') as stream:
                raw = stream.read(MAX_FILE_BYTES+1)
            if len(raw) > MAX_FILE_BYTES or len(raw) != asset.size_bytes:
                raise ValueError('Dung lượng mẫu đã thay đổi')
            target = folder/'assets'/asset.name
            written.append(target)
            target.write_bytes(raw)
            hashes[asset.name] = hashlib.sha256(raw).hexdigest()
        request = dict(job_id=job.id, project_id=project_id, task=project.task, classes=project.classes,
                       manifest=job.manifest, sha256=hashes, model=model)
        if project.task == 'detection_3d':
            input_path = STORAGE/f'{project_id}-inputs.json'
            if not input_path.is_file():
                raise ValueError('Lượt 3D cần calibration và kích thước ảnh KITTI. Tạo lượt từ màn hình chọn tác vụ.')
            inputs = json.loads(input_path.read_text(encoding='utf-8'))
            request['inputs'] = {name:inputs[name] for name in job.manifest}
        target = folder/'request.json'
        written.append(target)
        target.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
        if google:
            from .colab_google import prepare_job
            written.append(folder/'google.json')
            prepare_job(job)
            job.status = 'uploading'
        session.add(job)
        session.commit()
        session.refresh(job)
        return public_job(job)
    except Exception as exc:
        session.rollback()
        for target in written:
            target.unlink(missing_ok=True)
        if isinstance(exc, (OSError, ValueError)):
            raise HTTPException(422, f'Không xuất được lượt Colab: {exc}') from exc
        raise


def import_ready(job, session):
    from .main import save_bundle, MAX_FILE_BYTES
    folder = Path(job.root)/job.id
    marker, prediction = folder/'result.ready.json', folder/'predictions.json'
    if not marker.is_file() or not prediction.is_file():
        return
    if marker.stat().st_size > 4096 or prediction.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Kết quả Colab vượt giới hạn dung lượng')
    receipt = json.loads(marker.read_text(encoding='utf-8'))
    with prediction.open('rb') as stream:
        raw = stream.read(MAX_FILE_BYTES+1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('Kết quả Colab vượt 32 MiB')
    if receipt.get('job_id') != job.id:
        raise ValueError('Kết quả thuộc lượt Colab khác')
    if receipt.get('sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('Drive chưa đồng bộ xong hoặc checksum không khớp; sẽ tự thử lại')
    bundle = LabelBundle.model_validate_json(raw)
    if sorted(s.asset_name for s in bundle.samples) != sorted(job.manifest):
        raise ValueError('Kết quả phải đủ và đúng các mẫu của lượt Colab')
    if not bundle.run.model or bundle.run.inference_seconds is None:
        raise ValueError('Colab phải gửi tên model và thời gian inference đo thực tế')
    if any(s.active_seconds is not None for s in bundle.samples):
        raise ValueError('Thời gian người gán nhãn chỉ được đo trong editor, không lấy từ Colab')
    result = save_bundle(job.project_id, 'ai', bundle, session, commit=False)
    job.label_set_id = result['id']
    job.status, job.error = 'imported', None
    session.add(job)
    session.commit()  # AI snapshot + receipt committed together; restart cannot import twice.


def sync_once():
    if not SYNC_LOCK.acquire(blocking=False):
        return
    try:
        with Session(engine) as session:
            jobs = session.exec(select(ColabJob).where(ColabJob.status != 'imported')).all()
            for job in jobs:
                try:
                    from .colab_google import sync_job
                    sync_job(job)
                    import_ready(job, session)
                    session.add(job)
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    job.status, job.error = 'error', str(exc)[:1000]
                    session.add(job)
                    session.commit()
    finally:
        SYNC_LOCK.release()


async def watch():
    import asyncio
    while True:
        try:
            await asyncio.to_thread(sync_once)
        except Exception:
            logging.getLogger(__name__).exception('Colab sync will retry')
        await asyncio.sleep(5)
