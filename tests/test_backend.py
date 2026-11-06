"""Backend contracts, using loopback sockets only (never the real logger)."""
import asyncio
from contextlib import asynccontextmanager, suppress
import json
from pathlib import Path
import struct
import time
from types import SimpleNamespace

import paho.mqtt.client as paho
import pytest
from pydantic import ValidationError

from solarman_hub.archive import Archive
from solarman_hub.config import AppConfig, ConfigStore, Logger, Storage, public_config
from solarman_hub.mqtt import Publisher
from solarman_hub.profiles import Profile, ProfileStore
from solarman_hub.protocol import Frame, Framer, local_ack
from solarman_hub.runtime import Runtime

FIXTURES = Path(__file__).parent / "fixtures"
SERIAL = 1234567890


def frame(code=0x4110, sequence=1, payload=b"\x02", serial=SERIAL):
    body = struct.pack("<HHBBI", len(payload), code, 0, sequence, serial) + payload
    return Frame.parse(b"\xa5" + body + bytes((sum(body) & 255, 0x15)))


async def receive(reader):
    header = await reader.readexactly(3)
    return Frame.parse(header + await reader.readexactly(int.from_bytes(header[1:3], "little") + 10))


@asynccontextmanager
async def cloud_server(handler):
    tasks, writers, errors = set(), set(), []

    async def run(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        writers.add(writer)
        try:
            await handler(reader, writer)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        except Exception as error:
            errors.append(error)
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()
            writers.discard(writer)
            tasks.discard(task)

    server = await asyncio.start_server(run, "127.0.0.1", 0)
    try:
        yield server.sockets[0].getsockname()[1]
    finally:
        server.close()
        await server.wait_closed()
        for writer in list(writers):
            writer.close()
        remaining = list(tasks)
        for task in remaining:
            task.cancel()
        await asyncio.gather(*remaining, return_exceptions=True)
        assert not errors


@asynccontextmanager
async def hub(directory, cloud_port=1, enabled=True, ack_timeout=.1):
    store = ConfigStore(directory)
    config = AppConfig.model_validate({"cloud": {"host": "127.0.0.1", "port": cloud_port,
        "enabled": enabled, "connect_timeout": .1, "ack_timeout": ack_timeout},
        "loggers": [{"serial": SERIAL, "allowed_ip": "127.0.0.1"}]})
    store.save(config)
    runtime = Runtime(directory, tcp_host="127.0.0.1", tcp_port=0)
    await runtime.start()
    try:
        yield runtime
    finally:
        await runtime.close()


@asynccontextmanager
async def logger_connection(runtime):
    reader, writer = await asyncio.open_connection("127.0.0.1", runtime.tcp_port)
    try:
        yield reader, writer
    finally:
        writer.close()
        with suppress(ConnectionError):
            await writer.wait_closed()


def test_reference_profile_all_48_fields_and_arbitrary_serial(tmp_path):
    report = Frame.parse(bytes.fromhex((FIXTURES / "sofar-report.hex").read_text()))
    expected = json.loads((FIXTURES / "sofar-expected.json").read_text())
    profile = ProfileStore(tmp_path).load()["sofar-hyd-g3-2115"]
    for serial in (SERIAL, 42):
        raw = bytearray(report.raw)
        raw[7:11] = serial.to_bytes(4, "little")
        raw[-2] = sum(raw[1:-2]) & 255
        sample = profile.decode(Frame.parse(bytes(raw)), "Europe/Warsaw")
        assert sample["sample_time"] == expected["sample_time"]
        assert len(sample["values"]) == 48
        assert {key: value["value"] for key, value in sample["values"].items()} == expected["values"]


def test_profile_rejects_out_of_bounds_duplicate_and_overflow(tmp_path):
    source = ProfileStore(tmp_path).load()["sofar-hyd-g3-2115"].model_dump()
    source["fields"][0]["offset"] = source["match"]["length"] - 2
    with pytest.raises(ValidationError):
        Profile.model_validate(source)
    source["fields"][0]["offset"] = 11
    source["fields"].append(source["fields"][0].copy())
    with pytest.raises(ValidationError):
        Profile.model_validate(source)
    source["fields"].pop()
    source["fields"][0]["scale"] = 1e308
    profile = Profile.model_validate(source)
    report = Frame.parse(bytes.fromhex((FIXTURES / "sofar-report.hex").read_text()))
    with pytest.raises(ValueError, match="zakres"):
        profile.decode(report, "UTC")


def test_framer_fragmentation_concatenation_and_resync():
    first, second = frame(), frame(0x4710, 2, b"\0")
    corrupt = bytearray(first.raw)
    corrupt[-2] ^= 1
    parser = Framer()
    assert parser.feed(b"garbage" + bytes(corrupt) + first.raw[:2]) == []
    assert parser.feed(first.raw[2:] + second.raw) == [first, second]
    assert parser.invalid > 0
    assert not parser.buffer


def test_ack_echoes_sequence_serial_and_timezone():
    upload = frame(sequence=177, serial=42)
    ack = local_ack(upload, 9, "Europe/Warsaw", timestamp=0)
    assert (ack.code, ack.serial, ack.sequence) == (0x1110, 42, 177)
    assert ack.raw[5] == 9
    assert struct.unpack("<BBIi", ack.raw[11:-2]) == (2, 1, 0, 60)


def test_configuration_secrets_and_atomic_save(tmp_path):
    store = ConfigStore(tmp_path)
    config = AppConfig()
    config.mqtt.password = "secret-test-value"
    store.save(config)
    redacted = public_config(store.load())
    assert "password" not in redacted["mqtt"]
    assert "secret-test-value" not in json.dumps(redacted)
    assert store.candidate(redacted).mqtt.password == "secret-test-value"
    redacted["mqtt"]["password"] = ""
    assert store.candidate(redacted).mqtt.password == "secret-test-value"
    redacted["mqtt"]["clear_password"] = "false"
    with pytest.raises(ValueError):
        store.candidate(redacted)
    redacted["mqtt"]["clear_password"] = True
    assert store.candidate(redacted).mqtt.password == ""
    assert store.path.stat().st_mode & 0o777 == 0o600


async def test_relay_raw_ack_and_bidirectional_unknown_frames(tmp_path):
    seen = []
    finished = asyncio.Event()
    upload = frame()
    command = frame(0x4510, 31, b"command")
    reply = frame(0x1510, 31, b"reply")
    expected_ack = local_ack(upload, 77, "UTC", timestamp=1700000000)

    async def cloud(reader, writer):
        seen.append(await receive(reader))
        writer.write(command.raw + expected_ack.raw)
        await writer.drain()
        seen.append(await receive(reader))
        finished.set()
        await reader.read()

    async with cloud_server(cloud) as port, hub(tmp_path, port) as runtime:
        async with logger_connection(runtime) as (reader, writer):
            writer.write(upload.raw[:4])
            await writer.drain()
            writer.write(upload.raw[4:])
            responses = [await asyncio.wait_for(receive(reader), 1) for _ in range(2)]
            assert {item.raw for item in responses} == {expected_ack.raw, command.raw}
            writer.write(reply.raw)
            await asyncio.wait_for(finished.wait(), 1)
            assert seen == [upload, reply]
            assert runtime.states[SERIAL]["cloud_acks"] == 1
            assert runtime.states[SERIAL]["local_acks"] == 0


@pytest.mark.parametrize("behavior", ["silent", "eof", "late"])
async def test_cloud_failure_returns_exactly_one_local_ack(tmp_path, behavior):
    async def cloud(reader, writer):
        upload = await receive(reader)
        if behavior == "eof":
            return
        if behavior == "late":
            await asyncio.sleep(.25)
            writer.write(local_ack(upload, 99, "UTC").raw)
            await writer.drain()
        await reader.read()

    async with cloud_server(cloud) as port, hub(tmp_path, port) as runtime:
        async with logger_connection(runtime) as (reader, writer):
            upload = frame(sequence=45)
            writer.write(upload.raw)
            ack = await asyncio.wait_for(receive(reader), 1)
            assert (ack.code, ack.sequence) == (0x1110, 45)
            assert runtime.states[SERIAL]["local_acks"] == 1
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1), .35)


