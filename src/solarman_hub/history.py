"""Bounded measurement history. SQLite work never runs in the TCP event loop."""
import asyncio
from contextlib import closing
from datetime import datetime
import hashlib
import json
import math
import os
import threading
from pathlib import Path
import re
import sqlite3
import time


class History:
    def __init__(self, data_dir, settings, event):
        self.path = Path(data_dir)/"history.sqlite3"
        self.archive = Path(data_dir)/"archive"
        self.settings = settings
        self.event = event
        self.queue = asyncio.Queue(maxsize=256)
        self.task = None
        self.last_error = None
        self.dropped = 0
        self.importing = False
        self.imported = 0
        self.size = 0
        self.stopping = threading.Event()

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=3)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=3000")
        return connection

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.execute("PRAGMA auto_vacuum=FULL")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA journal_size_limit=1048576")
            db.execute("PRAGMA wal_autocheckpoint=128")
            db.executescript('''CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY, serial INTEGER NOT NULL, sampled REAL NOT NULL,
                received REAL NOT NULL, profile TEXT NOT NULL, revision TEXT NOT NULL,
                digest TEXT NOT NULL UNIQUE, document TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS samples_lookup ON samples(serial, sampled DESC, id DESC);
                CREATE INDEX IF NOT EXISTS samples_received ON samples(received);
                CREATE INDEX IF NOT EXISTS samples_profile ON samples(serial, profile, revision, sampled);
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);''')
            db.commit()
        os.chmod(self.path, 0o600)
        self.maintain()

    async def start(self):
        try:
            await asyncio.to_thread(self.initialize)
        except (OSError, sqlite3.Error) as error:
            self.last_error = str(error)
            self.event("history_error", level="error", error=str(error))
        self.task = asyncio.create_task(self.run(), name="history-writer")

    def submit(self, sample):
        if not self.settings.history_enabled:
            return
        try:
            self.queue.put_nowait(sample)
        except asyncio.QueueFull:
            self.dropped += 1

    @staticmethod
    def timestamp(sample):
        value = sample.get("sample_time")
        result = datetime.fromisoformat(value).timestamp() if value else float(sample["received_at"])
        if not math.isfinite(result):
            raise ValueError("Invalid history timestamp")
        return result

    def insert(self, db, sample):
        timestamp = self.timestamp(sample)
        if self.settings.history_days and float(sample["received_at"]) < time.time()-self.settings.history_days*86400:
            return False
        canonical = {key: sample.get(key) for key in ("serial", "sample_time", "profile", "profile_revision", "values")}
        if not sample.get("sample_time"):
            canonical["received_at"] = sample["received_at"]
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, allow_nan=False).encode()).hexdigest()
        cursor = db.execute("INSERT OR IGNORE INTO samples(serial,sampled,received,profile,revision,digest,document) VALUES(?,?,?,?,?,?,?)",
            (sample["serial"], timestamp, sample["received_at"], sample["profile"], sample["profile_revision"], digest,
             json.dumps(sample, ensure_ascii=False, allow_nan=False)))
        return bool(cursor.rowcount)

    def check_capacity(self):
        if self.size > self.settings.history_max_mb*1024*1024:
            raise OSError("History storage limit: waiting for readers to release WAL")

    def write(self, sample):
        self.maintain()
        self.check_capacity()
        with closing(self.connect()) as db:
            self.insert(db, sample)
            db.commit()
        self.maintain()

    def maintain(self):
        with closing(self.connect()) as db:
            if self.settings.history_days:
                db.execute("DELETE FROM samples WHERE received < ?", (time.time()-self.settings.history_days*86400,))
                db.commit()
            # FULL auto-vacuum shrinks deleted pages. Reserve space for a write and WAL.
            maximum = self.settings.history_max_mb*1024*1024
            target = max(1024*1024, maximum-2*1024*1024)
            for _ in range(64):
                size = db.execute("PRAGMA page_count").fetchone()[0]*db.execute("PRAGMA page_size").fetchone()[0]
                if size <= target:
                    break
                count=db.execute("SELECT count(*) FROM samples").fetchone()[0]
                amount=min(65536,max(1,int(count*(1-target/max(1,size))*1.1)))
                db.execute("DELETE FROM samples WHERE id IN (SELECT id FROM samples ORDER BY received,id LIMIT ?)",(amount,))
                db.commit()
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.size = sum(path.stat().st_size for path in self.path.parent.glob(self.path.name+"*") if path.is_file())

    def import_archive(self):
        with closing(self.connect()) as db:
            if db.execute("SELECT 1 FROM metadata WHERE key='jsonl_imported'").fetchone():
                return
        self.check_capacity()
        self.importing = True
        try:
            paths = sorted(self.archive.glob("measurements.*.jsonl"), reverse=True)
            paths += [self.archive/"measurements.jsonl"]
            for path in paths:
                if not path.is_file():
                    continue
                with path.open(encoding="utf-8") as stream, closing(self.connect()) as db:
                    batch = 0
                    for line in stream:
                        if self.stopping.is_set():
                            return
                        try:
                            self.imported += int(self.insert(db, json.loads(line)))
                        except (ValueError, KeyError, TypeError):
                            continue
                        batch += 1
                        if batch % 128 == 0:
                            db.commit()
                            self.maintain()
                            self.check_capacity()
                    db.commit()
                self.maintain()
                self.check_capacity()
            with closing(self.connect()) as db:
                db.execute("INSERT OR REPLACE INTO metadata VALUES('jsonl_imported','1')")
                db.commit()
        finally:
            self.importing = False

    async def run(self):
        if self.settings.history_enabled:
            try:
                await asyncio.to_thread(self.import_archive)
            except (OSError, sqlite3.Error, ValueError) as error:
                self.last_error = str(error)
                self.event("history_import_error", level="warning", error=str(error))
        while True:
            sample = None
            acquired = False
            try:
                try:
                    sample = await asyncio.wait_for(self.queue.get(), 60)
                    acquired = True
                except TimeoutError:
                    pass
                if sample is not None:
                    await asyncio.to_thread(self.write, sample)
                else:
                    await asyncio.to_thread(self.maintain)
                self.last_error = None
            except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as error:
                self.last_error = str(error)
                if sample is not None:
                    self.dropped += 1
                self.event("history_error", level="error", error=str(error))
            finally:
                if acquired:
                    self.queue.task_done()

    @staticmethod
    def bounds(start, end):
        start, end = float(start), float(end)
        if not all(map(math.isfinite, (start, end))) or end < start or end-start > 3660*86400:
            raise ValueError("Invalid history time range")
        return start, end

    def rows(self, serial, start, end, limit=50, before=None):
        start, end = self.bounds(start, end)
        limit = max(1, min(int(limit), 200))
        if not self.path.exists():
            return {"samples": [], "next_before": None}
        with closing(self.connect()) as db:
            where = "serial=? AND sampled>=? AND sampled<=?"
            parameters = [serial, start, end]
            if before is not None:
                cursor = db.execute("SELECT sampled,id FROM samples WHERE serial=? AND id=?", (serial, int(before))).fetchone()
                if cursor is None:
                    raise ValueError("Invalid history cursor")
                where += " AND (sampled<? OR (sampled=? AND id<?))"
                parameters += [cursor["sampled"], cursor["sampled"], cursor["id"]]
            rows = db.execute(f"SELECT id,sampled,document FROM samples WHERE {where} ORDER BY sampled DESC,id DESC LIMIT ?", (*parameters, limit+1)).fetchall()
            samples = [{**json.loads(row["document"]), "history_id": row["id"], "sampled_at": row["sampled"]} for row in rows[:limit]]
            return {"samples": samples, "next_before": samples[-1]["history_id"] if len(rows)>limit else None}

    def series(self, serial, field, profile, revision, start, end, points=600, gap_seconds=900):
        start, end = self.bounds(start, end)
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", field):
            raise ValueError("Invalid field identifier")
        points = max(4, min(int(points), 1500))
        bucket_width = max((end-start)/max(1, points//4), .001)
        buckets = {}
        scanned, segment, previous = 0, 0, None
        name, unit = field, ""
        with closing(self.connect()) as db:
            cursor = db.execute("SELECT sampled,document FROM samples WHERE serial=? AND profile=? AND revision=? AND sampled>=? AND sampled<=? ORDER BY sampled,id LIMIT 100001",
                                (serial, profile, revision, start, end))
            for row in cursor:
                scanned += 1
                if scanned > 100000:
                    break
                sample = json.loads(row["document"])
                spec = sample.get("values", {}).get(field)
                if not spec or not isinstance(spec.get("value"), (int, float)) or not math.isfinite(spec["value"]):
                    continue
                name, unit = spec["name"], spec.get("unit", "")
                timestamp = row["sampled"]
                if previous is not None and timestamp-previous > gap_seconds:
                    segment += 1
                previous = timestamp
                point = {"time": timestamp, "value": spec["value"], "segment": segment}
                index = min(max(0, int((timestamp-start)/bucket_width)), points//4-1)
                bucket = buckets.get(index)
                if bucket is None:
                    buckets[index] = [point, point, point, point]
                else:
                    if point["value"] < bucket[1]["value"]: bucket[1] = point
                    if point["value"] > bucket[2]["value"]: bucket[2] = point
                    bucket[3] = point
        result = []
        for index in sorted(buckets):
            unique = {(point["time"],point["value"],point["segment"]): point for point in buckets[index]}
            result.extend(sorted(unique.values(), key=lambda point: point["time"]))
        return {"field": field, "name": name, "unit": unit, "profile": profile, "profile_revision": revision,
                "points": result, "scanned": min(scanned,100000), "truncated": scanned>100000, "from": start, "to": end}

    def status(self):
        return {"enabled": self.settings.history_enabled, "queued": self.queue.qsize(), "dropped": self.dropped,
                "last_error": self.last_error, "size_bytes": self.size, "importing": self.importing, "imported": self.imported,
                "retention_days": self.settings.history_days, "max_mb": self.settings.history_max_mb}

    async def close(self):
        self.stopping.set()
        if self.task:
            try:
                await asyncio.wait_for(self.queue.join(), 5)
            except TimeoutError:
                pass
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
