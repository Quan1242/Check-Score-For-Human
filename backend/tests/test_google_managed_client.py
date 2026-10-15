import json
from urllib.parse import parse_qs, urlparse

import pytest

from app import colab_google as google
from test_api import client


@pytest.mark.parametrize('wrapped', [False, True])
def test_operator_client_allows_user_consent_without_upload(client, tmp_path, monkeypatch, wrapped):
    config = dict(client_id='operator.apps.googleusercontent.com', client_secret='private-operator-secret')
    path = tmp_path/'managed-client.json'
    path.write_text(json.dumps({'installed': config} if wrapped else config))
    monkeypatch.setenv('M49_GOOGLE_CLIENT_FILE', str(path))
    status = client.get('/api/colab/google/status')
    assert status.json()['configured'] is True
    assert 'secret' not in status.text
    assert not (google.private_dir()/'client.json').exists()
    run_id = '11111111-1111-4111-8111-111111111111'
    response = client.post('/api/colab/google/connect', params={'run_id': run_id})
    assert response.status_code == 200
    query = parse_qs(urlparse(response.json()['url']).query)
    assert query['client_id'] == [config['client_id']]
    assert 'client_secret' not in query
    observed = []
    def token(values):
        observed.append(values)
        return dict(access_token='user-access', refresh_token='user-refresh', expires_in=3600, scope=google.SCOPE)
    monkeypatch.setattr(google, 'token_request', token)
    monkeypatch.setattr(google, 'http', lambda *a, **kw: (b'{"user":{"permissionId":"user-account"}}', {}))
    response = client.get('/api/colab/google/callback', params={'state': query['state'][0], 'code': 'code'})
    assert response.status_code == 200
    assert observed[0]['client_secret'] == config['client_secret']
    assert '/api/guided/'+run_id in response.text
    assert 'window.location.replace' in response.text
    assert config['client_secret'] not in response.text
    assert google.credentials()['account_id'] == 'user-account'
    assert client.get('/api/colab/google/status').json()['connected'] is True
    assert client.post('/api/colab/google/client', files={'file': ('client.json', '{}')}).status_code == 409
    assert client.post('/api/colab/google/disconnect').json() == dict(configured=True, connected=False, scope=google.SCOPE)
    assert path.is_file()


@pytest.mark.parametrize('raw', [None, 'invalid-json', '{"installed": {}}', '{"web": {"client_id": "test"}}'])
def test_missing_or_invalid_managed_client_is_reported_without_leaking_config(client, tmp_path, monkeypatch, raw):
    path = tmp_path/'managed-client.json'
    if raw is not None:
        path.write_text(raw)
    monkeypatch.setenv('M49_GOOGLE_CLIENT_FILE', str(path))
    assert client.get('/api/colab/google/status').json()['configured'] is False
    response = client.post('/api/colab/google/connect')
    assert response.status_code == 503
    assert str(path) not in response.text


def test_fresh_install_uses_bundled_client_without_sharing_user_tokens(client, tmp_path, monkeypatch):
    path = tmp_path/'bundled-client.json'
    path.write_text(json.dumps({'installed': dict(client_id='shared.apps.googleusercontent.com', client_secret='desktop-config')}))
    monkeypatch.setattr(google, 'BUNDLED_CLIENT', path)
    status = client.get('/api/colab/google/status').json()
    assert status['configured'] is True and status['connected'] is False
    response = client.post('/api/colab/google/connect')
    query = parse_qs(urlparse(response.json()['url']).query)
    assert query['client_id'] == ['shared.apps.googleusercontent.com']
    assert not (google.private_dir()/'token.json').exists()
    google.write_json(google.private_dir()/'client.json', dict(client_id='local.apps.googleusercontent.com', client_secret='override'))
    assert google.oauth_client()['client_id'] == 'local.apps.googleusercontent.com'