async def test_refused_cloud_and_decode_error_do_not_break_logger(tmp_path):
    reserved = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = reserved.sockets[0].getsockname()[1]
    reserved.close()
    await reserved.wait_closed()
    async with hub(tmp_path, port) as runtime, logger_connection(runtime) as (reader, writer):
        writer.write(frame().raw + frame(0x4210, 2, b"wrong-profile-length").raw)
        first = await asyncio.wait_for(receive(reader), 1)
        second = await asyncio.wait_for(receive(reader), 1)
        assert [first.code, second.code] == [0x1110, 0x1210]
        assert runtime.states[SERIAL]["decode_error"]
        assert runtime.states[SERIAL]["local_acks"] == 2


async def test_reconnect_bootstrap_ack_is_not_forwarded_twice(tmp_path):
    uploads = []
    first_closed = asyncio.Event()

    async def cloud(reader, writer):
        handshake = await receive(reader)
        uploads.append(handshake)
        writer.write(local_ack(handshake, 20, "UTC").raw)
        await writer.drain()
        if len(uploads) == 1:
            writer.close()
            await writer.wait_closed()
            first_closed.set()
            return
        heartbeat = await receive(reader)
        uploads.append(heartbeat)
        writer.write(local_ack(heartbeat, 21, "UTC").raw)
        await writer.drain()
        await reader.read()

    async with cloud_server(cloud) as port, hub(tmp_path, port) as runtime:
        async with logger_connection(runtime) as (reader, writer):
            handshake = frame()
            writer.write(handshake.raw)
            assert (await asyncio.wait_for(receive(reader), 1)).code == 0x1110
            await asyncio.wait_for(first_closed.wait(), 1)
            for _ in range(100):
                if not runtime.states[SERIAL]["cloud_connected"]:
                    break
                await asyncio.sleep(.005)
            heartbeat = frame(0x4710, 2, b"\0")
            writer.write(heartbeat.raw)
            response = await asyncio.wait_for(receive(reader), 1)
            assert (response.code, response.sequence) == (0x1710, 2)
            assert uploads == [handshake, handshake, heartbeat]
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1), .05)


