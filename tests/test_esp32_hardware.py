"""Opt-in bench tests. Require a spare ESP32 with cloud forwarding DISABLED.

HUB_TEST_ESP_CREDENTIALS=/private/device.json pytest tests/test_esp32_hardware.py
Add HUB_TEST_ESP_OTA=1 only to authorize writing the bundled OTA image.
The private JSON contains ip and admin_password; never put it in the repository.
"""
import base64
import json
import os
from pathlib import Path
import socket
import struct
import time
import urllib.error
import urllib.request

import pytest
from solarman_hub.protocol import Frame

pytestmark = pytest.mark.skipif(not os.environ.get('HUB_TEST_ESP_CREDENTIALS'), reason='Opt-in ESP32 bench hardware')
FIXTURE = Path(__file__).parent/'fixtures/sofar-report.hex'


class PrivateHeaders(bytes):
    def __repr__(self):
        return "<private HTTP headers>"


class Bench:
    def __init__(self, private):
        self.host = private['ip']
        self.auth = 'Basic '+base64.b64encode(('admin:'+private['admin_password']).encode()).decode()
        self.csrf = ''

    def api(self, path, data=None):
        request = urllib.request.Request('http://'+self.host+path,
            data=None if data is None else json.dumps(data).encode(),
            headers={'Authorization': self.auth, 'Content-Type': 'application/json', 'X-Companion-Token': self.csrf})
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.load(response)
        if path=='/api/status':
            self.csrf = result['csrf']
        return result

    def header(self, path, length, authorized=True, mime='application/json', extra=''):
        return PrivateHeaders((f'POST {path} HTTP/1.1\r\nHost: {self.host}\r\nContent-Type: {mime}\r\n'
            f'Content-Length: {length}\r\nConnection: close\r\n'+
            (f'Authorization: {self.auth}\r\nX-Companion-Token: {self.csrf}\r\n' if authorized else '')+extra+'\r\n').encode())

    def request(self, header, body=b''):
        with socket.create_connection((self.host,80), timeout=5) as connection:
            connection.settimeout(40 if len(body)>65536 else 6)
            connection.sendall(header+body)
            response=b''
            while True:
                try:part=connection.recv(4096)
                except ConnectionResetError:break
                if not part:break
                response+=part
        assert response.startswith(b'HTTP/1.'), 'Missing HTTP response'
        return int(response.split(b' ',2)[1])

    def ack(self):
        start=time.monotonic()
        with socket.create_connection((self.host,10000), timeout=1) as connection:
            connection.settimeout(1)
            connection.sendall(bytes.fromhex(FIXTURE.read_text()))
            response=b''
            while len(response)<23:
                response+=connection.recv(23-len(response))
        ack=Frame.parse(response)
        assert ack.code==0x1210 and ack.serial==1234567890
        assert time.monotonic()-start<1, 'HTTP request stalled the V5 receiver'

    def wait_boot(self, old_csrf):
        end=time.monotonic()+30
        while time.monotonic()<end:
            try:
                status=self.api('/api/status')
                if status['csrf']!=old_csrf:
                    self.api('/api/time',{'unix':int(time.time())})
                    return status
            except (OSError,ValueError):
                pass
            time.sleep(.3)
        raise AssertionError('ESP32 did not restart successfully')


@pytest.fixture(scope='module')
def bench():
    value=Bench(json.loads(Path(os.environ['HUB_TEST_ESP_CREDENTIALS']).read_text()))
    status=value.api('/api/status');config=value.api('/api/config')
    assert status['mode']=='receiver' and not status['logger_connected'], 'Use an idle bench ESP32'
    assert not config['upstream_enabled'], 'Never send synthetic data to a real upstream'
    assert config['allowed_serial'] in (0,1234567890), 'Use the synthetic serial or learn-first mode'
    value.api('/api/time',{'unix':int(time.time())})
    return value


def test_slow_headers_do_not_block_v5(bench):
    with socket.create_connection((bench.host,80), timeout=2) as connection:
        connection.sendall(b'GET /api/status HTTP/1.1\r\nHost:')
        bench.ack()
        time.sleep(.7)
        response=connection.recv(1024)
        assert b'408' in response
    bench.ack()


@pytest.mark.parametrize('path,length,mime,extra,authorized,expected',[
    ('/update',100000,'multipart/form-data; boundary=bench','',False,401),
    ('/api/config',3000000,'application/json','',True,413),
    ('/api/config',10,'application/json','Content-Length: 11\r\n',True,400),
    ('/api/config',10,'text/plain','',True,415),
    ('/api/config',4096,'application/json','',True,413),
    ('/api/time',2,'application/json','X-Companion-Token: other\r\n',True,400),
])
def test_preflight_rejects_before_body_and_receiver_survives(bench,path,length,mime,extra,authorized,expected):
    # No body is supplied: waiting for it would fail the six-second deadline.
    assert bench.request(bench.header(path,length,authorized,mime,extra))==expected
    bench.ack()



def test_peer_resets_do_not_poison_following_http_or_v5(bench):
    for _ in range(10):
        with socket.create_connection((bench.host,80),timeout=2) as connection:
            connection.sendall(b'GET /api/status HTTP/1.1\r\nHost: bench\r\n\r\n')
            connection.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0))
        time.sleep(.02)
        assert bench.api('/api/status')['mode']=='receiver'
        bench.ack()

def multipart_prefix():
    return b'--bench\r\nContent-Disposition: form-data; name="firmware"; filename="firmware.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'


def test_incomplete_upload_times_out_and_restores_v5(bench):
    with socket.create_connection((bench.host,80),timeout=3) as connection:
        connection.sendall(bench.header('/update',100000,True,'multipart/form-data; boundary=bench')+
                           multipart_prefix()+b'\xe9'+b'\0'*4095)
        time.sleep(3.5)
        assert b'408' in connection.recv(4096)
    bench.ack()


@pytest.mark.parametrize('tail',[
    b'\r\n--bench\r\nContent-Disposition: form-data; name="extra"\r\n\r\nvalue\r\n--bench--\r\n',
    b'\r\n--bench--\r\ntrailing-epilogue',
])
def test_extra_multipart_parts_or_epilogue_never_commit(bench,tail):
    body=multipart_prefix()+b'\xe9'+b'\0'*4095+tail
    assert bench.request(bench.header('/update',len(body),True,'multipart/form-data; boundary=bench'),body)==400
    bench.ack()


@pytest.mark.skipif(os.environ.get('HUB_TEST_ESP_OTA')!='1',reason='Explicitly opt in to writing bench OTA flash')
@pytest.mark.parametrize('ending',[b'--',b'--\r\n'])
def test_complete_ota_accepts_both_legal_endings(bench,ending):
    image=(Path(__file__).resolve().parents[1]/'firmware/esp32-companion/dist/firmware.bin').read_bytes()
    body=multipart_prefix()+image+b'\r\n--bench'+ending
    old=bench.csrf
    assert bench.request(bench.header('/update',len(body),True,'multipart/form-data; boundary=bench'),body)==200
    status=bench.wait_boot(old)
    assert status['mode']=='receiver' and status['connected']
    assert not bench.api('/api/config')['upstream_enabled']
    bench.ack()
