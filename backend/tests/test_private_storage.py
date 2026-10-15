import os
import stat

import pytest

from app import colab_google as google, main


def test_failed_json_write_preserves_token_and_cleans_temporary_file(tmp_path):
    path = tmp_path/'token.json'
    google.write_json(path, {'refresh_token': 'original'})
    with pytest.raises(TypeError):
        google.write_json(path, {'refresh_token': object()})
    assert google.read_json(path) == {'refresh_token': 'original'}
    assert list(tmp_path.iterdir()) == [path]


def test_fixed_temporary_name_is_not_overwritten(tmp_path):
    legacy = tmp_path/'token.tmp'
    legacy.write_text('unrelated')
    google.write_json(tmp_path/'token.json', {'refresh_token': 'replacement'})
    assert legacy.read_text() == 'unrelated'
    assert google.read_json(tmp_path/'token.json')['refresh_token'] == 'replacement'


@pytest.mark.skipif(os.name != 'posix', reason='POSIX mode bits; Windows uses inherited ACLs')
def test_existing_credentials_permissions_are_repaired(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'STORAGE', tmp_path)
    folder = tmp_path/'google-colab'
    folder.mkdir()
    folder.chmod(0o755)
    for name in ('client.json', 'token.json'):
        path = folder/name
        path.write_text('{}')
        path.chmod(0o644)
    google.private_dir()
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    for name in ('client.json', 'token.json'):
        assert stat.S_IMODE((folder/name).stat().st_mode) == 0o600
    google.write_json(folder/'token.json', {'refresh_token': 'new'})
    assert stat.S_IMODE((folder/'token.json').stat().st_mode) == 0o600