async def test_rejected_logger_cleanup_has_no_unhandled_error(tmp_path):
    loop = asyncio.get_running_loop()
    previous, errors = loop.get_exception_handler(), []
    loop.set_exception_handler(lambda loop, context: errors.append(context))
    try:
        async with hub(tmp_path, enabled=False) as runtime:
            async with logger_connection(runtime) as (reader, writer):
                writer.write(frame(serial=999).raw)
                assert await asyncio.wait_for(reader.read(), 1) == b""
            await asyncio.sleep(.02)
            assert not runtime.sessions
        assert not errors
    finally:
        loop.set_exception_handler(previous)


async def test_apply_cancels_silent_cloud_and_changes_snapshot(tmp_path):
    received = asyncio.Event()

    async def cloud(reader, writer):
        await receive(reader)
        received.set()
        await reader.read()

    async with cloud_server(cloud) as port, hub(tmp_path, port, ack_timeout=60) as runtime:
        async with logger_connection(runtime) as (reader, writer):
            writer.write(frame().raw)
            await asyncio.wait_for(received.wait(), 1)
            config = runtime.store.load()
            config.cloud.enabled = False
            config.server.timezone = "UTC"
            runtime.store.save(config)
            await asyncio.wait_for(runtime.apply(), 1)
            assert await asyncio.wait_for(reader.read(), 1) == b""
            assert not runtime.connections
            assert not runtime.active.cloud.enabled
            assert not runtime.status()["restart_required"]


