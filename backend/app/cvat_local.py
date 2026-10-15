"""Create local CVAT tasks for up to ten M49 assignments (2D and polygons)."""
import json
from pathlib import Path
from threading import RLock
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request as WebRequest
from pydantic import Field, SecretStr, ValidationError
from sqlmodel import Session, select

from .benchmark import require, editor, claim, elapsed, public_assignment
from .colab_google import local_request, read_json, write_json
from .db import get_session
from .models import AnnotationEvent, Assignment, Asset, Experiment, Project
from .schemas import StrictModel, LabelBundle

router = APIRouter(prefix='/api/cvat')
LOCK = RLock()


def folder():
    from .main import STORAGE
    path = STORAGE/'cvat-local'
    path.mkdir(exist_ok=True, parents=True)
    return path


class Connection(StrictModel):
    url: str = 'http://localhost:8080'
    token: SecretStr


def normalized_url(value):
    parsed = urlparse(value.strip())
    if (parsed.scheme not in ('http', 'https') or parsed.hostname not in ('localhost', '127.0.0.1', '::1')
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise HTTPException(422, 'Nhập địa chỉ CVAT trên máy này, ví dụ http://localhost:8080')
    try:
        parsed.port
    except ValueError:
        raise HTTPException(422, 'Cổng CVAT không hợp lệ') from None
    return value.strip().rstrip('/')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the local CVAT token to a redirected host.


def remote(config, method, path, value=None, body=None, content_type=None):
    headers = {'Authorization': 'Bearer '+config['token'], 'Accept': 'application/vnd.cvat+json'}
    if value is not None:
        body, content_type = json.dumps(value).encode(), 'application/json'
    if content_type:
        headers['Content-Type'] = content_type
    try:
        with build_opener(NoRedirect).open(Request(config['url']+'/api/'+path, data=body,
                headers=headers, method=method), timeout=30) as response:
            raw = response.read(4*1024*1024+1)
            if len(raw) > 4*1024*1024:
                raise HTTPException(502, 'Phản hồi CVAT vượt giới hạn')
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raise HTTPException(502, f'CVAT trả HTTP {exc.code}. Kiểm tra địa chỉ, token và quyền đọc/ghi task.') from None
    except (URLError, TimeoutError, OSError):
        raise HTTPException(502, 'Không kết nối được CVAT. Mở CVAT trên máy rồi thử lại.') from None
    except ValueError:
        raise HTTPException(502, 'Địa chỉ này không trả dữ liệu API CVAT hợp lệ.') from None


def settings():
    value = read_json(folder()/'connection.json')
    if not value:
        raise HTTPException(422, 'Kết nối CVAT trước khi mở nhiệm vụ')
    return value


@router.get('/connection')
def connection():
    value = read_json(folder()/'connection.json', {})
    return dict(configured=bool(value), url=value.get('url', 'http://localhost:8080'))


@router.post('/connection')
def connect(body: Connection, request: WebRequest):
    local_request(request)
    value = dict(url=normalized_url(body.url), token=body.token.get_secret_value().strip())
    if not value['token'] or any(c.isspace() for c in value['token']):
        raise HTTPException(422, 'Nhập Personal Access Token của CVAT')
    with LOCK:
        user = remote(value, 'GET', 'users/self')
        value['user_id'] = user['id']
        write_json(folder()/'connection.json', value)
    return connection()


@router.post('/disconnect')
def disconnect(request: WebRequest):
    local_request(request)
    with LOCK:
        (folder()/'connection.json').unlink(missing_ok=True)
    return connection()


def context(key, session):
    row = require(session, Assignment, key)
    exp = require(session, Experiment, row.experiment_id)
    project = require(session, Project, exp.project_id)
    if project.task not in ('detection_2d', 'instance_segmentation'):
        raise HTTPException(422, 'Kết nối CVAT hiện hỗ trợ ảnh 2D và polygon; 3D dùng trình gán nhãn M49.')
    if row.final_id:
        raise HTTPException(409, 'Nhiệm vụ đã chốt')
    return row, project, require(session, Asset, row.asset_id)


def binding(key, config):
    path = folder()/(key+'.json')
    state = read_json(path)
    if state and 'group' in state:
        path = folder()/(state['group']+'.json')
        state = read_json(path)
    if state and (state['url'] != config['url'] or state['user_id'] != config['user_id']):
        raise HTTPException(409, 'Kết nối lại đúng máy chủ và tài khoản CVAT đã tạo nhiệm vụ này.')
    return path, state


def upload_images(config, task_id, assets):
    from .main import STORAGE, MAX_FILE_BYTES
    boundary = 'm49'+uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="image_quality"\r\n\r\n100\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="sorting_method"\r\n\r\nlexicographical\r\n'.encode()]
    for index, asset in enumerate(assets):
        raw = (STORAGE/asset.storage_name).read_bytes()
        if len(raw) > MAX_FILE_BYTES or len(raw) != asset.size_bytes:
            raise HTTPException(422, 'Tệp ảnh đã thay đổi hoặc vượt giới hạn')
        if any(c in asset.name for c in '\r\n"/\\'):
            raise HTTPException(422, 'Tên ảnh không hợp lệ để gửi CVAT')
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="client_files[{index}]"; filename="{asset.name}"\r\n'
                      'Content-Type: application/octet-stream\r\n\r\n').encode()+raw+b'\r\n')
    parts.append(f'--{boundary}--\r\n'.encode())
    return remote(config, 'POST', f'tasks/{task_id}/data/', body=b''.join(parts),
                  content_type='multipart/form-data; boundary='+boundary)


