# Architecture

One process runs an asyncio TCP listener and aiohttp control plane. Paho has its own MQTT network thread; callbacks return into the asyncio loop. No shared mutable domain state is owned by Paho threads.

Data path: TCP → V5 framing/validation → relay session → original cloud bytes/ACK or bounded local fallback. A separate observation path runs pure profile decoding and hands results to bounded archive/MQTT outputs. Decoder errors must not close the relay. No MQTT input commands are supported.

## Boundaries

- `auth.py`: optional PBKDF2-SHA256 administrator password (600,000 iterations, random 16-byte salt), atomic private hash storage; the existing token remains valid for recovery and bearer API access. Password verification runs off the event loop with at most two concurrent checks. CLI password changes require a process restart.
- `config.py`: typed settings, validation, secret-preserving updates, atomic persistence and revisions. Config snapshots are treated as immutable. Public representation redacts password.
- `protocol.py`: stream framing, checksum, identifiers, known ACK mapping and local ACK. Knows no inverter measurement fields.
- `profiles.py`: validated declarative profile definitions and pure byte-to-values conversion. Built-in resources + custom data directory, no executable plugins.
- `relay.py`: per-logger session, bidirectional cloud socket, ACK correlation and reconnect/bootstrap. Owns deadlines and ACK exclusivity; unknown frames may pass through without decoding.
- `history.py`: bounded SQLite worker and queries, reception-age and physical-size retention, one-time JSONL backfill, profile-aware chart downsampling. Relay never waits for database writes.
- `identity.py`: conservative identification from verified V5 layouts, with source/time. Configured model remains distinct.
- `bundles.py`: validated ESP32 profile imports, visible conflicts, saved settings only; no automatic apply or device changes.
- `guides.py` + `guides/*.md`: nine localized guides with stable chapter IDs and shared TOC generation. The ESP32 / Flashing view reuses the ESP32 and OTA chapters through static/guide.js; downloads and commands have one UI entry point.
- `runtime.py`: composition, explicit apply, state/freshness and orchestration. Rejects unconfigured/disabled serials and duplicate sessions. Separate saved/applied revisions.
- `archive.py`: bounded async handoff to thread-based rotating JSONL files. Failure/drop counters visible without stopping transport.
- `mqtt.py`: bounded latest-per-logger state and Paho output queue, discovery, availability, birth handling. `mqtt_probe.py` tests independent credentials without publishing.
- `web.py`: authenticated API, CSRF, configuration operations, restricted downloads, localized chapter-based guide and static assets. No shell execution or automatic device reconfiguration.
- `static/i18n.js` + `static/locales.json`: nine data-only interface catalogs, English source messages and Polish default; browser-local preference. Changing language updates labels without reloading config or translating user-authored data. Responsive breakpoints account for the interface scale.
- `static/`: dependency-free local browser UI. User-controlled text is inserted with textContent; only the Markdown renderer's HTML enters innerHTML, with raw HTML disabled.
- `__main__.py`: CLI, lifecycle and binding overrides.

## Extensions

A different report layout within V5: add/clone a JSON profile and a sanitized fixture + expected values. Keep offset/scaling knowledge out of relay/runtime/web. Match code+length is a format guard, not model autodetection; users choose profile explicitly.

A truly different wire protocol: add a focused protocol/session adapter and tests first. Do not generalize every module into a plugin interface ahead of a second real implementation. MQTT sees normalized samples regardless of decoder.

A new setting: add it to the single Pydantic model, expose it in the panel, document apply/restart behavior and add validation tests when meaningful. Do not add an HA API IP/token: this product connects to MQTT broker only.

## Operational invariants

- Runtime failure of cloud/MQTT/archive is visible independently.
- TCP connectivity, measurement freshness and cloud connectivity are distinct.
- Persisted latest values remain old after restart; receipt of old/duplicate samples must not make them fresh.
- Queues are bounded. Dropped archival/telemetry data is acceptable and counted; indefinite blocking of relay is not.
- Local ACK does not imply cloud delivery. There is no replay/backfill contract.
- Config and profile changes require explicit apply; socket binding requires restart.
- Management secrets belong to the data directory/environment; never to shipped profiles or fixtures.

## ESP32 Companion

`firmware/esp32-companion` is optional and independent of the Python relay. Modes are exclusive: local V5 receiver/proxy with one upstream, or passive PCAP. `v5_protocol.h` isolates framing/ACK and has native host tests. `receiver.cpp` owns bounded queues, original ACK or local fallback, bootstrap and late-ACK exclusion. `capture.cpp` filters in the Wi-Fi callback and moves storage to a worker. `main.cpp` owns NVS, authenticated HTTP/CSRF and OTA. `web_ui.h` is English-only. The builder embeds the canonical profile; unknown maps are unverified drafts. Product artifacts in dist are packaged into the Hub via a resource symlink and Docker COPY. OTA commits only after the complete accepted request; two slots do not imply automatic rollback.

`compose.yaml` also has an opt-in `tools` profile with the one-shot `esp-flash` service. Its separate Dockerfile installs pinned esptool and verifies bundled image hashes. Only the selected serial device is passed through; the web server has no USB permissions or flashing endpoint. Normal Hub startup never flashes hardware.

The companion uses `include/bounded_web_server.h` to retain Arduino routing while replacing its blocking request parser. Authentication and route limits are checked before reading a body. Headers, JSON and single-file multipart uploads have independent size, idle and total deadlines; completion cleanup resumes the receiver/capture after every rejected or interrupted OTA. HTTP reads advance only through available bounded chunks. Socket checks avoid Arduino 2.0.17's zero-length-recv/stale-errno behavior. A one-result DNS worker and expiring address cache keep hostname resolution off the receiver loop, with a bounded initial resolution wait before local fallback.

Cloud-link generations own their reader and pending ACK futures. Connect/bootstrap is serialized; cleanup of an old generation cannot close a replacement connection. Session shutdown is idempotent and always releases the logger identity. Measurements more than five minutes in the future are retained diagnostically but cannot replace live/cache/MQTT state. Repeated DST hours use reception time to disambiguate their UTC offset.

## Proxmox provisioning

`scripts/proxmox-vm.sh` runs on a Proxmox VE 8/9 amd64 host. It validates an unused VM ID, storage, Linux bridge/VLAN and DHCP/static IPv4 settings, confirms the summary, then checks the official Debian 13 cloud image against its HTTPS SHA-512 manifest. Cloud-Init starts a retryable systemd bootstrap inside the new VM; it installs Debian Docker packages and runs the existing Compose project. Only hashed web/console passwords enter the private snippet; the generated console password is kept in a root-only host access file. A chosen web password is installed into the normal Docker data volume before the listener starts. Failed creation leaves the VM for inspection. Snippets remain external to VM backups and must accompany migration/restore. Provisioning tests run without a hypervisor; real Proxmox acceptance is still outstanding.

The HYD G3 profile includes `battery1_cycles`: unsigned 16-bit big-endian, scale 1, register `0x060A`, byte offset 474 in the full 2115-byte V5 frame. Its register meaning comes from the [legacy Solarman G3 HYD map](https://github.com/StephanJoubert/home_assistant_solarman/blob/main/custom_components/solarman/inverter_definitions/sofar_g3hyd.yaml); position was checked against adjacent known battery registers and 24 private archived reports. Unlike the original 47 measurements, this field was not independently compared with a cloud/BMS display. Fixtures use a synthetic counter, never private frames. Existing field IDs and the profile ID remain unchanged.
