from io import BytesIO
import json
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
from app.db import get_session
from app import main

@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    monkeypatch.setattr(main, "init_db", lambda: None)
    def sessions():
        with Session(engine) as session:
            yield session
    main.app.dependency_overrides[get_session] = sessions
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()
    engine.dispose()

def project(c, task="detection_2d"):
    response = c.post("/api/projects", json={"name": "Demo", "task": task, "classes": ["car"]})
    assert response.status_code == 201
    return response.json()["id"]

def upload_image(c, pid):
    stream = BytesIO()
    Image.new("RGB", (100, 80)).save(stream, format="PNG")
    return c.post(f"/api/projects/{pid}/assets", files={"file": ("demo.png", stream.getvalue(), "image/png")})

def bundle():
    return {"task": "detection_2d", "name": "AI run", "samples": [{"asset_name": "demo.png", "objects": [{"id": "1", "category": "car", "confidence": 0.9, "geometry": {"kind": "bbox2d", "xyxy": [1, 2, 50, 60]}}]}]}

def import_json(c, pid, source, data):
    return c.post(f"/api/projects/{pid}/imports/{source}", files={"file": ("labels.json", json.dumps(data), "application/json")})

def test_ai_assisted_keeps_original_and_metadata_hides_payload(client):
    pid = project(client)
    assert upload_image(client, pid).status_code == 201
    original = bundle()
    ai = import_json(client, pid, "ai", original)
    assert ai.status_code == 201
    ai_id = ai.json()["id"]
    edited = bundle()
    edited.update(annotator="A", parent_id=ai_id)
    edited["samples"][0]["objects"][0]["geometry"]["xyxy"][2] = 55
    assert client.post(f"/api/projects/{pid}/annotations/assisted", json=edited).status_code == 201
    assert client.get(f"/api/label-sets/{ai_id}").json()["samples"][0]["objects"][0]["geometry"]["xyxy"][2] == 50
    rows = client.get(f"/api/projects/{pid}/label-sets").json()
    assert all("payload" not in r for r in rows)
    assert client.get(f"/api/projects/{pid}/summary").json()["label_sets"]["assisted"] == 1

def test_upload_duplicate_invalid_and_size_limit(client, monkeypatch):
    pid = project(client)
    assert upload_image(client, pid).status_code == 201
    assert upload_image(client, pid).status_code == 409
    assert client.post(f"/api/projects/{pid}/assets", files={"file": ("broken.png", b"not an image")}).status_code == 400
    monkeypatch.setattr(main, "MAX_FILE_BYTES", 4)
    assert client.post(f"/api/projects/{pid}/assets", files={"file": ("big.png", b"12345")}).status_code == 413

@pytest.mark.parametrize("fault", ["unknown_asset", "unknown_class", "out_of_bounds", "no_confidence", "wrong_task", "duplicate_sample"])
def test_reject_invalid_predictions(client, fault):
    pid = project(client); upload_image(client, pid)
    data = bundle(); obj = data["samples"][0]["objects"][0]
    if fault == "unknown_asset": data["samples"][0]["asset_name"] = "missing.png"
    if fault == "unknown_class": obj["category"] = "bus"
    if fault == "out_of_bounds": obj["geometry"]["xyxy"][2] = 101
    if fault == "no_confidence": obj.pop("confidence")
    if fault == "wrong_task": data["task"] = "instance_segmentation"
    if fault == "duplicate_sample": data["samples"].append(data["samples"][0])
    assert import_json(client, pid, "ai", data).status_code == 422

def test_cross_project_parent_rejected(client):
    a, b = project(client), project(client)
    upload_image(client, a); upload_image(client, b)
    ai = import_json(client, a, "ai", bundle()).json()["id"]
    data = bundle(); data.update(parent_id=ai, annotator="A")
    assert client.post(f"/api/projects/{b}/annotations/assisted", json=data).status_code == 422

def test_segmentation_and_3d_validation(client):
    pid = project(client, "instance_segmentation"); upload_image(client, pid)
    data = bundle(); data["task"] = "instance_segmentation"
    data["samples"][0]["objects"][0]["geometry"] = {"kind": "polygon", "points": [[1,1],[50,1],[30,50]]}
    assert import_json(client, pid, "ai", data).status_code == 201
    p3 = project(client, "detection_3d")
    assert client.post(f"/api/projects/{p3}/assets", files={"file": ("demo.bin", b"0"*16)}).status_code == 201
    data["task"] = "detection_3d"; data["samples"][0]["asset_name"] = "demo.bin"
    data["samples"][0]["objects"][0]["geometry"] = {"kind":"cuboid3d", "center":[1,2,3], "size_lwh":[4,2,1], "yaw":0}
    assert import_json(client, p3, "ai", data).status_code == 201
    data["samples"][0]["objects"][0]["geometry"]["size_lwh"][0] = -1
    assert import_json(client, p3, "ai", data).status_code == 422