def members_of(state, key, asset):
    # Existing one-image tasks remain readable.
    if 'members' in state:
        return state['members']
    return [dict(key=key, name=asset.name, width=asset.width, height=asset.height,
                 revision=state['revision'], objects=state['objects'])]


def verify_frames(config, state, members):
    meta = remote(config, 'GET', f"tasks/{state['task_id']}/data/meta")
    frames = meta.get('frames', [])
    expected = {m['name']: m for m in members}
    if (meta.get('size') != len(members) or meta.get('deleted_frames')
            or len(frames) != len(members) or len(expected) != len(members)
            or {f.get('name') for f in frames} != set(expected)
            or meta.get('start_frame', 0) != 0 or meta.get('frame_filter', '')):
        raise HTTPException(409, 'Dữ liệu task CVAT không khớp mẫu M49; không nhập nhãn.')
    mapping = {}
    for index, frame in enumerate(frames):
        member = expected[frame['name']]
        if (frame.get('width'), frame.get('height')) != (member['width'], member['height']):
            raise HTTPException(409, 'Kích thước ảnh CVAT không khớp mẫu M49.')
        mapping[member['key']] = index
    return mapping


@router.post('/assignments/{key}/open')
def open_task(key: str, request: WebRequest, session: Session = Depends(get_session)):
    local_request(request)
    with LOCK:
        config = settings()
        row, project, asset = context(key, session)
        path, state = binding(key, config)
        if not state:
            candidates = session.exec(select(Assignment).where(
                Assignment.experiment_id == row.experiment_id, Assignment.annotator == row.annotator,
                Assignment.mode == row.mode, Assignment.parent_id == row.parent_id,
                Assignment.final_id.is_(None)).order_by(Assignment.id)).all()
            # Do not replace tasks that were already opened separately.
            rows = [row] + [r for r in candidates if r.id != key and not (folder()/(r.id+'.json')).exists()][:9]
            members = []
            for item in rows:
                data = editor(item.id, session)
                current = claim(session, item.id, item.revision)
                current.active_seconds, current.running_since = elapsed(current), None
                session.add(current)
                members.append(dict(key=current.id, name=data['asset']['name'],
                    width=data['asset']['width'], height=data['asset']['height'],
                    revision=current.revision, objects=data['objects']))
            session.commit()
            state = dict(url=config['url'], user_id=config['user_id'], members=members,
                         task_id=None, ready=False, upload_started=False)
            # Persist the group before its pointers so retries never recreate a remote task.
            path = folder()/('group-'+key+'.json')
            write_json(path, state)
            for member in members:
                write_json(folder()/(member['key']+'.json'), dict(group=path.stem))
        members = members_of(state, key, asset)
        for member in members:
            current = require(session, Assignment, member['key'])
            if not current.final_id and current.revision != member['revision']:
                raise HTTPException(409, 'Nhãn M49 đã thay đổi sau khi mở CVAT. Không ghi đè nhiệm vụ này.')
        shape_type = 'rectangle' if project.task == 'detection_2d' else 'polygon'
        if state['task_id'] is None:
            task = remote(config, 'POST', 'tasks', dict(name=f'M49 {row.mode} {key} ({len(members)} images)',
                labels=[dict(name=c, type=shape_type, attributes=[]) for c in project.classes]))
            state['task_id'] = int(task['id'])
            write_json(path, state)
        task_id = state['task_id']
        result = dict(ready=False, task_id=task_id, url=None,
                      samples=[dict(assignment_id=m['key'], name=m['name'],
                          finalized=bool(require(session, Assignment, m['key']).final_id)) for m in members])
        if not state['upload_started']:
            task = remote(config, 'GET', f'tasks/{task_id}')
            if not task.get('size'):
                assets = [require(session, Asset, require(session, Assignment, m['key']).asset_id) for m in members]
                uploaded = upload_images(config, task_id, assets)
                state['rq_id'] = uploaded.get('rq_id')
            state['upload_started'] = True
            write_json(path, state)
        if not state['ready']:
            if state.get('rq_id'):
                progress = remote(config, 'GET', 'requests/'+quote(state['rq_id'], safe=''))
                if progress['status'] == 'failed':
                    raise HTTPException(502, f'CVAT không xử lý được ảnh của task {task_id}. Kiểm tra task trong CVAT.')
                if progress['status'] != 'finished':
                    return result
            task = remote(config, 'GET', f'tasks/{task_id}')
            if not task.get('size'):
                return result
            frames = verify_frames(config, state, members)
            labels = remote(config, 'GET', f'labels?task_id={task_id}&page_size=100')['results']
            mapping = {item['name']: item['id'] for item in labels}
            shapes = []
            for member in members:
                for obj in member['objects']:
                    geometry = obj['geometry']
                    points = geometry['xyxy'] if shape_type == 'rectangle' else [v for p in geometry['points'] for v in p]
                    shapes.append(dict(type=shape_type, frame=frames[member['key']], label_id=mapping[obj['category']],
                        points=points, occluded=False, outside=False, rotation=0, attributes=[], source='manual'))
            remote(config, 'PUT', f'tasks/{task_id}/annotations', dict(version=0, tags=[], tracks=[], shapes=shapes))
            state['ready'] = True
            write_json(path, state)
        return dict(result, ready=True, url=f"{config['url']}/tasks/{task_id}")


