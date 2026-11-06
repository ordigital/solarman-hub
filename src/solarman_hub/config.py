"""Validated configuration and durable atomic persistence. No network access."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Port = Annotated[int, Field(ge=1, le=65535, strict=True)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True, serialize_by_alias=True)


class Server(Model):
    tcp_host: str = "0.0.0.0"
    tcp_port: Port = 10000
    web_host: str = "0.0.0.0"
    web_port: Port = 8080
    handshake_timeout: float = Field(default=15, ge=1, le=120, allow_inf_nan=False)
    idle_timeout: float = Field(default=400, ge=30, le=3600, allow_inf_nan=False)
    max_connections: int = Field(default=16, ge=1, le=256, strict=True)
    timezone: str = "Europe/Warsaw"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Nieznana strefa czasowa") from error
        return value


class Cloud(Model):
    enabled: bool = True
    host: str = Field(default="access3.solarmanpv.com", min_length=1, max_length=253)
    port: Port = 10000
    connect_timeout: float = Field(default=4, ge=.1, le=30, allow_inf_nan=False)
    ack_timeout: float = Field(default=8, ge=.1, le=60, allow_inf_nan=False)


class Logger(Model):
    serial: int = Field(ge=1, le=0xffffffff, strict=True)
    name: str = Field(default="Logger", min_length=1, max_length=80)
    allowed_ip: str = ""
    profile: str | None = "sofar-hyd-g3-2115"
    stale_after: int = Field(default=900, ge=30, le=86400, strict=True)
    enabled: bool = True
    protocol: Literal["solarman-v5"] = "solarman-v5"

    @field_validator("allowed_ip")
    @classmethod
    def valid_ip(cls, value):
        if value:
            import ipaddress
            ipaddress.ip_address(value)
        return value


class MQTT(Model):
    enabled: bool = False
    host: str = Field(default="homeassistant.local", min_length=1, max_length=253)
    port: Port = 1883
    username: str = Field(default="", max_length=256)
    password: str = Field(default="", max_length=4096, repr=False)
    tls: bool = False
    topic_prefix: str = "solarman_hub"
    discovery_prefix: str = "homeassistant"
    client_id: str = "solarman-hub"
    discovery: bool = True
    qos: Literal[0, 1] = 1

    @field_validator("topic_prefix", "discovery_prefix", "client_id")
    @classmethod
    def topic_safe(cls, value):
        if not value or len(value) > 128 or any(c in value for c in "+#\x00 ") or value.startswith("/") or value.endswith("/"):
            raise ValueError("Nieprawidłowy identyfikator lub prefiks MQTT")
        return value


class Storage(Model):
    history_enabled: bool = True
    history_days: int = Field(default=30, ge=0, le=3650, strict=True)
    history_max_mb: int = Field(default=128, ge=8, le=16384, strict=True)
    frames: bool = True
    measurements: bool = True
    max_file_mb: int = Field(default=10, ge=1, le=1024, strict=True)
    backups: int = Field(default=5, ge=1, le=100, strict=True)
    queue_size: int = Field(default=256, ge=16, le=4096, strict=True)


class AppConfig(Model):
    schema_version: Literal[1] = 1
    server: Server = Field(default_factory=Server)
    cloud: Cloud = Field(default_factory=Cloud)
    mqtt: MQTT = Field(default_factory=MQTT)
    storage: Storage = Field(default_factory=Storage)
    loggers: list[Logger] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def unique_loggers(self):
        serials = [logger.serial for logger in self.loggers]
        if len(serials) != len(set(serials)):
            raise ValueError("Numery seryjne loggerów muszą być unikalne")
        return self


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="."+path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.chmod(temp, 0o600)
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def public_config(config: AppConfig):
    data = config.model_dump()
    data["mqtt"].pop("password")
    data["mqtt"]["password_set"] = bool(config.mqtt.password)
    return data


class ConfigStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.path = data_dir/"config.json"
        if not self.path.exists():
            atomic_json(self.path, AppConfig().model_dump())

    def load(self):
        return AppConfig.model_validate_json(self.path.read_text())

    def candidate(self, data):
        data = json.loads(json.dumps(data))
        mqtt = data.setdefault("mqtt", {})
        mqtt.pop("password_set", None)
        clear = mqtt.pop("clear_password", False)
        if not isinstance(clear, bool):
            raise ValueError("clear_password musi być wartością logiczną")
        if clear:
            mqtt["password"] = ""
        elif not mqtt.get("password"):
            mqtt["password"] = self.load().mqtt.password
        return AppConfig.model_validate(data)

    def save(self, config: AppConfig):
        atomic_json(self.path, config.model_dump())

    def revision(self, profiles):
        material = {"config": self.load().model_dump(), "profiles": profiles}
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:16]
