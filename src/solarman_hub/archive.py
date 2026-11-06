"""Bounded asynchronous output: disk failures never escape into TCP forwarding."""
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from .config import Storage, atomic_json


class Archive:
    def __init__(self, data_dir: Path, settings: Storage):
        self.directory = data_dir/"archive"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.settings = settings
        self.queue = asyncio.Queue(maxsize=4096)
        self.events = deque(maxlen=500)
        self.dropped = 0
        self.last_error = None
        self.task = None
        self.retention_applied = {}

    def start(self):
        self.task = asyncio.create_task(self.run(), name="archive-writer")

    def submit(self, kind, row):
        if self.queue.qsize() >= self.settings.queue_size:
            self.dropped += 1
            return
        try:
            self.queue.put_nowait((kind, row))
        except asyncio.QueueFull:
            self.dropped += 1

    def event(self, name, level="info", **fields):
        row = {"time": datetime.now(timezone.utc).isoformat(), "event": name, "level": level, **fields}
        self.events.append(row)
        self.submit("events", row)

    def frame(self, direction, serial, raw):
        if self.settings.frames:
            self.submit("frames", {"received_at": time.time(), "direction": direction,
                "serial": serial, "hex": raw.hex()})

    def measurement(self, row):
        if self.settings.measurements:
            self.submit("measurements", row)

    def write(self, kind, row):
        if kind == "device":
            atomic_json(self.directory/"devices"/(str(row["serial"])+".json"), row)
            return
        path = self.directory/(kind+".jsonl")
        payload = json.dumps(row, ensure_ascii=False, allow_nan=False)+"\n"
        maximum = self.settings.max_file_mb*1024*1024
        if path.exists() and path.stat().st_size+len(payload.encode()) > maximum:
            for index in range(self.settings.backups, 0, -1):
                source = path if index == 1 else self.directory/f"{kind}.{index-1}.jsonl"
                destination = self.directory/f"{kind}.{index}.jsonl"
                if source.exists():
                    os.chmod(source, 0o600)
                    source.replace(destination)
        # A lower backup limit must also reclaim files created with the old
        # setting, rather than leaving those files permanently outside rotation.
        if self.retention_applied.get(kind) != self.settings.backups:
            for backup in self.directory.glob(kind+".*.jsonl"):
                suffix = backup.name[len(kind)+1:-6]
                if suffix.isdecimal():
                    if int(suffix) > self.settings.backups:
                        backup.unlink()
                    else:
                        os.chmod(backup, 0o600)
            self.retention_applied[kind] = self.settings.backups
        descriptor = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
        if kind == "measurements" and not row.get("out_of_order"):
            atomic_json(self.directory/"latest"/(str(row["serial"])+".json"), row)

    async def run(self):
        while True:
            kind, row = await self.queue.get()
            try:
                await asyncio.to_thread(self.write, kind, row)
                self.last_error = None
            except (OSError, ValueError) as error:
                self.last_error = str(error)
                self.dropped += 1
                self.events.append({"time": datetime.now(timezone.utc).isoformat(),
                    "event": "archive_error", "level": "error", "error": str(error)})
            finally:
                self.queue.task_done()

    async def close(self):
        if self.task:
            try:
                await asyncio.wait_for(self.queue.join(), 5)
            except asyncio.TimeoutError:
                pass
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def status(self):
        return {"queued": self.queue.qsize(), "dropped": self.dropped, "last_error": self.last_error}
