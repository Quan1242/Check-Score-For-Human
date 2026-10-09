import json
import os
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .db import STORAGE, get_session, init_db
from .models import Asset, LabelSet, Project
from .schemas import LabelBundle, ProjectCreate

MAX_FILE_BYTES = 32 * 1024 * 1024

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="M49 Annotation Benchmark API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","), allow_methods=["*"], allow_headers=["*"])


def get_project(project_id: str, session: Session):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Không tìm thấy dự án")
    return project

async def read_limited(file: UploadFile):
    data = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "Mỗi tệp tối đa 32 MiB")
    if not data:
        raise HTTPException(400, "Tệp rỗng")
    return data

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/projects", status_code=201)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)):
    project = Project(**body.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project

@app.get("/api/projects")
def projects(session: Session = Depends(get_session)):
    return session.exec(select(Project).order_by(Project.created_at.desc())).all()

@app.get("/api/projects/{project_id}/assets")
def assets(project_id: str, session: Session = Depends(get_session)):
    get_project(project_id, session)
    rows = session.exec(select(Asset).where(Asset.project_id == project_id)).all()
    return [{**a.model_dump(exclude={"storage_name"}), "url": f"/api/assets/{a.id}/file"} for a in rows]

@app.post("/api/projects/{project_id}/assets", status_code=201)
async def upload_asset(project_id: str, file: UploadFile = File(...), session: Session = Depends(get_session)):
    project = get_project(project_id, session)
    name = (file.filename or "").replace("\\", "/").split("/")[-1]
    ext = Path(name).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".bin", ".pcd"}:
        raise HTTPException(400, "Hỗ trợ JPG, PNG; dự án 3D hỗ trợ thêm BIN/PCD")
    if ext in {".bin", ".pcd"} and project.task != "detection_3d":
        raise HTTPException(400, "Point cloud chỉ dùng cho dự án 3D")
    if session.exec(select(Asset).where(Asset.project_id == project_id, Asset.name == name)).first():
        raise HTTPException(409, "Tên tệp đã tồn tại trong dự án")
    data = await read_limited(file)
    width = height = None
    kind = "pointcloud"
    if ext in {".jpg", ".jpeg", ".png"}:
        try:
            with Image.open(BytesIO(data)) as img:
                if img.format not in {"JPEG", "PNG"}:
                    raise ValueError("Không phải ảnh JPEG/PNG")
                width, height = img.size
                img.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise HTTPException(400, "Ảnh không hợp lệ")
        kind = "image"
    elif ext == ".bin" and len(data) % 16:
        raise HTTPException(400, "KITTI BIN cần các điểm float32 x,y,z,intensity (16 byte/điểm)")
    elif ext == ".pcd" and b"FIELDS" not in data[:4096]:
        raise HTTPException(400, "Không tìm thấy header PCD")
    storage_name = str(uuid4()) + ext
    path = STORAGE / storage_name
    path.write_bytes(data)
    asset = Asset(project_id=project_id, name=name, kind=kind, storage_name=storage_name, width=width, height=height, size_bytes=len(data))
    try:
        session.add(asset)
        session.commit()
        session.refresh(asset)
    except Exception as exc:
        session.rollback()
        path.unlink(missing_ok=True)
        if isinstance(exc, IntegrityError):
            raise HTTPException(409, "Tên tệp đã tồn tại")
        raise
    return asset.model_dump(exclude={"storage_name"})

@app.get("/api/assets/{asset_id}/file")
def asset_file(asset_id: str, session: Session = Depends(get_session)):
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Không tìm thấy tệp")
    path = STORAGE / asset.storage_name
    if not path.is_file():
        raise HTTPException(404, "Tệp lưu trữ bị thiếu")
    return FileResponse(path)


