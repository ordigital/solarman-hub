"""Solarman V5 framing only. This module knows nothing about measurement profiles."""
from dataclasses import dataclass
from datetime import datetime
import struct
import time
from zoneinfo import ZoneInfo

ACK_CODES = {0x4110: 0x1110, 0x4210: 0x1210, 0x4310: 0x1310, 0x4710: 0x1710, 0x4810: 0x1810}
MAX_FRAME = 16384


@dataclass(frozen=True)
class Frame:
    raw: bytes
    code: int
    serial: int
    sequence: int

    @classmethod
    def parse(cls, raw):
        if len(raw) < 13 or len(raw) > MAX_FRAME or raw[0] != 0xa5 or raw[-1] != 0x15:
            raise ValueError("Nieprawidłowy format V5")
        if int.from_bytes(raw[1:3], "little")+13 != len(raw) or sum(raw[1:-2]) & 255 != raw[-2]:
            raise ValueError("Nieprawidłowa długość lub suma kontrolna V5")
        return cls(raw, int.from_bytes(raw[3:5], "little"), int.from_bytes(raw[7:11], "little"), raw[6])


class Framer:
    def __init__(self):
        self.buffer = bytearray()
        self.invalid = 0

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while self.buffer:
            if self.buffer[0] != 0xa5:
                del self.buffer[0]
                self.invalid += 1
                continue
            if len(self.buffer) < 3:
                break
            size = int.from_bytes(self.buffer[1:3], "little")+13
            if size > MAX_FRAME:
                del self.buffer[0]
                self.invalid += 1
                continue
            if len(self.buffer) < size:
                break
            try:
                frame = Frame.parse(bytes(self.buffer[:size]))
            except ValueError:
                del self.buffer[0]
                self.invalid += 1
                continue
            del self.buffer[:size]
            frames.append(frame)
        return frames


def local_ack(frame: Frame, sequence: int, timezone: str, timestamp=None):
    if frame.code not in ACK_CODES:
        raise ValueError("Brak definicji ACK dla tego rodzaju ramki")
    timestamp = int(time.time() if timestamp is None else timestamp)
    offset = int(datetime.fromtimestamp(timestamp, ZoneInfo(timezone)).utcoffset().total_seconds()/60)
    kind = frame.raw[11] if len(frame.raw) > 13 else 0
    body = struct.pack("<HHBBI", 10, ACK_CODES[frame.code], sequence & 255, frame.sequence, frame.serial)
    body += struct.pack("<BBIi", kind, 1, timestamp, offset)
    return Frame.parse(b"\xa5"+body+bytes([sum(body) & 255, 0x15]))
