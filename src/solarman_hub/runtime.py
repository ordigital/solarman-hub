"""Small composition root: configuration snapshots, observation and lifecycle."""
from . import __version__
import asyncio
from contextlib import suppress
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import time

from .archive import Archive
from .history import History
from .identity import observed_identity
from .config import ConfigStore
from .mqtt import Publisher
from .profiles import ProfileStore
from .relay import Session


class Runtime:
    def __init__(self, data_dir: Path, tcp_host=None, tcp_port=None):
        self.started_at = time.time()
        self.store = ConfigStore(data_dir)
        self.profiles = ProfileStore(data_dir)
        self.active = self.store.load()
        self.active_profiles = self.profiles.load()
        self.validate_references(self.active, self.active_profiles)
        self.active_revision = self.store.revision(self.profiles.documents())
        self.startup_server = self.active.server.model_dump()
        self.tcp_host = tcp_host if tcp_host is not None else self.active.server.tcp_host
        self.tcp_port = tcp_port if tcp_port is not None else self.active.server.tcp_port
        self.archive = Archive(data_dir, self.active.storage)
        self.mqtt = Publisher(data_dir, self.archive.event)
        self.history = History(data_dir, self.active.storage, self.archive.event)
        self.sessions = {}
        self.connections = set()
        self.states = {logger.serial: self.new_state(logger) for logger in self.active.loggers}
        self.server = None
        self.maintenance = None
        self.lock = asyncio.Lock()
        self.accepting = True
        for logger in self.active.loggers:
            try:
                identity = json.loads((data_dir/"archive"/"devices"/(str(logger.serial)+".json")).read_text())["identity"]
                if isinstance(identity, dict):
                    self.states[logger.serial]["identity"] = identity
            except (OSError, ValueError, KeyError, TypeError):
                pass
            try:
                sample = json.loads((data_dir/"archive"/"latest"/(str(logger.serial)+".json")).read_text())
                profile = self.active_profiles.get(logger.profile)
                if (profile and isinstance(sample, dict) and isinstance(sample.get("values"), dict) and
                        isinstance(sample.get("received_at"), (int, float)) and math.isfinite(sample["received_at"]) and
                        sample.get("profile") == logger.profile and
                        sample.get("profile_revision") == profile.revision and
                        self.valid_sample_clock(sample)):
                    self.states[logger.serial]["latest"] = sample
                    self.mqtt.latest[logger.serial] = sample
            except (OSError, ValueError):
                pass

    @staticmethod
    def validate_references(config, profiles):
        for logger in config.loggers:
            if logger.profile is not None and logger.profile not in profiles:
                raise ValueError(f"Nieznany profil loggera {logger.serial}: {logger.profile}")

    @staticmethod
    def new_state(logger):
        return {"serial": logger.serial, "name": logger.name, "connected": False,
            "cloud_connected": False, "frames": 0, "reports": 0, "decoded": 0,
            "cloud_acks": 0, "local_acks": 0, "invalid_bytes": 0, "decode_error": None,
            "cloud_error": None, "last_frame_at": None, "latest": None, "identity": {}, "frame_types": {}}

    def observe(self, session, frame):
        """Observer failures must never be allowed to terminate the relay."""
        logger = session.logger
        state = session.state
        try:
            peer = session.writer.get_extra_info("peername")
            fields = observed_identity(frame, str(peer[0]) if peer else "")
            previous = state["identity"]
            changed = any(key not in previous or previous[key]["value"] != value["value"] for key,value in fields.items())
            previous.update(fields)
            kind = f"0x{frame.code:04x}/{len(frame.raw)}"
            if kind in state["frame_types"] or len(state["frame_types"]) < 32:
                state["frame_types"][kind] = state["frame_types"].get(kind, 0)+1
            if changed:
                self.archive.submit("device", {"serial": logger.serial, "identity": previous.copy()})
        except Exception as error:
            self.archive.event("identity_error", level="warning", serial=logger.serial, error=str(error))
        if frame.code == 0x4210:
            state["reports"] += 1
        profile = self.active_profiles.get(logger.profile)
        if profile is None or frame.code != profile.match.code:
            return
        try:
            received_at = time.time()
            sample = profile.decode(frame, session.config.server.timezone, reference_time=received_at)
            sample.update(serial=logger.serial, received_at=received_at, frame_sha256=hashlib.sha256(frame.raw).hexdigest())
            if not self.valid_sample_clock(sample):
                self.archive.measurement({**sample, "out_of_order": True})
                self.history.submit(sample)
                raise ValueError("Sample timestamp is too far in the future")
            previous = state.get("latest")
            if previous and sample["sample_time"] and previous.get("sample_time"):
                if datetime.fromisoformat(sample["sample_time"]) < datetime.fromisoformat(previous["sample_time"]):
                    self.archive.measurement({**sample, "out_of_order": True})
                    self.history.submit({**sample, "out_of_order": True})
                    self.archive.event("older_sample_ignored", serial=logger.serial, sample_time=sample["sample_time"])
                    return
                if sample["sample_time"] == previous["sample_time"] and sample["values"] == previous["values"]:
                    return
            state["latest"] = sample
            state["decoded"] += 1
            state["decode_error"] = None
            self.archive.measurement(sample)
            self.history.submit(sample)
            self.mqtt.set_available(logger.serial, self.fresh(state, logger))
            self.mqtt.accept(logger, sample)
            self.archive.event("measurement", serial=logger.serial, sample_time=sample["sample_time"], fields=len(sample["values"]))
        except Exception as error:
            state["decode_error"] = str(error)
            self.archive.event("decode_error", level="warning", serial=logger.serial, error=str(error))

    @staticmethod
    def valid_sample_clock(sample):
        try:
            value = sample.get("sample_time")
            return not value or datetime.fromisoformat(value).timestamp() <= time.time()+300
        except (ValueError, TypeError, OverflowError):
            return False

    @staticmethod
    def fresh(state, logger):
        sample = state.get("latest")
        if not sample or not state["connected"]:
            return False
        age = time.time()-sample["received_at"]
        if age > logger.stale_after:
            return False
        if sample.get("sample_time"):
            sample_age = time.time()-datetime.fromisoformat(sample["sample_time"]).timestamp()
            if sample_age > logger.stale_after or sample_age < -300:
                return False
        return True

    async def accept(self, reader, writer):
        if not self.accepting or len(self.connections) >= self.active.server.max_connections:
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
            return
        session = Session(self, reader, writer)
        self.connections.add(session)
        try:
            await session.run()
        finally:
            self.connections.discard(session)

    async def start(self):
        self.archive.start()
        await self.history.start()
        try:
            await self.mqtt.configure(self.active)
            self.server = await asyncio.start_server(self.accept, self.tcp_host, self.tcp_port)
        except BaseException:
            await self.close()
            raise
        self.tcp_port = self.server.sockets[0].getsockname()[1]
        self.maintenance = asyncio.create_task(self.tick(), name="freshness")
        self.archive.event("started", tcp_host=self.tcp_host, tcp_port=self.tcp_port)

    async def tick(self):
        last_saved_discovery = None
        while True:
            for logger in self.active.loggers:
                state = self.states.get(logger.serial)
                if state:
                    self.mqtt.set_available(logger.serial, logger.enabled and self.fresh(state, logger))
            self.mqtt.flush()
            signature = tuple(sorted(self.mqtt.known_discovery))
            if signature != last_saved_discovery:
                try:
                    from .config import atomic_json
                    await asyncio.to_thread(atomic_json, self.mqtt.discovery_cache, list(signature))
                    last_saved_discovery = signature
                except OSError:
                    pass
            await asyncio.sleep(2)

    async def apply(self):
        self.accepting = False
        try:
            await self._apply()
        finally:
            self.accepting = True

    async def _apply(self):
        config = self.store.load()
        profiles = self.profiles.load()
        self.validate_references(config, profiles)
        revision = self.store.revision(self.profiles.documents())
        await asyncio.gather(*(session.stop() for session in list(self.connections)))
        # Let each old session finish its own task cleanup before accepting its replacement.
        for _ in range(100):
            if not self.connections:
                break
            await asyncio.sleep(.02)
        if self.connections:
            raise RuntimeError("Poprzednie połączenia jeszcze się zamykają; spróbuj ponownie")
        previous = self.active
        self.active = config
        self.active_profiles = profiles
        self.active_revision = revision
        self.archive.settings = config.storage
        self.history.settings = config.storage
        self.states = {logger.serial: self.states.get(logger.serial, self.new_state(logger)) for logger in config.loggers}
        previous_profiles = {logger.serial: logger.profile for logger in previous.loggers}
        for logger in config.loggers:
            state = self.states[logger.serial]
            state["name"] = logger.name
            sample = state.get("latest")
            if (previous_profiles.get(logger.serial) != logger.profile or
                (sample and logger.profile and sample.get("profile_revision") != profiles[logger.profile].revision)):
                state["latest"] = None
                self.mqtt.latest.pop(logger.serial, None)
        await self.mqtt.configure(config)
        self.archive.event("configuration_applied", revision=revision)

    async def reconnect(self, serial):
        session = self.sessions.get(serial)
        if session:
            await session.stop()

    def status(self):
        saved = self.store.load()
        states = []
        for logger in self.active.loggers:
            state = dict(self.states[logger.serial])
            state.update(name=logger.name, enabled=logger.enabled, profile=logger.profile,
                         fresh=logger.enabled and self.fresh(state, logger), stale_after=logger.stale_after)
            sample = state.get("latest")
            state["received_age"] = round(time.time()-sample["received_at"], 1) if sample else None
            states.append(state)
        return {"version": __version__, "started_at": self.started_at, "now": time.time(),
            "saved_revision": self.store.revision(self.profiles.documents()), "applied_revision": self.active_revision,
            "restart_required": any(getattr(saved.server, key) != self.startup_server[key]
                for key in ("tcp_host", "tcp_port", "web_host", "web_port")),
            "listener": {"host": self.tcp_host, "port": self.tcp_port},
            "cloud": {"enabled": self.active.cloud.enabled, "host": self.active.cloud.host, "port": self.active.cloud.port},
            "connections": len(self.connections), "loggers": states,
            "mqtt": self.mqtt.status(), "archive": self.archive.status(), "history": self.history.status()}

    async def close(self):
        self.accepting = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await asyncio.gather(*(session.stop() for session in list(self.connections)))
        for _ in range(100):
            if not self.connections:
                break
            await asyncio.sleep(.02)
        if self.maintenance:
            self.maintenance.cancel()
            with suppress(asyncio.CancelledError):
                await self.maintenance
        await self.mqtt.close()
        await self.history.close()
        await self.archive.close()
