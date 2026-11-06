import json
from pathlib import Path
import pytest
from aiohttp import CookieJar
from aiohttp.test_utils import TestClient, TestServer
from solarman_hub.runtime import Runtime
from solarman_hub.web import create_app

@pytest.fixture
async def client(tmp_path):
    runtime = Runtime(tmp_path, tcp_host='127.0.0.1', tcp_port=0)
    async with TestClient(TestServer(create_app(runtime)), cookie_jar=CookieJar(unsafe=True)) as client:
        client.runtime = runtime
        client.token = (tmp_path/'admin-token.txt').read_text().strip()
        yield client

async def login(client):
    response = await client.post('/api/login', json={'token': client.token})
    assert response.status == 200
    return {'X-CSRF-Token': (await response.json())['csrf']}

async def test_auth_csrf_origin_and_secret_preservation(client):
    assert (await client.get('/api/status')).status == 401
    assert (await client.get('/api/archive/frames')).status == 401
    assert (await client.get('/health')).status == 200
    assert (await client.post('/api/login', json={'token': 'żółć'})).status == 401
    headers = await login(client)
    assert (await client.post('/api/apply', json={})).status == 403
    assert (await client.post('/api/apply', json={}, headers={**headers,'Origin':'http://evil.invalid'})).status == 403
    value = await (await client.get('/api/config')).json()
    value['config']['mqtt']['password'] = 'private-test-password'
    assert (await client.put('/api/config', json=value, headers=headers)).status == 200
    current = await (await client.get('/api/config')).json()
    assert 'private-test-password' not in json.dumps(current)
    assert current['config']['mqtt']['password_set'] is True
    current['config']['mqtt']['password'] = ''
    assert (await client.put('/api/config', json=current, headers=headers)).status == 200
    assert client.runtime.store.load().mqtt.password == 'private-test-password'
    current = await (await client.get('/api/config')).json()
    value['revision'] = current['revision']
    current['config']['mqtt']['clear_password'] = True
    assert (await client.put('/api/config', json=current, headers=headers)).status == 200
    assert client.runtime.store.load().mqtt.password == ''
    assert (await client.put('/api/config', json=value, headers=headers)).status == 409

async def test_profiles_preview_docs_and_bad_requests(client):
    headers = await login(client)
    profile = (await (await client.get('/api/profiles')).json())['profiles'][0]
    definition = {key:value for key,value in profile.items() if key not in ('builtin','revision')}
    assert (await client.post('/api/profiles', json=definition, headers=headers)).status == 400
    definition['id'] = 'test-custom'
    assert (await client.post('/api/profiles', json=definition, headers=headers)).status == 200
    fixture = Path(__file__).parent/'fixtures'/'sofar-report.hex'
    response = await client.post('/api/preview', json={'profile':definition,'hex':fixture.read_text()}, headers=headers)
    assert response.status == 200
    assert len((await response.json())['values']) == 48
    assert (await client.delete('/api/profiles/test-custom', json={}, headers=headers)).status == 200
    assert (await client.post('/api/preview', json={}, headers=headers)).status == 400
    assert (await client.post('/api/login', json=[])).status == 400
    assert 'Solarman Hub' in (await (await client.get('/api/docs')).json())['html']
    for name in ('app.js','style.css','icon.svg'):
        assert (await client.get('/static/'+name)).status == 200
    assert (await client.get('/static/config.json')).status == 404
    assert (await client.get('/api/archive/unknown')).status == 404

async def test_bearer_and_config_revision_apply(client):
    headers = {'Authorization':'Bearer '+client.token}
    value = await (await client.get('/api/config', headers=headers)).json()
    value['config']['cloud']['enabled'] = False
    assert (await client.put('/api/config', json=value, headers=headers)).status == 200
    status = await (await client.get('/api/status', headers=headers)).json()
    assert status['saved_revision'] != status['applied_revision']
    assert (await client.post('/api/apply', json={}, headers=headers)).status == 200
    status = await (await client.get('/api/status', headers=headers)).json()
    assert status['saved_revision'] == status['applied_revision']
    assert status['cloud']['enabled'] is False
    assert client.token not in json.dumps(status)


@pytest.mark.parametrize("content", ["", "short"])
def test_corrupt_token_fails_closed(tmp_path, monkeypatch, content):
    from solarman_hub.web import admin_token
    monkeypatch.delenv("HUB_ADMIN_TOKEN", raising=False)
    (tmp_path/"admin-token.txt").write_text(content)
    with pytest.raises(ValueError):
        admin_token(tmp_path)


def test_token_persistence_and_permissions(tmp_path, monkeypatch):
    from solarman_hub.web import admin_token
    monkeypatch.delenv("HUB_ADMIN_TOKEN", raising=False)
    token = admin_token(tmp_path)
    timestamp = (tmp_path/"admin-token.txt").stat().st_mtime_ns
    assert admin_token(tmp_path) == token
    assert (tmp_path/"admin-token.txt").stat().st_mtime_ns == timestamp
    assert (tmp_path/"admin-token.txt").stat().st_mode & 0o777 == 0o600


async def test_history_bundle_and_firmware_api(client):
    from test_bundles_guides import bundle
    from test_history import sample
    import time
    for path in ('/api/history/123','/api/firmware/firmware.bin'):
        assert (await client.get(path)).status==401
    headers=await login(client)
    assert (await client.get('/api/history/123')).status==404
    value=bundle(client.runtime).model_dump()
    response=await client.post('/api/import/preview',json=value,headers=headers)
    assert response.status==200
    summary=await response.json()
    payload={'bundle':value,'revision':summary['revision']}
    assert (await client.post('/api/import',json=payload,headers=headers)).status==200
    assert (await client.post('/api/import',json=payload,headers=headers)).status==409
    assert client.runtime.active.loggers==[]
    await client.runtime.apply()
    store=client.runtime.history;store.initialize()
    row=sample(1,time.time()-10);row['serial']=1234567890
    store.write(row)
    result=await (await client.get('/api/history/1234567890')).json()
    assert len(result['samples'])==1
    assert (await client.get('/api/history/1234567890?from=nan')).status==400
    for language in ('en','pl','de','fr','cs','sk','lt','uk','ru'):
        guide=await (await client.get('/api/docs?lang='+language)).json()
        assert guide['language']==language and len(guide['toc'])==10
    assert (await client.get('/api/docs?lang=invalid')).status==400
    artifact=await client.get('/api/firmware/firmware.bin')
    assert artifact.status==200 and (await artifact.read())[0]==0xe9
    assert (await client.get('/api/firmware/other.bin')).status==404


async def test_mqtt_failure_uses_standard_error_response(client, monkeypatch):
    from solarman_hub import mqtt_probe

    async def failed_probe(settings):
        return {'ok': False, 'message': 'Could not connect to the MQTT broker.'}

    monkeypatch.setattr(mqtt_probe, 'probe', failed_probe)
    headers = await login(client)
    config = (await (await client.get('/api/config')).json())['config']
    response = await client.post('/api/mqtt/test', json={'config': config}, headers=headers)
    assert response.status == 400
    result = await response.json()
    assert result['error'] == result['message'] == 'Could not connect to the MQTT broker.'
    assert result['ok'] is False
