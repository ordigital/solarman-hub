"""V5 relay session. ACK ownership is exclusive; decoding is an isolated observer."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import time

from .protocol import ACK_CODES, Framer, local_ack


class CloudLink:
    def __init__(self, session):
        self.session = session
        self.writer = None
        self.reader_task = None
        self.pending = {}
        self.handshake = None
        self.connect_lock = asyncio.Lock()
        self.generation = 0

    async def close(self, expected=None):
        async with self.connect_lock:
            if expected is None or expected == self.generation:
                await self._close()

    async def _close(self):
        # Detach this generation before awaiting transport cleanup. Old readers
        # and exchanges must never touch futures of a replacement connection.
        writer, task, pending = self.writer, self.reader_task, self.pending
        self.writer = self.reader_task = None
        self.pending = {}
        self.generation += 1
        if self.session.state is not None:
            self.session.state["cloud_connected"] = False
        for future in list(pending.values()):
            if not future.done():
                future.set_exception(ConnectionError("Połączenie z chmurą zostało zamknięte"))
        if task and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
        if writer:
            writer.close()
            with suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), 2)

    async def receive(self, reader, writer, pending):
        parser = Framer()
        try:
            while data := await reader.read(8192):
                for frame in parser.feed(data):
                    if frame.serial != self.session.logger.serial:
                        raise ValueError("Nieprawidłowy numer loggera w odpowiedzi chmury")
                    self.session.record("cloud_to_hub", frame)
                    future = pending.get((frame.code, frame.sequence))
                    if future is not None and not future.done():
                        future.set_result(frame)
                    elif frame.code in ACK_CODES.values():
                        self.session.event("late_cloud_ack_dropped", control=hex(frame.code))
                    else:
                        await self.session.send_logger(frame)
            raise ConnectionError("Chmura zamknęła połączenie TCP")
        except (OSError, ValueError, asyncio.TimeoutError) as error:
            self.session.event("cloud_disconnected", level="warning", error=str(error))
        finally:
            if self.writer is writer:
                self.writer = None
                writer.close()
                self.session.state["cloud_connected"] = False
                for future in list(pending.values()):
                    if not future.done():
                        future.set_exception(ConnectionError("Chmura rozłączyła połączenie"))

    async def ensure(self, first):
        settings = self.session.config.cloud
        if not settings.enabled:
            raise ConnectionError("Przekazywanie do chmury jest wyłączone")
        async with self.connect_lock:
            if self.writer:
                return
            await self._close()
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(settings.host, settings.port), settings.connect_timeout)
                self.writer = writer
                self.reader_task = asyncio.create_task(self.receive(reader, writer, self.pending), name=f"cloud-{first.serial}")
                self.session.state["cloud_connected"] = True
                self.session.event("cloud_connected", host=settings.host, port=settings.port)
                if first.code != 0x4110 and self.handshake:
                    response = await self.exchange(self.handshake)  # consumed, never forwarded twice
                    self.session.sequence = response.raw[5]
                    self.session.event("cloud_bootstrapped")
            except BaseException:
                await self._close()
                raise

    async def exchange(self, frame):
        key = (ACK_CODES[frame.code], frame.sequence)
        future = asyncio.get_running_loop().create_future()
        pending, writer = self.pending, self.writer
        pending[key] = future
        try:
            if not writer:
                raise ConnectionError("Chmura jest niedostępna")
            writer.write(frame.raw)
            self.session.record("hub_to_cloud", frame)
            await asyncio.wait_for(writer.drain(), self.session.config.cloud.ack_timeout)
            return await asyncio.wait_for(future, self.session.config.cloud.ack_timeout)
        finally:
            pending.pop(key, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    async def relay(self, frame):
        await self.ensure(frame)
        generation = self.generation
        try:
            return await self.exchange(frame)
        except (OSError, ValueError, asyncio.TimeoutError):
            await self.close(expected=generation)
            raise

    async def forward_unknown(self, frame):
        generation = None
        try:
            await self.ensure(frame)
            generation = self.generation
            writer = self.writer
            if not writer:
                raise ConnectionError("Chmura jest niedostępna")
            writer.write(frame.raw)
            self.session.record("hub_to_cloud", frame)
            await asyncio.wait_for(writer.drain(), self.session.config.cloud.ack_timeout)
        except (OSError, ValueError, asyncio.TimeoutError) as error:
            if generation is not None:
                await self.close(expected=generation)
            self.session.event("unknown_frame_not_forwarded", level="warning", control=hex(frame.code), error=str(error))


class Session:
    def __init__(self, runtime, reader, writer):
        self.runtime = runtime
        self.reader = reader
        self.writer = writer
        self.config = runtime.active
        self.revision = runtime.active_revision
        self.logger = None
        self.state = None
        self.cloud = CloudLink(self)
        self.queue = asyncio.Queue(maxsize=32)
        self.worker = None
        self.run_task = None
        self.sequence = 0
        self.started = time.monotonic()
        self.closing = False
        self.stop_requested = False

    def event(self, name, **fields):
        self.runtime.archive.event(name, serial=self.logger.serial if self.logger else None, **fields)

    def record(self, direction, frame):
        self.runtime.archive.frame(direction, frame.serial, frame.raw)

    async def send_logger(self, frame):
        self.writer.write(frame.raw)
        self.record("hub_to_logger", frame)
        await asyncio.wait_for(self.writer.drain(), 5)

    async def process(self):
        while True:
            frame = await self.queue.get()
            if frame.code == 0x4110:
                self.cloud.handshake = frame
            try:
                response = await self.cloud.relay(frame)
                self.sequence = response.raw[5]
                origin = "cloud"
                self.state["cloud_acks"] += 1
                self.state["last_cloud_ack"] = time.time()
                self.state["cloud_error"] = None
            except (OSError, ValueError, asyncio.TimeoutError) as error:
                self.sequence = (self.sequence+1) & 255
                response = local_ack(frame, self.sequence, self.config.server.timezone)
                origin = "local"
                self.state["local_acks"] += 1
                self.state["cloud_error"] = str(error)
                self.event("local_ack", level="warning", control=hex(frame.code), error=str(error))
            await self.send_logger(response)
            self.state["last_ack_origin"] = origin
            self.state["last_ack_at"] = time.time()
            self.queue.task_done()

    async def identify(self, frame):
        peer = self.writer.get_extra_info("peername")[0]
        logger = next((logger for logger in self.config.loggers if logger.serial == frame.serial and logger.enabled), None)
        if not logger or (logger.allowed_ip and logger.allowed_ip != peer):
            raise ValueError("Logger nie jest dozwolony; dodaj jego numer seryjny i IP w konfiguracji")
        if logger.serial in self.runtime.sessions:
            raise ValueError("Ten logger ma już aktywną sesję")
        self.logger = logger
        self.runtime.sessions[logger.serial] = self
        self.state = self.runtime.states.setdefault(logger.serial, self.runtime.new_state(logger))
        self.state.update(connected=True, peer=peer, connected_at=time.time(), session_revision=self.revision)
        self.event("logger_connected", peer=peer)
        self.worker = asyncio.create_task(self.process(), name=f"uploads-{logger.serial}")
        self.worker.add_done_callback(self.worker_finished)

    def worker_finished(self, task):
        # Wake the read loop immediately if writing an ACK fails. Otherwise a
        # dead upload worker could leave the session connected until idle timeout.
        if not task.cancelled() and task.exception() is not None:
            self.writer.close()

    async def run(self):
        self.run_task = asyncio.current_task()
        parser = Framer()
        try:
            while True:
                if self.logger:
                    timeout = self.config.server.idle_timeout
                else:
                    timeout = self.config.server.handshake_timeout-(time.monotonic()-self.started)
                    if timeout <= 0:
                        raise asyncio.TimeoutError("Przekroczono czas identyfikacji loggera")
                data = await asyncio.wait_for(self.reader.read(8192), timeout)
                if not data:
                    break
                if self.worker and self.worker.done():
                    await self.worker
                for frame in parser.feed(data):
                    if self.logger is None:
                        await self.identify(frame)
                    if frame.serial != self.logger.serial:
                        raise ValueError("Zmiana numeru loggera wewnątrz sesji")
                    self.record("logger_to_hub", frame)
                    self.state["last_frame_at"] = time.time()
                    self.state["frames"] += 1
                    self.state["invalid_bytes"] = parser.invalid
                    self.runtime.observe(self, frame)
                    if frame.code in ACK_CODES:
                        self.queue.put_nowait(frame)
                    else:
                        await self.cloud.forward_unknown(frame)
                if parser.invalid > 4096:
                    raise ValueError("Zbyt wiele nieprawidłowych danych V5")
        except (OSError, ValueError, asyncio.TimeoutError, asyncio.QueueFull) as error:
            self.event("logger_error", level="warning", error=str(error))
        finally:
            self.closing = True
            try:
                if self.worker:
                    self.worker.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await self.worker
                await self.cloud.close()
                await self.stop()
            finally:
                # Release identity even if cancellation interrupts I/O cleanup.
                self.writer.close()
                if self.logger:
                    self.state.update(connected=False, cloud_connected=False)
                    if self.runtime.sessions.get(self.logger.serial) is self:
                        self.runtime.sessions.pop(self.logger.serial, None)
                    self.runtime.mqtt.set_available(self.logger.serial, False)
                    self.event("logger_disconnected")

    async def stop(self):
        if (not self.stop_requested and not self.closing and self.run_task
                and self.run_task is not asyncio.current_task() and not self.run_task.cancelling()):
            self.run_task.cancel()
        self.stop_requested = True
        self.writer.close()
        with suppress(Exception):
            await asyncio.wait_for(self.writer.wait_closed(), 2)
