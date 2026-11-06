"""Conservative observed identity, separate from configured model or measurements."""
import re
import time


def observed_identity(frame, peer):
    now = time.time()
    values = {"logger_serial": {"value": str(frame.serial), "source": "V5 header", "observed_at": now},
              "peer_ip": {"value": peer, "source": "TCP peer", "observed_at": now}}
    if frame.code == 0x4110 and len(frame.raw) == 330:
        raw = frame.raw[30:62].split(b"\0", 1)[0]
        if re.fullmatch(rb"LSW3_[A-Za-z0-9_.-]{4,27}", raw):
            values["logger_firmware"] = {"value": raw.decode("ascii"), "source": "V5 0x4110 / 330 bytes / offset 30", "observed_at": now}
    if frame.code == 0x4210 and len(frame.raw) == 2115:
        raw = frame.raw[142:158].split(b"\0", 1)[0]
        if re.fullmatch(rb"[A-Z0-9][A-Z0-9-]{5,15}", raw):
            values["inverter_serial"] = {"value": raw.decode("ascii"), "source": "Sofar HYD report 0x4210 / 2115 bytes / offset 142", "observed_at": now}
    return values