async def test_archive_disk_failure_and_queue_bounds(tmp_path, monkeypatch):
    archive = Archive(tmp_path, Storage(queue_size=16))
    for index in range(20):
        archive.event("test", index=index)
    assert archive.queue.qsize() == 16
    assert archive.dropped == 4

    def disk_failure(*args):
        raise OSError("test disk full")

    monkeypatch.setattr(archive, "write", disk_failure)
    archive.start()
    await asyncio.wait_for(archive.queue.join(), 1)
    assert archive.last_error == "test disk full"
    assert archive.dropped == 20
    await archive.close()


class FakeMQTT:
    def __init__(self):
        self.remaining = 0
        self.sent = []

    def publish(self, topic, payload, **kwargs):
        if self.remaining <= 0:
            return SimpleNamespace(rc=paho.MQTT_ERR_QUEUE_SIZE)
        self.remaining -= 1
        self.sent.append((topic, payload, kwargs))
        return SimpleNamespace(rc=paho.MQTT_ERR_SUCCESS)


def test_mqtt_retries_availability_discovery_and_latest_after_full_queue(tmp_path):
    publisher = Publisher(tmp_path, lambda *a, **kw: None)
    publisher.config = AppConfig(loggers=[Logger(serial=SERIAL)])
    publisher.connected = True
    publisher.client = client = FakeMQTT()
    publisher.set_available(SERIAL, True)
    assert SERIAL not in publisher.published_availability
    sample = ProfileStore(tmp_path).load()["sofar-hyd-g3-2115"].decode(
        Frame.parse(bytes.fromhex((FIXTURES / "sofar-report.hex").read_text())), "UTC")
    sample["received_at"] = time.time()
    publisher.accept(publisher.config.loggers[0], sample)
    assert SERIAL in publisher.pending_samples
    obsolete = "homeassistant/sensor/solarman_999/old/config"
    publisher.known_discovery.add(obsolete)
    publisher.flush()
    assert obsolete in publisher.known_discovery
    for _ in range(60):
        client.remaining = 3
        publisher.flush()
    assert obsolete not in publisher.known_discovery
    assert not publisher.pending_samples
    assert publisher.published_availability[SERIAL]
    assert len(publisher.known_discovery) == 48
    states = [json.loads(payload) for topic, payload, _ in client.sent if topic.endswith("/state")]
    assert states and len(states[-1]["values"]) == 48
    assert any(topic == obsolete and payload == "" for topic, payload, _ in client.sent)


def test_register_alias_preserves_profile_json(tmp_path):
    profile = next(iter(ProfileStore(tmp_path).load().values()))
    document = profile.model_dump()
    assert all("register" in field and "register_hint" not in field for field in document["fields"])
    assert Profile.model_validate(document).revision == profile.revision


@pytest.mark.parametrize('cycles', [0, 677, 32768, 65535])
def test_battery_cycles_unsigned_counter_and_existing_sensor_ids(tmp_path, cycles):
    profile = ProfileStore(tmp_path).load()['sofar-hyd-g3-2115']
    raw = bytearray.fromhex((FIXTURES / 'sofar-report.hex').read_text())
    raw[474:476] = cycles.to_bytes(2, 'big')
    raw[-2] = sum(raw[1:-2]) & 255
    sample = profile.decode(Frame.parse(bytes(raw)), 'Europe/Warsaw')
    value = sample['values']['battery1_cycles']
    assert value['value'] == cycles
    assert value['unit'] == 'cycle'
    field = next(field for field in profile.fields if field.id == 'battery1_cycles')
    assert field.register_hint == '0x060A'
    assert profile.id == 'sofar-hyd-g3-2115'
    assert sample['values']['battery1_soc']['value'] == json.loads(
        (FIXTURES / 'sofar-expected.json').read_text())['values']['battery1_soc']
