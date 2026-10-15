"""Personal Colab handoff: OAuth Drive upload, prepared notebook, result download.

This does not start a Colab runtime. The user runs the prepared notebook in Colab.
Single-user, single-worker localhost deployment, like the rest of this application.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID
import secrets
import tempfile
from threading import RLock
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, File, HTTPException, Request as WebRequest, UploadFile
from fastapi.responses import HTMLResponse

SCOPE = 'https://www.googleapis.com/auth/drive.file'
API = 'https://www.googleapis.com/drive/v3/'
LOCK = RLock()
PENDING = {}
BUNDLED_CLIENT = Path(__file__).with_name('google-oauth-client.json')
router = APIRouter(prefix='/api/colab/google')


def redirect_uri():
    return f"http://127.0.0.1:{os.getenv('M49_BACKEND_PORT', '8000')}/api/colab/google/callback"


def private_dir():
    from .main import STORAGE
    folder = STORAGE/'google-colab'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'posix':
        folder.chmod(0o700)
        for name in ('client.json', 'token.json'):
            path = folder/name
            if path.exists():
                path.chmod(0o600)
    return folder


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def oauth_client():
    """Operator-managed configuration; never return it in a public response."""
    configured = os.getenv('M49_GOOGLE_CLIENT_FILE')
    local = private_dir()/'client.json'
    path = Path(configured).expanduser() if configured else local if local.is_file() else BUNDLED_CLIENT
    try:
        value = read_json(path)
        if value is None:
            return None
        value = value.get('installed', value)
        client_id, secret = value['client_id'], value['client_secret']
        if not isinstance(client_id, str) or not client_id.endswith('.apps.googleusercontent.com') or not isinstance(secret, str) or not secret:
            return None
        return dict(client_id=client_id, client_secret=secret)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def write_json(path, value):
    # Create exclusively with mode 0600, before any secret bytes are written.
    fd, name = tempfile.mkstemp(prefix=path.name+'.', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def local_request(request: WebRequest):
    # Reject cross-site form submissions to local credential-management endpoints.
    origin = request.headers.get('origin')
    allowed = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000').split(',')
    if origin and origin not in allowed:
        raise HTTPException(403, 'Nguồn yêu cầu không được phép')


class GoogleError(RuntimeError):
    def __init__(self, status, reason=''):
        self.status = status
        explanations = {
            'accessNotConfigured': 'Google Drive API chưa được bật trong project của OAuth client. Bật Google Drive API rồi kết nối lại.',
            'SERVICE_DISABLED': 'Google Drive API chưa được bật trong project của OAuth client. Bật Google Drive API rồi kết nối lại.',
            'invalid_client': 'OAuth client không hợp lệ. Nhập lại JSON Desktop app tải từ Google Cloud.',
            'invalid_grant': 'Mã cấp quyền đã hết hạn hoặc đã dùng. Bấm Kết nối Google trong M49 để bắt đầu lại.',
            'redirect_uri_mismatch': 'Địa chỉ callback không khớp OAuth client. Dùng OAuth client loại Desktop app và thử kết nối lại.',
            'insufficientPermissions': 'Google chưa cấp đủ quyền Drive. Kết nối lại và chọn quyền quản lý tệp của ứng dụng.',
            'ACCESS_TOKEN_SCOPE_INSUFFICIENT': 'Google chưa cấp đủ quyền Drive. Kết nối lại và chọn quyền quản lý tệp của ứng dụng.',
            'admin_policy_enforced': 'Quản trị viên tài khoản Google đang chặn quyền ứng dụng.',
        }
        self.reason = reason if reason in explanations else ''
        super().__init__(explanations.get(reason, f'Google trả lỗi HTTP {status}. Kiểm tra quyền Google, Drive API và kết nối lại.'))


def google_error(status, raw):
    # Only known reason codes are exposed, never Google's raw message or credentials.
    try:
        error = json.loads(raw).get('error', {})
        if isinstance(error, str):
            return GoogleError(status, error)
        for item in error.get('details', []) + error.get('errors', []):
            result = GoogleError(status, item.get('reason', ''))
            if result.reason:
                return result
    except (ValueError, AttributeError, TypeError):
        pass
    return GoogleError(status)


def http(method, url, data=None, headers=None, limit=1024*1024):
    try:
        with urlopen(Request(url, data=data, headers=headers or {}, method=method), timeout=60) as response:
            raw = response.read(limit+1)
            if len(raw) > limit:
                raise ValueError('Phản hồi Google vượt giới hạn dung lượng')
            return raw, dict(response.headers)
    except HTTPError as exc:
        if exc.code == 308:  # Resumable upload acknowledgement.
            return b'', dict(exc.headers)
        raise google_error(exc.code, exc.read(64*1024)) from None
    except (URLError, OSError) as exc:
        raise RuntimeError('Không kết nối được Google Drive; ứng dụng sẽ thử lại.') from exc


def token_request(values):
    raw, _ = http('POST', 'https://oauth2.googleapis.com/token', urlencode(values).encode(),
                  {'Content-Type': 'application/x-www-form-urlencoded'})
    return json.loads(raw)


@router.get('/status')
def status():
    with LOCK:
        folder = private_dir()
        token = read_json(folder/'token.json', {})
        return dict(configured=oauth_client() is not None, connected=bool(token.get('refresh_token')),
                    scope=SCOPE)


@router.post('/client')
async def configure_client(request: WebRequest, file: UploadFile = File(...)):
    local_request(request)
    if os.getenv('M49_GOOGLE_CLIENT_FILE'):
        await file.close()
        raise HTTPException(409, 'Cấu hình Google do quản trị viên quản lý trên backend.')
    try:
        raw = await file.read(64*1024+1)
        if len(raw) > 64*1024:
            raise ValueError()
        value = json.loads(raw)['installed']
        client_id, secret = value['client_id'], value['client_secret']
        if not isinstance(client_id, str) or not client_id.endswith('.apps.googleusercontent.com') or not isinstance(secret, str) or not secret:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, 'Chọn tệp JSON OAuth client loại Desktop app tải từ Google Cloud') from None
    finally:
        await file.close()
    with LOCK:
        if status()['connected']:
            raise HTTPException(409, 'Ngắt kết nối Google trước khi đổi OAuth client')
        write_json(private_dir()/'client.json', dict(client_id=client_id, client_secret=secret))
        PENDING.clear()
    return status()


@router.post('/connect')
def connect(request: WebRequest, run_id: UUID | None = None):
    local_request(request)
    with LOCK:
        client = oauth_client()
        if not client:
            raise HTTPException(503, 'Kết nối Google chưa được quản trị viên cấu hình. Liên hệ người cung cấp ứng dụng.')
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        PENDING.clear()
        PENDING[state] = (time.time()+600, verifier, str(run_id) if run_id else None)
        return {'url': 'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(dict(
            client_id=client['client_id'], redirect_uri=redirect_uri(), response_type='code', scope=SCOPE,
            access_type='offline', prompt='consent', state=state,
            code_challenge=challenge, code_challenge_method='S256'))}


@router.get('/callback', response_class=HTMLResponse)
def callback(state: str = '', code: str = '', error: str = ''):
    with LOCK:
        pending = PENDING.pop(state, None)
        if not pending or pending[0] < time.time():
            raise HTTPException(400, 'Phiên cấp quyền hết hạn hoặc không hợp lệ. Kết nối lại từ ứng dụng.')
        if error or not code:
            return HTMLResponse('<meta charset="utf-8"><p>Chưa được cấp quyền Google. Quay lại ứng dụng để thử lại.</p>', status_code=400)
        client = oauth_client()
        if not client:
            raise HTTPException(503, 'Cấu hình Google của ứng dụng không khả dụng. Liên hệ quản trị viên.')
        stage = 'Đổi mã cấp quyền Google'
        try:
            token = token_request({**client, 'code': code, 'code_verifier': pending[1],
                                   'redirect_uri': redirect_uri(), 'grant_type': 'authorization_code'})
            if SCOPE not in token.get('scope', '').split():
                raise HTTPException(400, 'Chưa cấp quyền Drive. Bấm Kết nối Google lại và chọn quyền quản lý tệp của ứng dụng trên màn hình Google.')
            if not token.get('refresh_token'):
                raise HTTPException(400, 'Google chưa cấp quyền duy trì kết nối. Bấm Kết nối Google lại và xác nhận quyền.')
            token['expires_at'] = time.time()+token['expires_in']
            stage = 'Kiểm tra tài khoản Google Drive'
            raw, _ = http('GET', API+'about?fields=user(permissionId)', headers={'Authorization': 'Bearer '+token['access_token']})
            token['account_id'] = json.loads(raw)['user']['permissionId']
            stage = 'Lưu kết nối trên máy'
            write_json(private_dir()/'token.json', token)
        except GoogleError as exc:
            raise HTTPException(400, f'{stage}: {exc}') from None
        except RuntimeError:
            raise HTTPException(400, f'{stage}: Không kết nối được Google. Kiểm tra mạng rồi kết nối lại.') from None
        except (ValueError, KeyError, TypeError):
            raise HTTPException(400, f'{stage}: Google trả dữ liệu thiếu hoặc không hợp lệ. Bấm Kết nối Google để thử lại.') from None
        except OSError:
            raise HTTPException(400, f'{stage}: Không ghi được cấu hình. Kiểm tra quyền ghi thư mục storage trên máy.') from None
    content = '<meta charset="utf-8"><h2>Đã kết nối Google Drive</h2><p id="status">M49 sẽ tự tiếp tục và tải notebook nếu bạn đã chọn gửi lượt AI. Giữ web M49 mở; không cần sao chép URL này.</p>'
    if len(pending) > 2 and pending[2]:
        # Navigate from the callback itself: Google may sever the opener reference.
        endpoint = json.dumps('/api/guided/'+pending[2])
        content += '''<script>
const endpoint = '''+endpoint+''';
const deadline = Date.now() + 10 * 60 * 1000;
async function waitForNotebook() {
  if (Date.now() > deadline) {
    document.getElementById('status').textContent = 'Chưa nhận được notebook. Quay lại M49 để kiểm tra và mở Colab.';
    return;
  }
  try {
    const response = await fetch(endpoint, {cache: 'no-store'});
    if (response.ok) {
      const run = await response.json();
      if (run.colab_url) {
        const url = new URL(run.colab_url);
        if (url.protocol === 'https:' && url.hostname === 'colab.research.google.com' && !url.username && !url.password) {
          window.location.replace(url.href);
          return;
        }
      }
    }
  } catch {}
  setTimeout(waitForNotebook, 2000);
}
waitForNotebook();
</script>'''
    return HTMLResponse(content, headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})


@router.post('/disconnect')
def disconnect(request: WebRequest):
    local_request(request)
    with LOCK:
        (private_dir()/'token.json').unlink(missing_ok=True)
        PENDING.clear()
    return status()


@router.post('/checkpoints', status_code=201)
async def checkpoint(request: WebRequest, file: UploadFile = File(...)):
    from .colab_sync import store_checkpoint
    local_request(request)
    if not status()['connected']:
        await file.close()
        raise HTTPException(422, 'Kết nối Google trước khi tải checkpoint')
    root = private_dir()/'jobs'
    root.mkdir(exist_ok=True)
    return await store_checkpoint(file, root)


def credentials():
    with LOCK:
        folder = private_dir()
        token = read_json(folder/'token.json', {})
        if not token.get('refresh_token'):
            raise RuntimeError('Kết nối Google Drive để tiếp tục lượt AI')
        if token.get('expires_at', 0) < time.time()+60:
            client = oauth_client()
            if not client:
                raise RuntimeError('Cấu hình Google của ứng dụng không khả dụng. Liên hệ quản trị viên.')
            try:
                updated = token_request({**client, 'refresh_token': token['refresh_token'], 'grant_type': 'refresh_token'})
            except GoogleError as exc:
                if exc.status in (400, 401):
                    (folder/'token.json').unlink(missing_ok=True)
                raise
            token.update(updated)
            token['expires_at'] = time.time()+updated['expires_in']
            write_json(folder/'token.json', token)
        return token


def drive(method, path, value=None, limit=1024*1024):
    token = credentials()
    headers = {'Authorization': 'Bearer '+token['access_token']}
    data = None
    if value is not None:
        data = json.dumps(value).encode()
        headers['Content-Type'] = 'application/json'
    raw, _ = http(method, API+path, data, headers, limit)
    return json.loads(raw) if raw else {}


def media(file_id, limit):
    raw, _ = http('GET', API+f'files/{file_id}?alt=media', headers={'Authorization': 'Bearer '+credentials()['access_token']}, limit=limit)
    return raw


def upload_file(file_id, name, parent, source=None, mime='application/octet-stream'):
    # IDs are reserved and persisted before upload: retry/restart cannot create duplicates.
    total = source.stat().st_size if source else 0
    checksum = None
    if total:
        with source.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'md5').hexdigest()
    existing = None
    try:
        existing = drive('GET', f'files/{file_id}?fields=id,size,md5Checksum')
        if not total or (str(existing.get('size')) == str(total) and existing.get('md5Checksum') == checksum):
            return
    except GoogleError as exc:
        if exc.status != 404:
            raise
    metadata = dict(id=file_id, name=name, parents=[parent] if parent else [], mimeType=mime)
    if not total:
        drive('POST', 'files', metadata)
        return
    headers = {'Authorization': 'Bearer '+credentials()['access_token'], 'Content-Type': 'application/json',
               'X-Upload-Content-Type': mime, 'X-Upload-Content-Length': str(total)}
    upload_url = 'https://www.googleapis.com/upload/drive/v3/files'
    if existing:
        upload_url += '/'+file_id
        metadata = {'name': name, 'mimeType': mime}
    _, response_headers = http('PATCH' if existing else 'POST', upload_url+'?uploadType=resumable', json.dumps(metadata).encode(), headers)
    location = next(v for k, v in response_headers.items() if k.lower() == 'location')
    parsed = urlparse(location)
    if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.googleapis.com'):
        raise ValueError('Địa chỉ tải lên Google không hợp lệ')
    offset = 0
    with source.open('rb') as stream:
        while offset < total:
            stream.seek(offset)
            chunk = stream.read(8*1024*1024)
            if not chunk:
                raise ValueError('Tệp tải lên đã thay đổi; thử lại với tệp gốc')
            content_range = f'bytes {offset}-{offset+len(chunk)-1}/{total}'
            _, result_headers = http('PUT', location, chunk, {'Content-Type': mime, 'Content-Range': content_range,
                'Authorization': 'Bearer '+credentials()['access_token']})
            accepted = next((v for k, v in result_headers.items() if k.lower() == 'range'), None)
            next_offset = int(accepted.rsplit('-', 1)[1])+1 if accepted else offset+len(chunk)
            if not offset < next_offset <= offset+len(chunk):
                raise ValueError('Google chưa nhận đủ khối dữ liệu; sẽ thử tải lại')
            offset = next_offset
    uploaded = drive('GET', f'files/{file_id}?fields=id,size,md5Checksum')
    if str(uploaded.get('size')) != str(total) or uploaded.get('md5Checksum') != checksum:
        raise ValueError('Tệp trên Drive chưa khớp dung lượng/checksum; sẽ thử tải lại')


def job_info(job):
    state = read_json(Path(job.root)/job.id/'google.json', {})
    return {'colab_url': 'https://colab.research.google.com/drive/'+state['ids']['notebook'] if state.get('uploaded') else None,
            'transport': 'google' if state else 'desktop'}


def prepare_job(job):
    folder = Path(job.root)/job.id
    write_json(folder/'google.json', {'account_id': credentials()['account_id'], 'ids': {}, 'uploaded': False})


def notebook_bytes(job, state, request):
    template = Path(__file__).resolve().parents[2]/'colab'/f"{request['task']}.ipynb"
    notebook = json.loads(template.read_text(encoding='utf-8'))
    ids = state['ids']
    downloads = {'request.json': ids['request'], **{'assets/'+name: ids['asset:'+name] for name in request['manifest']}}
    if request['model'].get('custom'):
        downloads['../'+request['model']['checkpoint']] = ids['model']
    outputs = {name: ids['output:'+name] for name in ('predictions.json', 'timing.json', 'environment.txt', 'result.ready.json')}
    bootstrap = f'''# M49_GOOGLE_HANDOFF: prepared for exactly one approved job.
from google.colab import auth
import google.auth
from google.auth.transport.requests import AuthorizedSession
auth.authenticate_user()
_credentials, _ = google.auth.default()
_drive = AuthorizedSession(_credentials)
ROOT = Path('/content/m49/{job.id}')
ROOT.mkdir(parents=True, exist_ok=True)
_downloads = {downloads!r}
_outputs = {outputs!r}
for _name, _id in _downloads.items():
    _response = _drive.get(f'https://www.googleapis.com/drive/v3/files/{{_id}}?alt=media', timeout=120)
    _response.raise_for_status()
    _path = ROOT / _name
    _path.parent.mkdir(parents=True, exist_ok=True)
    _path.write_bytes(_response.content)
_publish_local = publish_drive_result
def publish_drive_result(root, request, bundle, timing, environment):
    # Re-running the last cell retries transmission of the same local result.
    if not (root/'result.ready.json').exists():
        _publish_local(root, request, bundle, timing, environment)
    for _name, _id in _outputs.items():
        _response = _drive.patch(f'https://www.googleapis.com/upload/drive/v3/files/{{_id}}?uploadType=media',
                                 data=(root/_name).read_bytes(), headers={{'Content-Type': 'application/octet-stream'}}, timeout=120)
        _response.raise_for_status()
    print('Đã gửi kết quả về M49. Quay lại web để tiếp tục.')
'''
    replaced = False
    for cell in notebook['cells']:
        cell['outputs'] = [] if cell['cell_type'] == 'code' else cell.get('outputs', [])
        if cell['cell_type'] != 'code':
            cell.pop('outputs', None)
            continue
        cell['execution_count'] = None
        source = ''.join(cell['source'])
        if "from google.colab import drive" in source:
            start = source.index('from google.colab import drive')
            end = source.index('request = load_drive_job', start)
            source = source[:start]+bootstrap+'\n'+source[end:]
            cell['source'] = source.splitlines(keepends=True)
            replaced = True
    if not replaced:
        raise ValueError('Notebook chưa hỗ trợ kết nối Google tự động')
    notebook['cells'][0]['source'] = [f'# M49 · {len(job.manifest)} mẫu · lượt {job.id}\n',
        'Bấm Runtime → Run all và cấp quyền Google bằng tài khoản đã kết nối M49.\n',
        'Ảnh/model được nạp tự động; kết quả gửi về web. Không sửa ROOT hay kéo tệp.\n',
        'Chỉ ảnh gốc và cấu hình model được chuyển; không có nhãn Manual/ground truth.\n']
    notebook.setdefault('metadata', {})['accelerator'] = 'GPU'
    return json.dumps(notebook, ensure_ascii=False).encode()


def sync_job(job):
    folder = Path(job.root)/job.id
    state_path = folder/'google.json'
    state = read_json(state_path)
    if not state:
        return
    if credentials()['account_id'] != state['account_id']:
        raise ValueError('Kết nối lại đúng tài khoản Google đã gửi lượt này')
    if not state['uploaded']:
        request = read_json(folder/'request.json')
        if request['model'].get('custom'):
            checkpoint = Path(job.root)/request['model']['checkpoint']
            with checkpoint.open('rb') as stream:
                actual_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual_hash != request['model']['sha256']:
                raise ValueError('Checkpoint trên máy đã thay đổi sau khi tạo lượt; cần khôi phục đúng tệp model.')
        keys = ['folder', 'assets', 'request', 'notebook'] + ['asset:'+n for n in job.manifest]
        keys += ['output:'+n for n in ('predictions.json', 'timing.json', 'environment.txt', 'result.ready.json')]
        if request['model'].get('custom'):
            keys += ['model']
        if not state['ids']:
            allocated = drive('GET', 'files/generateIds?'+urlencode(dict(count=len(keys), space='drive', type='files')))['ids']
            state['ids'] = dict(zip(keys, allocated, strict=True))
            write_json(state_path, state)
        ids = state['ids']
        upload_file(ids['folder'], 'M49-'+job.id, None, mime='application/vnd.google-apps.folder')
        upload_file(ids['assets'], 'assets', ids['folder'], mime='application/vnd.google-apps.folder')
        for name in job.manifest:
            upload_file(ids['asset:'+name], name, ids['assets'], folder/'assets'/name)
        upload_file(ids['request'], 'request.json', ids['folder'], folder/'request.json', 'application/json')
        if 'model' in ids:
            source = Path(job.root)/request['model']['checkpoint']
            upload_file(ids['model'], source.name, ids['folder'], source)
        placeholder = folder/'empty-output'
        placeholder.write_bytes(b'')
        for key in keys:
            if key.startswith('output:'):
                upload_file(ids[key], key[7:], ids['folder'], placeholder)
        notebook = folder/'run.ipynb'
        notebook.write_bytes(notebook_bytes(job, state, request))
        upload_file(ids['notebook'], 'M49-'+job.id+'.ipynb', ids['folder'], notebook, 'application/vnd.google.colaboratory')
        state['uploaded'] = True
        write_json(state_path, state)
    ids = state['ids']
    receipt = media(ids['output:result.ready.json'], 4096)
    if not receipt:
        job.status, job.error = 'awaiting_colab', None
        return
    marker = json.loads(receipt)
    if marker.get('job_id') != job.id:
        raise ValueError('Kết quả Google thuộc lượt khác')
    raw = media(ids['output:predictions.json'], 32*1024*1024)
    if hashlib.sha256(raw).hexdigest() != marker.get('sha256'):
        raise ValueError('Kết quả chưa tải lên đầy đủ; sẽ tự thử lại')
    # Publish locally only after checking the entire remote payload.
    (folder/'predictions.json').write_bytes(raw)
    (folder/'result.ready.json').write_bytes(receipt)
    job.error = None
