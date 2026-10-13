import hashlib
import json
from pathlib import Path
import time
import runpy
import sys
from types import ModuleType
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app import colab_google as google, colab_sync
from app.models import ColabJob
from test_api import client, project, upload_image, bundle
from test_datasets_sync import db_session


def configure(client):
    payload = {'installed': {'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'private-client-secret'}}
    response = client.post('/api/colab/google/client', files={'file': ('client.json', json.dumps(payload))})
    assert response.status_code == 200, response.text
    return payload['installed']


def test_google_error_only_exposes_known_reasons():
    raw = json.dumps({'error': {'message': 'secret-access-token', 'details': [{'reason': 'SERVICE_DISABLED'}]}}).encode()
    error = google.google_error(403, raw)
    assert error.reason == 'SERVICE_DISABLED'
    assert 'chưa được bật' in str(error)
    assert 'secret' not in str(error)
    assert 'secret' not in str(google.google_error(400, b'{"error":"secret-client-value"}'))
    assert 'HTTP 502' in str(google.google_error(502, b'not json'))


def test_callback_identifies_disabled_drive_api_without_leaking_tokens(client, monkeypatch):
    configure(client)
    url = client.post('/api/colab/google/connect').json()['url']
    state = parse_qs(urlparse(url).query)['state'][0]
    monkeypatch.setattr(google, 'token_request', lambda values: dict(access_token='secret', refresh_token='secret', expires_in=3600, scope=google.SCOPE))
    def disabled(*args, **kwargs):
        raise google.GoogleError(403, 'SERVICE_DISABLED')
    monkeypatch.setattr(google, 'http', disabled)
    response = client.get('/api/colab/google/callback', params={'state':state,'code':'private-code'})
    assert response.status_code == 400
    assert 'Kiểm tra tài khoản Google Drive' in response.json()['detail']
    assert 'chưa được bật' in response.json()['detail']
    assert 'secret' not in response.text and 'private-code' not in response.text
    assert not client.get('/api/colab/google/status').json()['connected']


def connected():
    google.write_json(google.private_dir()/'token.json', {
        'access_token': 'private-access-token', 'refresh_token': 'private-refresh-token',
        'expires_at': time.time()+3600, 'account_id': 'account-one', 'scope': google.SCOPE})


def test_oauth_pkce_one_use_state_and_private_tokens(client, monkeypatch):
    configure(client)
    result = client.post('/api/colab/google/connect').json()
    query = parse_qs(urlparse(result['url']).query)
    assert query['scope'] == [google.SCOPE]
    assert query['redirect_uri'] == [google.REDIRECT]
    assert query['code_challenge_method'] == ['S256']
    assert 'client_secret' not in query
    state = query['state'][0]
    observed = []
    def token(values):
        observed.append(values)
        return dict(access_token='secret-access', refresh_token='secret-refresh', expires_in=3600, scope=google.SCOPE)
    monkeypatch.setattr(google, 'token_request', token)
    monkeypatch.setattr(google, 'http', lambda *a, **kw: (b'{"user":{"permissionId":"account-one"}}', {}))
    assert client.get('/api/colab/google/callback', params={'state': 'forged', 'code': 'code'}).status_code == 400
    assert not observed
    response = client.get('/api/colab/google/callback', params={'state': state, 'code': 'code'})
    assert response.status_code == 200
    verifier = observed[0]['code_verifier']
    challenge = google.base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    assert challenge == query['code_challenge'][0]
    assert client.get('/api/colab/google/callback', params={'state': state, 'code': 'code'}).status_code == 400
    public = client.get('/api/colab/google/status')
    assert public.json()['connected']
    assert 'secret' not in public.text and 'secret' not in response.text
    assert client.post('/api/colab/google/disconnect').json()['connected'] is False


def test_oauth_denial_expiry_scope_and_cross_origin(client, monkeypatch):
    configure(client)
    assert client.post('/api/colab/google/connect', headers={'Origin': 'https://attacker.invalid'}).status_code == 403
    def begin():
        return parse_qs(urlparse(client.post('/api/colab/google/connect').json()['url']).query)['state'][0]
    state = begin()
    assert client.get('/api/colab/google/callback', params={'state': state, 'error': 'access_denied'}).status_code == 400
    state = begin()
    google.PENDING[state] = (time.time()-1, 'verifier')
    assert client.get('/api/colab/google/callback', params={'state': state, 'code': 'code'}).status_code == 400
    state = begin()
    monkeypatch.setattr(google, 'token_request', lambda values: dict(access_token='secret', refresh_token='secret', expires_in=3600, scope='email'))
    assert client.get('/api/colab/google/callback', params={'state': state, 'code': 'code'}).status_code == 400
    assert not client.get('/api/colab/google/status').json()['connected']


def test_refresh_revoked_connection_requires_new_consent(client, monkeypatch):
    configure(client)
    connected()
    path = google.private_dir()/'token.json'
    token = google.read_json(path)
    token['expires_at'] = 0
    google.write_json(path, token)
    def revoked(values):
        raise google.GoogleError(400)
    monkeypatch.setattr(google, 'token_request', revoked)
    with pytest.raises(google.GoogleError):
        google.credentials()
    assert not client.get('/api/colab/google/status').json()['connected']


def google_job(client):
    connected()
    pid = project(client)
    asset = upload_image(client, pid).json()['id']
    for session in db_session():
        value = colab_sync.export_job(pid, colab_sync.JobCreate(asset_ids=[asset]), session, google=True)
        job = session.get(ColabJob, value['id'])
        session.expunge(job)
    return job


def fake_drive(monkeypatch):
    files, allocated = {}, []
    def drive(method, path, value=None, **kwargs):
        assert path.startswith('files/generateIds?')
        count = int(parse_qs(path.split('?')[1])['count'][0])
        ids = ['file-'+str(i) for i in range(count)]
        allocated.append(ids)
        return {'ids': ids}
    def upload(file_id, name, parent, source=None, mime=None):
        files.setdefault(file_id, (name, source.read_bytes() if source else b''))
    monkeypatch.setattr(google, 'drive', drive)
    monkeypatch.setattr(google, 'upload_file', upload)
    monkeypatch.setattr(google, 'media', lambda file_id, limit: files[file_id][1])
    return files, allocated


def test_upload_retry_notebook_binding_and_result_validation(client, monkeypatch):
    job = google_job(client)
    files, allocated = fake_drive(monkeypatch)
    folder = Path(job.root)/job.id
    google.sync_job(job)
    assert job.status == 'awaiting_colab'
    info = google.job_info(job)
    assert info['transport'] == 'google' and info['colab_url'].startswith('https://colab.research.google.com/drive/')
    state = google.read_json(folder/'google.json')
    notebook = json.loads(files[state['ids']['notebook']][1])
    text = json.dumps(notebook)
    assert 'PASTE_JOB_ID' not in text and 'drive.mount' not in text
    assert 'private-access-token' not in text and 'private-refresh-token' not in text
    assert job.id in text and 'auth.authenticate_user()' in text
    assert {name for name, _ in files.values()} >= {'assets', 'demo.png', 'request.json', 'predictions.json'}
    request = json.loads(files[state['ids']['request']][1])
    assert set(request) == {'job_id','project_id','task','classes','manifest','sha256','model'}
    for cell in notebook['cells']:
        source = ''.join(cell['source'])
        if cell['cell_type'] == 'code' and not source.startswith('%'):
            compile(source, 'generated.ipynb', 'exec')
    # Simulate restart after uploading half the files. Reserved IDs are reused.
    state['uploaded'] = False
    google.write_json(folder/'google.json', state)
    count = len(files)
    google.sync_job(job)
    assert len(files) == count and len(allocated) == 1
    payload = bundle()
    payload['run'] = dict(model='fixture', inference_seconds=1.25)
    raw = json.dumps(payload).encode()
    ids = state['ids']
    files[ids['output:predictions.json']] = ('predictions.json', raw)
    files[ids['output:result.ready.json']] = ('result.ready.json', json.dumps({'job_id': 'wrong', 'sha256': hashlib.sha256(raw).hexdigest()}).encode())
    with pytest.raises(ValueError, match='khác'):
        google.sync_job(job)
    assert not (folder/'result.ready.json').exists()
    files[ids['output:result.ready.json']] = ('result.ready.json', json.dumps({'job_id': job.id, 'sha256': 'wrong'}).encode())
    with pytest.raises(ValueError, match='đầy đủ'):
        google.sync_job(job)
    files[ids['output:result.ready.json']] = ('result.ready.json', json.dumps({'job_id': job.id, 'sha256': hashlib.sha256(raw).hexdigest()}).encode())
    google.sync_job(job)
    for session in db_session():
        saved = session.get(ColabJob, job.id)
        colab_sync.import_ready(saved, session)
        assert saved.status == 'imported' and saved.label_set_id


def test_different_google_account_cannot_receive_pending_job(client, monkeypatch):
    job = google_job(client)
    monkeypatch.setattr(google, 'credentials', lambda: {'account_id': 'someone-else'})
    with pytest.raises(ValueError, match='đúng tài khoản'):
        google.sync_job(job)


@pytest.mark.parametrize('task', ['detection_2d', 'instance_segmentation'])
def test_generated_notebook_supports_custom_model_without_editing(task):
    job = SimpleNamespace(id='job-id', manifest=['image.png'])
    state = {'ids': {'request':'request-id', 'asset:image.png':'image-id', 'model':'model-id',
                    **{'output:'+name:'output-'+str(i) for i,name in enumerate(['predictions.json','timing.json','environment.txt','result.ready.json'])}}}
    request = {'task': task, 'manifest': job.manifest, 'model': {'custom': True, 'checkpoint': 'models/model.pt'}}
    notebook = json.loads(google.notebook_bytes(job, state, request))
    text = json.dumps(notebook)
    assert '../models/model.pt' in text and 'model-id' in text
    assert 'PASTE_JOB_ID' not in text
    for cell in notebook['cells']:
        source = ''.join(cell['source'])
        if cell['cell_type'] == 'code' and not source.startswith('%'):
            compile(source, 'generated.ipynb', 'exec')


def test_upload_uses_reserved_id_and_chunks(client, monkeypatch, tmp_path):
    connected()
    content = tmp_path/'model.pt'
    content.write_bytes(b'x'*(8*1024*1024+7))
    def missing(*args, **kwargs):
        raise google.GoogleError(404)
    monkeypatch.setattr(google, 'drive', missing)
    calls = []
    def fake_http(method, url, data=None, headers=None, **kwargs):
        calls.append((method, url, len(data), headers, json.loads(data) if method == 'POST' else None))
        return b'{}', {'Location': 'https://www.googleapis.com/upload/session'}
    monkeypatch.setattr(google, 'http', fake_http)
    google.upload_file('reserved-id', 'model.pt', 'folder-id', content)
    assert calls[0][4]['id'] == 'reserved-id'
    assert [c[2] for c in calls[1:]] == [8*1024*1024, 7]
    assert calls[-1][3]['Content-Range'] == f'bytes {8*1024*1024}-{content.stat().st_size-1}/{content.stat().st_size}'


def test_notebook_downloads_selected_files_and_retries_result_transfer(tmp_path, monkeypatch):
    job = SimpleNamespace(id='selected-job', manifest=['demo.png'])
    output_names = ['predictions.json','timing.json','environment.txt','result.ready.json']
    ids = {'request':'request-id','asset:demo.png':'image-id', **{'output:'+n:n for n in output_names}}
    request = {'task':'detection_2d','manifest':job.manifest,'model':{},'job_id':job.id,
               'sha256':{'demo.png':hashlib.sha256(b'image').hexdigest()}}
    notebook = json.loads(google.notebook_bytes(job, {'ids':ids}, request))
    config = next(''.join(c['source']) for c in notebook['cells'] if '# M49_GOOGLE_HANDOFF' in ''.join(c['source']))
    bootstrap = config[config.index('# M49_GOOGLE_HANDOFF'):config.index('request = load_drive_job')]
    local_root = tmp_path/job.id
    bootstrap = bootstrap.replace("Path('/content/m49/selected-job')", f'Path({str(local_root)!r})')
    downloads, uploads, auth_calls = [], [], []
    fail = [True]
    class Response:
        def __init__(self, content): self.content = content
        def raise_for_status(self): pass
    class Drive:
        def get(self, url, **kw):
            file_id = url.split('/files/')[1].split('?')[0]
            downloads.append(file_id)
            return Response({'request-id':json.dumps(request).encode(),'image-id':b'image'}[file_id])
        def patch(self, url, data, **kw):
            name = url.split('/files/')[1].split('?')[0]
            if name == 'timing.json' and fail[0]:
                fail[0] = False
                raise RuntimeError('network failure')
            uploads.append((name, data))
            return Response(b'')
    modules = {name:ModuleType(name) for name in ['google','google.colab','google.colab.auth','google.auth','google.auth.transport','google.auth.transport.requests']}
    modules['google'].auth = modules['google.auth']
    modules['google.colab'].auth = modules['google.colab.auth']
    modules['google.colab.auth'].authenticate_user = lambda: auth_calls.append(True)
    modules['google.auth'].default = lambda: ('credentials',None)
    modules['google.auth.transport.requests'].AuthorizedSession = lambda credentials: Drive()
    for name, module in modules.items(): monkeypatch.setitem(sys.modules,name,module)
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[2]/'colab/drive_transport.py'))
    namespace = {'Path':Path, 'publish_drive_result':helpers['publish_drive_result']}
    exec(compile(bootstrap, 'handoff', 'exec'), namespace)
    assert downloads == ['request-id','image-id'] and auth_calls == [True]
    assert helpers['load_drive_job'](local_root,'detection_2d') == request
    payload = bundle()
    with pytest.raises(RuntimeError, match='network failure'):
        namespace['publish_drive_result'](local_root,request,payload,{},'fixture')
    assert 'result.ready.json' not in [name for name, _ in uploads]
    namespace['publish_drive_result'](local_root,request,payload,{},'fixture')
    assert [name for name, _ in uploads][-4:] == output_names
    assert json.loads(uploads[-1][1])['sha256'] == hashlib.sha256(uploads[-4][1]).hexdigest()
