import json
import subprocess
import sys

import pytest
from aiohttp import CookieJar
from aiohttp.test_utils import TestClient, TestServer

from solarman_hub.auth import check_password, load_password, password_record, save_password
from solarman_hub.runtime import Runtime
from solarman_hub.web import admin_token, create_app


@pytest.fixture(scope='module')
def record():
    return password_record('żółć1234')


def test_password_is_salted_persisted_privately_and_checked(record, tmp_path):
    save_password(tmp_path, record)
    loaded = load_password(tmp_path)
    assert loaded == record
    assert check_password('żółć1234', loaded)
    assert not check_password('wrong test password', loaded)
    assert not check_password(None, loaded)
    assert not check_password('x' * 1025, loaded)
    assert password_record('żółć1234')['salt'] != record['salt']
    path = tmp_path / 'admin-password.json'
    assert path.stat().st_mode & 0o777 == 0o600
    assert 'żółć1234' not in path.read_text()
    with pytest.raises(ValueError):
        save_password(tmp_path, {**record, 'iterations': 1_000_000_000})
    assert load_password(tmp_path) == record


@pytest.mark.parametrize('contents', ['{}', '[]', 'not json', 'x' * 1025])
def test_corrupt_password_file_prevents_server_start(tmp_path, contents):
    (tmp_path / 'admin-password.json').write_text(contents)
    with pytest.raises(ValueError):
        create_app(Runtime(tmp_path))


async def test_password_login_and_recovery_token_survive_restart(record, tmp_path):
    token = admin_token(tmp_path)
    save_password(tmp_path, record)
    for _ in range(2):
        runtime = Runtime(tmp_path, tcp_host='127.0.0.1', tcp_port=0)
        async with TestClient(TestServer(create_app(runtime)), cookie_jar=CookieJar(unsafe=True)) as client:
            assert (await client.post('/api/login', json={'token': 'incorrect password'})).status == 401
            response = await client.post('/api/login', json={'token': 'żółć1234'})
            assert response.status == 200
            csrf = (await response.json())['csrf']
            assert (await client.get('/api/status')).status == 200
            public = await (await client.get('/api/config')).text()
            assert record['digest'] not in public and record['salt'] not in public
            assert (await client.post('/api/logout', json={}, headers={'X-CSRF-Token': csrf})).status == 200
            assert (await client.get('/api/status')).status == 401
            assert (await client.post('/api/login', json={'token': token})).status == 200
        assert admin_token(tmp_path) == token


def test_password_cli_import_does_not_print_password_or_hash(record, tmp_path):
    result = subprocess.run([sys.executable, '-m', 'solarman_hub', 'password',
                             '--data-dir', str(tmp_path), '--hash-stdin'],
                            input=json.dumps(record), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert load_password(tmp_path) == record
    assert record['digest'] not in result.stdout + result.stderr


def test_password_minimum_is_eight_characters():
    assert check_password('test1234', password_record('test1234'))
    with pytest.raises(ValueError):
        password_record('short12')