def save_bundle(project_id: str, source: str, bundle: LabelBundle, session: Session, commit: bool = True):
    project = get_project(project_id, session)
    if bundle.task != project.task:
        raise HTTPException(422, "Tác vụ của nhãn không khớp dự án")
    if source == "assisted":
        parent = session.get(LabelSet, bundle.parent_id) if bundle.parent_id else None
        if not parent or parent.project_id != project_id or parent.source != "ai":
            raise HTTPException(422, "Nhãn sửa AI cần parent_id của lần chạy AI trong cùng dự án")
    elif bundle.parent_id is not None:
        raise HTTPException(422, "parent_id chỉ dùng cho nhãn assisted")
    if source in {"manual", "assisted"} and not (bundle.annotator or "").strip():
        raise HTTPException(422, "Cần tên người gán nhãn")
    assets = {a.name: a for a in session.exec(select(Asset).where(Asset.project_id == project_id)).all()}
    seen = set()
    kind = {"detection_2d": "bbox2d", "instance_segmentation": "polygon", "detection_3d": "cuboid3d"}[project.task]
    for sample in bundle.samples:
        asset = assets.get(sample.asset_name)
        if not asset or sample.asset_name in seen:
            raise HTTPException(422, "Tên ảnh/point cloud không tồn tại hoặc trùng trong gói nhãn")
        seen.add(sample.asset_name)
        if (project.task == "detection_3d") != (asset.kind == "pointcloud"):
            raise HTTPException(422, "Nhãn 3D phải gắn với point cloud; nhãn 2D/mask phải gắn với ảnh")
        ids = set()
        for obj in sample.objects:
            if obj.id in ids or obj.category not in project.classes or obj.geometry.kind != kind:
                raise HTTPException(422, "ID trùng, lớp sai hoặc kiểu hình học không khớp")
            ids.add(obj.id)
            if source == "ai" and obj.confidence is None:
                raise HTTPException(422, "Dự đoán AI cần confidence")
            g = obj.geometry
            if kind == "bbox2d" and (g.xyxy[2] > asset.width or g.xyxy[3] > asset.height):
                raise HTTPException(422, "Khung nằm ngoài ảnh gốc")
            if kind == "polygon" and any(x < 0 or y < 0 or x > asset.width or y > asset.height for x, y in g.points):
                raise HTTPException(422, "Polygon nằm ngoài ảnh gốc")
    row = LabelSet(project_id=project_id, source=source, name=bundle.name, annotator=bundle.annotator, parent_id=bundle.parent_id, payload=bundle.model_dump(mode="json"))
    session.add(row)
    if commit:
        session.commit()
    else:
        session.flush()
    session.refresh(row)
    return {"id": row.id, "source": source, "samples": len(bundle.samples)}

@app.post("/api/projects/{project_id}/imports/{source}", status_code=201)
async def import_labels(project_id: str, source: str, file: UploadFile = File(...), session: Session = Depends(get_session)):
    if source not in {"ground_truth", "ai"}:
        raise HTTPException(422, "Import chỉ hỗ trợ ground_truth hoặc ai")
    data = await read_limited(file)
    try:
        bundle = LabelBundle.model_validate_json(data)
    except ValidationError as exc:
        raise HTTPException(422, str(exc))
    return save_bundle(project_id, source, bundle, session)

@app.post("/api/projects/{project_id}/annotations/{source}", status_code=201)
def save_annotation(project_id: str, source: str, body: LabelBundle, session: Session = Depends(get_session)):
    if source not in {"manual", "assisted"}:
        raise HTTPException(422, "Chọn manual hoặc assisted")
    return save_bundle(project_id, source, body, session)

@app.get("/api/projects/{project_id}/label-sets")
def list_labels(project_id: str, session: Session = Depends(get_session)):
    get_project(project_id, session)
    rows = session.exec(select(LabelSet).where(LabelSet.project_id == project_id)).all()
    return [r.model_dump(exclude={"payload"}) for r in rows]

@app.get("/api/label-sets/{label_id}")
def label_detail(label_id: str, session: Session = Depends(get_session)):
    row = session.get(LabelSet, label_id)
    if not row:
        raise HTTPException(404, "Không tìm thấy bộ nhãn")
    return row.payload

@app.get("/api/projects/{project_id}/summary")
def summary(project_id: str, session: Session = Depends(get_session)):
    project = get_project(project_id, session)
    assets = session.exec(select(Asset).where(Asset.project_id == project_id)).all()
    labels = session.exec(select(LabelSet).where(LabelSet.project_id == project_id)).all()
    return {"project": project, "assets": len(assets), "label_sets": {source: sum(r.source == source for r in labels) for source in ["ground_truth", "ai", "manual", "assisted"]}, "evaluation_status": "m49_available_pending_validation"}

# Imported after save_bundle so the assignment router can share validation.
from .benchmark import router as benchmark_router
app.include_router(benchmark_router)
