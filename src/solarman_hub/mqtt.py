"""MQTT output only. Paho owns its network thread; asyncio owns application state."""
from __future__ import annotations
from . import __version__

import asyncio
from contextlib import suppress
import hashlib
import json
from pathlib import Path
import time
import socket

import paho.mqtt.client as paho

from .config import AppConfig, atomic_json


class Publisher:
    def __init__(self, data_dir: Path, event):
        self.data_dir = data_dir
        self.event = event
        self.client = None
        self.config = AppConfig()
        self.connected = False
        self.last_error = None
        self.last_publish = None
        self.latest = {}
        self.availability = {}
        self.published_availability = {}
        self.pending_samples = set()
        self.app_online_published = False
        self.published_discovery = set()
        self.discovery_cache = self.data_dir/"mqtt-discovery.json"
        try:
            self.known_discovery = set(json.loads(self.discovery_cache.read_text()))
        except (OSError, ValueError):
            self.known_discovery = set()
        self.loop = None

    @property
    def app_topic(self):
        return f"{self.config.mqtt.topic_prefix}/availability"

    async def configure(self, config: AppConfig):
        await self.close()
        self.config = config
        self.loop = asyncio.get_running_loop()
        self.published_discovery.clear()
        self.published_availability.clear()
        self.app_online_published = False
        configured = {logger.serial for logger in config.loggers if logger.enabled}
        self.latest = {serial: sample for serial, sample in self.latest.items() if serial in configured}
        self.availability = {serial: value for serial, value in self.availability.items() if serial in configured}
        self.pending_samples = set(self.latest)
        if not config.mqtt.enabled:
            self.connected = False
            return
        settings = config.mqtt
        client = paho.Client(paho.CallbackAPIVersion.VERSION2, client_id=settings.client_id)
        client.max_queued_messages_set(128)
        client.max_inflight_messages_set(10)
        client.reconnect_delay_set(1, 30)
        if settings.username or settings.password:
            client.username_pw_set(settings.username, settings.password)
        if settings.tls:
            client.tls_set()
        client.will_set(self.app_topic, "offline", qos=1, retain=True)

        def connected(client_, userdata, flags, reason, properties):
            self.loop.call_soon_threadsafe(self.on_connect, client_, reason)

        def disconnected(client_, userdata, flags, reason, properties):
            self.loop.call_soon_threadsafe(self.on_disconnect, client_, reason)

        def message(client_, userdata, msg):
            if msg.topic == f"{settings.discovery_prefix}/status" and msg.payload == b"online":
                self.loop.call_soon_threadsafe(self.republish)

        def connect_failed(client_, userdata):
            self.loop.call_soon_threadsafe(self.connection_failed, client_)

        client.on_connect = connected
        client.on_disconnect = disconnected
        client.on_message = message
        client.on_connect_fail = connect_failed
        self.client = client
        try:
            client.connect_async(settings.host, settings.port, keepalive=30)
            client.loop_start()
        except (OSError, ValueError):
            self.last_error = "Nie udało się rozpocząć połączenia z brokerem"
            self.event("mqtt_error", level="error", error=self.last_error)

    def on_connect(self, client, reason):
        if client is not self.client:
            return
        self.connected = not reason.is_failure
        self.last_error = None if self.connected else str(reason)
        if not self.connected:
            self.event("mqtt_error", level="warning", error=self.last_error)
            return
        client.subscribe(f"{self.config.mqtt.discovery_prefix}/status")
        self.app_online_published = False
        self.published_discovery.clear()
        self.republish()
        self.event("mqtt_connected")

    def on_disconnect(self, client, reason):
        if client is self.client:
            self.connected = False
            self.event("mqtt_disconnected", level="warning")

    def connection_failed(self, client):
        if client is self.client:
            self.connected = False
            self.last_error = "Broker MQTT jest nieosiągalny; ponawiam połączenie"

    def publish(self, topic, payload, retain=False):
        if not self.connected or not self.client:
            return False
        result = self.client.publish(topic, payload, qos=self.config.mqtt.qos, retain=retain)
        if result.rc != paho.MQTT_ERR_SUCCESS:
            self.last_error = "Ograniczona kolejka MQTT jest pełna lub broker jest niedostępny"
            return False
        self.last_publish = time.time()
        return True

    def discovery(self, logger, sample):
        settings = self.config.mqtt
        base = f"{settings.topic_prefix}/{logger.serial}"
        device = {"identifiers": [f"solarman_{logger.serial}"], "name": logger.name,
                  "manufacturer": "Solarman", "model": sample["profile"]}
        topics = {}
        for key, value in sample["values"].items():
            topic = f"{settings.discovery_prefix}/sensor/solarman_{logger.serial}/{key}/config"
            payload = {"name": value["name"], "unique_id": f"solarman_{logger.serial}_{key}",
                "state_topic": base+"/state", "value_template": "{{ value_json['values']['"+key+"'] }}",
                "availability_mode": "all", "availability": [{"topic": self.app_topic}, {"topic": base+"/availability"}],
                "expire_after": logger.stale_after, "device": device,
                "origin": {"name": "Solarman Hub", "sw_version": __version__}}
            if value.get("unit"):
                payload["unit_of_measurement"] = value["unit"]
            for field in ("device_class", "state_class"):
                if value.get(field):
                    payload[field] = value[field]
            topics[topic] = payload
        return topics

    def publish_sample(self, logger, sample):
        if not self.connected:
            return False
        complete = True
        topics = self.discovery(logger, sample) if self.config.mqtt.discovery else {}
        prefix = f"{self.config.mqtt.discovery_prefix}/sensor/solarman_{logger.serial}/"
        for obsolete in list(self.known_discovery):
            if obsolete.startswith(prefix) and obsolete not in topics:
                if self.publish(obsolete, "", retain=True):
                    self.known_discovery.discard(obsolete)
                else:
                    complete = False
        for topic, payload in topics.items():
            signature = (topic, hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
            if signature not in self.published_discovery:
                if self.publish(topic, json.dumps(payload), retain=True):
                    self.published_discovery.add(signature)
                    self.known_discovery.add(topic)
                else:
                    complete = False
        state = {"sample_time": sample["sample_time"], "received_at": sample["received_at"],
                 "values": {key: value["value"] for key, value in sample["values"].items()}}
        if time.time()-sample["received_at"] <= logger.stale_after:
            complete = self.publish(f"{self.config.mqtt.topic_prefix}/{logger.serial}/state", json.dumps(state), retain=False) and complete
        return complete

    def accept(self, logger, sample):
        self.latest[logger.serial] = sample  # at most one latest state per configured logger
        self.pending_samples.add(logger.serial)
        if self.publish_sample(logger, sample):
            self.pending_samples.discard(logger.serial)

    def set_available(self, serial, value):
        self.availability[serial] = value
        if self.connected and self.published_availability.get(serial) != value:
            if self.publish(f"{self.config.mqtt.topic_prefix}/{serial}/availability", "online" if value else "offline", retain=True):
                self.published_availability[serial] = value

    def republish(self):
        if not self.connected:
            return
        self.published_discovery.clear()
        self.published_availability.clear()
        self.pending_samples.update(self.latest)
        self.flush()

    def flush(self):
        """Retry bounded, coalesced output after a full Paho queue drains."""
        if not self.connected:
            return
        if not self.app_online_published:
            self.app_online_published = self.publish(self.app_topic, "online", retain=True)
            if not self.app_online_published:
                return
        configured = {logger.serial: logger for logger in self.config.loggers if logger.enabled}
        active_prefixes = ([f"{self.config.mqtt.discovery_prefix}/sensor/solarman_{serial}/" for serial in configured]
                           if self.config.mqtt.discovery else [])
        for topic in list(self.known_discovery):
            if not any(topic.startswith(prefix) for prefix in active_prefixes):
                if self.publish(topic, "", retain=True):
                    self.known_discovery.discard(topic)
        for serial, logger in configured.items():
            sample = self.latest.get(serial)
            if sample and serial in self.pending_samples and self.publish_sample(logger, sample):
                self.pending_samples.discard(serial)
            available = self.availability.get(serial, False)
            self.set_available(serial, available)

    async def close(self):
        client = self.client
        if client:
            if self.connected:
                # A clean DISCONNECT suppresses the broker's LWT. Confirm the
                # explicit offline publication before disconnecting, or a
                # retained "online" can survive a normal shutdown indefinitely.
                confirmed = False
                deadline = asyncio.get_running_loop().time() + 2
                while self.connected:
                    result = client.publish(self.app_topic, "offline", qos=1, retain=True)
                    remaining = deadline - asyncio.get_running_loop().time()
                    if result.rc == paho.MQTT_ERR_SUCCESS:
                        with suppress(RuntimeError, ValueError):
                            await asyncio.to_thread(result.wait_for_publish, timeout=max(0, remaining))
                            confirmed = result.is_published()
                        break
                    if remaining <= 0:
                        break
                    await asyncio.sleep(min(.05, remaining))
                if not confirmed:
                    # Do not suppress LWT with a clean DISCONNECT when PUBACK
                    # never arrived: let the broker report the lost connection.
                    transport = client.socket()
                    if transport:
                        with suppress(OSError):
                            transport.shutdown(socket.SHUT_RDWR)
                    self.event("mqtt_offline_unconfirmed", level="warning")
            self.client = None
            await asyncio.to_thread(client.disconnect)
            await asyncio.to_thread(client.loop_stop)
            try:
                await asyncio.to_thread(atomic_json, self.discovery_cache, sorted(self.known_discovery))
            except OSError:
                pass
        self.connected = False

    def status(self):
        return {"enabled": self.config.mqtt.enabled, "connected": self.connected,
                "last_error": self.last_error, "last_publish": self.last_publish,
                "cached_states": len(self.latest)}
