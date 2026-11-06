"""Regression coverage for transport, MQTT, timestamps and archive behavior."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, StrictUndefined
import paho.mqtt.client as paho
import pytest

from solarman_hub.archive import Archive
from solarman_hub.config import AppConfig, ConfigStore, Logger, Storage, atomic_json
from solarman_hub.mqtt import Publisher
from solarman_hub.profiles import ProfileStore
from solarman_hub.protocol import Frame, local_ack
from solarman_hub.relay import CloudLink, Session
from solarman_hub.runtime import Runtime
from test_backend import SERIAL, frame

FIXTURE = Path(__file__).parent/'fixtures/sofar-report.hex'


def test_home_assistant_templates_render_all_measurements(tmp_path):
    publisher = Publisher(tmp_path, lambda *a, **kw: None)
    logger = Logger(serial=SERIAL)
    sample = ProfileStore(tmp_path).load()[logger.profile].decode(Frame.parse(bytes.fromhex(FIXTURE.read_text())), 'UTC')
    state = {'values': {key: field['value'] for key, field in sample['values'].items()}}
    environment = Environment(undefined=StrictUndefined)
    configs = publisher.discovery(logger, sample)
    assert len(configs) == 48
    for topic, config in configs.items():
        key = topic.split('/')[-2]
        result = environment.from_string(config['value_template']).render(value_json=state)
        assert float(result) == pytest.approx(state['values'][key])


class WaitingWriter:
    def __init__(self, reader=None):
        self.reader = reader
        self.entered = asyncio.Event()
        self.gate = asyncio.Event()
        self.closed = False

    def close(self):
        if not self.closed and self.reader:
            self.reader.feed_eof()
        self.closed = True

    async def wait_closed(self):
        self.entered.set()
        await self.gate.wait()

    async def drain(self):
        pass

    def write(self, raw):
        pass

    def get_extra_info(self, name):
        return ('127.0.0.1', 12345)


async def test_repeated_stop_releases_logger_identity(tmp_path):
    config = AppConfig(loggers=[Logger(serial=SERIAL)])
    config.cloud.enabled = False
    ConfigStore(tmp_path).save(config)
    runtime = Runtime(tmp_path)
    reader = asyncio.StreamReader()
    writer = WaitingWriter(reader)
    session = Session(runtime, reader, writer)
    running = asyncio.create_task(session.run())
    reader.feed_data(frame().raw)
    async with asyncio.timeout(1):
        while SERIAL not in runtime.sessions:
            await asyncio.sleep(0)
    first = asyncio.create_task(session.stop())
    await asyncio.wait_for(writer.entered.wait(), 1)
    second = asyncio.create_task(session.stop())
    await asyncio.sleep(0)
    writer.gate.set()
    await asyncio.wait_for(asyncio.gather(first, second, running, return_exceptions=True), 1)
    assert SERIAL not in runtime.sessions
    assert not runtime.states[SERIAL]['connected']
    # The same serial can identify again without restarting the Hub.
    replacement_reader = asyncio.StreamReader()
    replacement_writer = WaitingWriter(replacement_reader)
    replacement_writer.gate.set()
    replacement = Session(runtime, replacement_reader, replacement_writer)
    await replacement.identify(frame())
    replacement.worker.cancel()
    await asyncio.gather(replacement.worker, return_exceptions=True)


async def test_cloud_close_does_not_touch_replacement_futures():
    session = SimpleNamespace(state={'cloud_connected': True})
    link = CloudLink(session)
    old_writer = WaitingWriter()
    link.writer = old_writer
    old = asyncio.get_running_loop().create_future()
    link.pending[(0x1110, 1)] = old
    closing = asyncio.create_task(link.close())
    await asyncio.wait_for(old_writer.entered.wait(), 1)
    replacement = asyncio.get_running_loop().create_future()
    link.pending[(0x1210, 2)] = replacement
    old_writer.gate.set()
    await closing
    with pytest.raises(ConnectionError):
        await old
    assert not replacement.done()
    assert link.pending[(0x1210, 2)] is replacement
    replacement.cancel()


async def test_cloud_waits_for_bootstrap_before_becoming_ready(monkeypatch):
    config = AppConfig()
    session = SimpleNamespace(config=config, state={}, logger=Logger(serial=SERIAL),
                              sequence=0, event=lambda *a, **kw: None)
    link = CloudLink(session)
    reader, writer = asyncio.StreamReader(), WaitingWriter()
    writer.gate.set()
    entered, release = asyncio.Event(), asyncio.Event()

    async def connect(*args):
        return reader, writer

    async def bootstrap(upload):
        entered.set()
        await release.wait()
        return local_ack(upload, 77, 'UTC')

    monkeypatch.setattr(asyncio, 'open_connection', connect)
    monkeypatch.setattr(link, 'exchange', bootstrap)
    link.handshake = frame()
    first = asyncio.create_task(link.ensure(frame(0x4710)))
    await asyncio.wait_for(entered.wait(), 1)
    second = asyncio.create_task(link.ensure(frame(0x4710, 2)))
    await asyncio.sleep(0)
    assert not second.done()
    release.set()
    await asyncio.gather(first, second)
    assert session.sequence == 77
    await link.close()


def report_at(timestamp):
    raw = bytearray(bytes.fromhex(FIXTURE.read_text()))
    now = datetime.fromtimestamp(timestamp, timezone.utc)
    for offset, value in zip((120,122,124,126,128,130), (now.year-2000,now.month,now.day,now.hour,now.minute,now.second)):
        raw[offset:offset+2] = value.to_bytes(2, 'big')
    raw[-2] = sum(raw[1:-2]) & 255
    return Frame.parse(bytes(raw))


def test_future_measurement_cannot_poison_live_or_restored_values(tmp_path):
    import time
    config = AppConfig(loggers=[Logger(serial=SERIAL)])
    config.server.timezone = 'UTC'
    ConfigStore(tmp_path).save(config)
    runtime = Runtime(tmp_path)
    session = SimpleNamespace(config=config, logger=config.loggers[0], state=runtime.states[SERIAL],
                              writer=SimpleNamespace(get_extra_info=lambda name: ('127.0.0.1', 1)))
    future = report_at(time.time()+86400)
    runtime.observe(session, future)
    assert session.state['latest'] is None
    assert session.state['decode_error']
    runtime.observe(session, report_at(time.time()))
    assert len(session.state['latest']['values']) == 48
    assert session.state['decode_error'] is None
    poisoned = runtime.active_profiles[config.loggers[0].profile].decode(future, 'UTC')
    poisoned.update(serial=SERIAL, received_at=time.time())
    atomic_json(tmp_path/'archive'/'latest'/f'{SERIAL}.json', poisoned)
    restarted = Runtime(tmp_path)
    assert restarted.states[SERIAL]['latest'] is None
    assert SERIAL not in restarted.mqtt.latest


@pytest.mark.parametrize('confirmed', [False, True])
async def test_mqtt_shutdown_requires_puback_before_clean_disconnect(tmp_path, confirmed):
    operations = []
    result = SimpleNamespace(rc=paho.MQTT_ERR_SUCCESS,
                             wait_for_publish=lambda **kw: None,
                             is_published=lambda: confirmed)
    client = SimpleNamespace(publish=lambda *a, **kw: result,
                             socket=lambda: SimpleNamespace(shutdown=lambda how: operations.append('shutdown')),
                             disconnect=lambda: operations.append('disconnect'), loop_stop=lambda: None)
    publisher = Publisher(tmp_path, lambda *a, **kw: None)
    publisher.client, publisher.connected = client, True
    await publisher.close()
    assert operations == (['disconnect'] if confirmed else ['shutdown', 'disconnect'])


def test_archive_shrinks_old_rotation_and_keeps_files_private(tmp_path):
    archive = Archive(tmp_path, Storage(backups=5))
    for index in range(1, 6):
        (archive.directory/f'frames.{index}.jsonl').write_text('{}\n')
    archive.write('frames', {'sample': 1})
    assert (archive.directory/'frames.jsonl').stat().st_mode & 0o777 == 0o600
    archive.settings = Storage(backups=1)
    archive.write('frames', {'sample': 2})
    assert [path.name for path in archive.directory.glob('frames.*.jsonl')] == ['frames.1.jsonl']


def test_profile_resolves_dst_fold_and_rejects_nonexistent_wall_time(tmp_path):
    profile=ProfileStore(tmp_path).load()['sofar-hyd-g3-2115']
    repeated=report_at(datetime(2026,10,25,2,30,tzinfo=timezone.utc).timestamp())
    first=profile.decode(repeated,'Europe/Warsaw',datetime(2026,10,25,0,30,tzinfo=timezone.utc).timestamp())
    second=profile.decode(repeated,'Europe/Warsaw',datetime(2026,10,25,1,30,tzinfo=timezone.utc).timestamp())
    assert first['sample_time'].endswith('+02:00')
    assert second['sample_time'].endswith('+01:00')
    missing=report_at(datetime(2026,3,29,2,30,tzinfo=timezone.utc).timestamp())
    with pytest.raises(ValueError,match='does not exist'):
        profile.decode(missing,'Europe/Warsaw')


async def test_late_close_of_old_generation_keeps_current_transport():
    link=CloudLink(SimpleNamespace(state={'cloud_connected':True}))
    current=WaitingWriter();current.gate.set()
    link.writer=current;link.generation=2
    await link.close(expected=1)
    assert link.writer is current and not current.closed
    await link.close()
    assert current.closed