class ImportResult(StrictModel):
    total_seconds: float = Field(gt=0, allow_inf_nan=False)


def objects_from_annotations(data, labels, task, frame=0, frame_count=1):
    if not isinstance(data, dict) or not isinstance(data.get('shapes'), list):
        raise ValueError('CVAT trả dữ liệu nhãn không hợp lệ; không chốt thành nhãn rỗng.')
    if any(data.get(k) for k in ('tracks', 'tags', 'intervals')):
        raise ValueError('Chỉ nhập rectangle/polygon dạng Shape; không hỗ trợ Track hoặc Tag.')
    if any(not isinstance(s, dict) or type(s.get('frame')) is not int or not 0 <= s['frame'] < frame_count for s in data['shapes']):
        raise ValueError('Nhãn CVAT có frame không hợp lệ.')
    data = dict(data, shapes=[s for s in data['shapes'] if s['frame'] == frame])
    expected = 'rectangle' if task == 'detection_2d' else 'polygon'
    objects = []
    if len(data.get('shapes', [])) > 80:
        raise ValueError('Tối đa 80 đối tượng mỗi mẫu.')
    for shape in data.get('shapes', []):
        if (shape['type'] != expected or shape['frame'] != frame or shape.get('rotation', 0) != 0
                or shape.get('outside') or shape.get('elements')):
            raise ValueError('Nhãn CVAT không đúng loại hình, có xoay hoặc thuộc frame khác.')
        points = shape['points']
        if expected == 'rectangle':
            geometry = dict(kind='bbox2d', xyxy=points)
        else:
            if len(points) % 2:
                raise ValueError('Tọa độ polygon không hợp lệ.')
            geometry = dict(kind='polygon', points=list(zip(points[::2], points[1::2])))
        objects.append(dict(id='cvat-'+str(shape['id']), category=labels[shape['label_id']], geometry=geometry))
    return objects


