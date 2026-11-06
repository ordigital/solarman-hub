"""Data-only decoder profiles. No eval, imports, sockets or device identifiers."""
from datetime import datetime
from decimal import Decimal
import hashlib
from importlib.resources import files
import math
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from .config import Model, atomic_json
from .protocol import Frame, MAX_FRAME


class Match(Model):
    code: int = Field(default=0x4210, ge=0, le=65535, strict=True)
    length: int = Field(ge=13, le=MAX_FRAME, strict=True)


class ValueField(Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    offset: int = Field(ge=0, le=MAX_FRAME, strict=True)
    size: Literal[1, 2, 4, 8] = 2
    endian: Literal["big", "little"] = "big"
    signed: bool = False
    scale: float = Field(default=1, allow_inf_nan=False)
    unit: str = Field(default="", max_length=24)
    device_class: str | None = None
    state_class: Literal["measurement", "total", "total_increasing"] | None = "measurement"
    register_hint: str | None = Field(default=None, alias="register")


class Timestamp(Model):
    offsets: list[int] = Field(min_length=6, max_length=6)
    size: Literal[1, 2] = 2
    endian: Literal["big", "little"] = "big"
    year_base: int = Field(default=2000, ge=0, le=9000)


class Profile(Model):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=3000)
    manufacturer: str = ""
    model: str = ""
    match: Match
    timestamp: Timestamp | None = None
    fields: list[ValueField] = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def valid_offsets(self):
        ids = [field.id for field in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("Identyfikatory pól muszą być unikalne")
        for field in self.fields:
            if field.offset+field.size > self.match.length-2:
                raise ValueError(f"Pole {field.id} wykracza poza dane ramki")
        if self.timestamp:
            if any(offset < 0 or offset+self.timestamp.size > self.match.length-2 for offset in self.timestamp.offsets):
                raise ValueError("Czas wykracza poza dane ramki")
        return self

    @property
    def revision(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:12]

    def decode(self, frame: Frame, timezone: str, reference_time=None):
        if frame.code != self.match.code or len(frame.raw) != self.match.length:
            raise ValueError(f"Profil oczekuje kodu 0x{self.match.code:04x} i {self.match.length} bajtów")
        values = {}
        for field in self.fields:
            raw = int.from_bytes(frame.raw[field.offset:field.offset+field.size], field.endian, signed=field.signed)
            value = float(Decimal(raw)*Decimal(str(field.scale)))
            if not math.isfinite(value):
                raise ValueError(f"Wartość pola {field.id} przekracza zakres liczbowy")
            values[field.id] = {"name": field.name, "value": value, "raw": raw, "unit": field.unit,
                "device_class": field.device_class, "state_class": field.state_class}
        sample_time = None
        if self.timestamp:
            spec = self.timestamp
            parts = [int.from_bytes(frame.raw[o:o+spec.size], spec.endian) for o in spec.offsets]
            parts[0] += spec.year_base
            zone = ZoneInfo(timezone)
            wall = datetime(*parts)
            candidates = [wall.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
            candidates = [candidate for candidate in candidates
                if datetime.fromtimestamp(candidate.timestamp(), zone).replace(tzinfo=None) == wall]
            if not candidates:
                raise ValueError("Sample local time does not exist in the configured timezone")
            # Fall-back hours occur twice. Live reception disambiguates their
            # offsets; offline previews without a reference remain deterministic.
            selected = min(candidates, key=lambda value: abs(value.timestamp()-reference_time)) if reference_time is not None else candidates[0]
            sample_time = selected.isoformat()
        return {"profile": self.id, "profile_revision": self.revision, "sample_time": sample_time,
                "values": values}


class ProfileStore:
    def __init__(self, data_dir: Path):
        self.directory = data_dir/"profiles"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.builtin = {}
        for resource in files("solarman_hub").joinpath("builtin_profiles").iterdir():
            if resource.name.endswith(".json"):
                profile = Profile.model_validate_json(resource.read_text())
                self.builtin[profile.id] = profile

    def load(self):
        result = dict(self.builtin)
        for path in sorted(self.directory.glob("*.json")):
            profile = Profile.model_validate_json(path.read_text())
            if profile.id in result:
                raise ValueError(f"Powielony identyfikator profilu: {profile.id}")
            result[profile.id] = profile
        return result

    def documents(self):
        return {key: value.model_dump() for key, value in self.load().items()}

    def save(self, profile: Profile):
        if profile.id in self.builtin:
            raise ValueError("Profil wbudowany jest tylko do odczytu. Utwórz kopię z nowym id.")
        atomic_json(self.directory/(profile.id+".json"), profile.model_dump())

    def delete(self, identifier):
        if identifier in self.builtin or identifier not in self.load():
            raise ValueError("Nie można usunąć tego profilu")
        (self.directory/(identifier+".json")).unlink()