def import_one(key, body, request, session, commit=True, snapshot=None):
    from .main import save_bundle
    local_request(request)
    with LOCK:
        config = settings()
        row, project, asset = context(key, session)
        _, state = binding(key, config)
        if not state or not state['ready']:
            raise HTTPException(409, 'Chờ task CVAT sẵn sàng trước khi nhập nhãn.')
        members = members_of(state, key, asset)
        member = next(m for m in members if m['key'] == key)
        task_id = state['task_id']
        if snapshot is None:
            frames = verify_frames(config, state, members)
            data = remote(config, 'GET', f'tasks/{task_id}/annotations')
            labels = remote(config, 'GET', f'labels?task_id={task_id}&page_size=100')['results']
        else:
            frames, data, labels = snapshot
        try:
            objects = objects_from_annotations(data, {v['id']: v['name'] for v in labels}, project.task, frames[key], len(members))
            bundle = LabelBundle(task=project.task, name=f'CVAT {row.mode} {asset.name}'[:120],
                annotator=row.annotator, parent_id=row.parent_id,
                samples=[dict(asset_name=asset.name, objects=objects, active_seconds=body.total_seconds)])
        except (ValueError, KeyError, TypeError, ValidationError) as exc:
            raise HTTPException(422, f'Không nhập được nhãn CVAT: {exc}') from None
        row = claim(session, key, member['revision'])
        saved = save_bundle(project.id, row.mode, bundle, session, commit=False)
        row.draft_id = row.final_id = saved['id']
        row.active_seconds, row.running_since = body.total_seconds, None
        session.add(row)
        session.add(AnnotationEvent(assignment_id=key, revision=row.revision, kind='cvat_import_declared_sample_time'))
        if commit:
            session.commit()
        else:
            session.flush()
        return public_assignment(row)


@router.post('/assignments/{key}/import')
def import_task(key: str, body: ImportResult, request: WebRequest, session: Session = Depends(get_session)):
    return import_one(key, body, request, session)


class BatchImport(StrictModel):
    samples: dict[str, ImportResult]


@router.post('/assignments/{key}/import-batch')
def import_batch(key: str, body: BatchImport, request: WebRequest, session: Session = Depends(get_session)):
    local_request(request)
    with LOCK:
        config = settings()
        _, _, asset = context(key, session)
        _, state = binding(key, config)
        if not state or not state['ready']:
            raise HTTPException(409, 'Chờ task CVAT sẵn sàng trước khi nhập nhãn.')
        members = members_of(state, key, asset)
        pending = {m['key'] for m in members if not require(session, Assignment, m['key']).final_id}
        if set(body.samples) != pending:
            raise HTTPException(422, 'Nhập thời gian cho từng ảnh chưa chốt trong task.')
        task_id = state['task_id']
        snapshot = (verify_frames(config, state, members),
                    remote(config, 'GET', f'tasks/{task_id}/annotations'),
                    remote(config, 'GET', f'labels?task_id={task_id}&page_size=100')['results'])
        try:
            result = [import_one(k, body.samples[k], request, session, commit=False, snapshot=snapshot) for k in sorted(pending)]
            session.commit()
        except Exception:
            session.rollback()
            raise
        return dict(assignments=result)
