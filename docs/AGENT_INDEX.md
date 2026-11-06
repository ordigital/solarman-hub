# Agent project index

This is the canonical navigation map for an agent starting without conversation history. Read [AGENTS.md](../AGENTS.md), then this index, then only the task-relevant source and tests. Use [ARCHITECTURE.md](ARCHITECTURE.md) for module boundaries and design decisions; use [README.md](../README.md) for product behavior and installation.

Do not read every source file, translation, capture or binary to find an entry point. Search the relevant module with `rg`; use `rg --files` for unfamiliar paths. If the index disagrees with the source, verify the affected area and repair the index in the same change.

## Repository map

| Location | Purpose |
|---|---|
| [src/solarman_hub](../src/solarman_hub) | Python application: V5 transport, decoding, storage, MQTT, web API and CLI |
| [static](../src/solarman_hub/static) | Dependency-free browser UI: HTML/CSS, JavaScript and language catalogs |
| [builtin_profiles](../src/solarman_hub/builtin_profiles) | Canonical declarative inverter/report maps; no installation identifiers |
| [firmware/esp32-companion](../firmware/esp32-companion) | Optional standalone ESP32 receiver/relay, passive capture, profile builder and OTA |
| [scripts/proxmox-vm.sh](../scripts/proxmox-vm.sh) | Interactive Proxmox host provisioner; Docker and Hub run inside the new Debian VM |
| [tests](../tests) | Backend, browser, native firmware and optional broker/hardware tests; sanitized fixtures in `tests/fixtures/` |
| [docs](.) | Architecture, development, audit, translated README files and Proxmox instructions |
| [guides](../src/solarman_hub/guides) | Canonical localized user guides served by the web panel |
| [pyproject.toml](../pyproject.toml), [Dockerfile](../Dockerfile), [compose.yaml](../compose.yaml), [CI](../.github/workflows/ci.yml) | Dependencies/package resources, container build, deployment and automated checks |

## Find the change

In this table, Python and `static/` paths are relative to `src/solarman_hub/`; test filenames are relative to `tests/`. Firmware paths are relative to `firmware/esp32-companion/`. Start with the listed files, then follow their direct dependencies as needed.

| Task | Entry points / related files | Focused tests |
|---|---|---|
| Setting, default, validation or secret-preserving save | `config.py`: `AppConfig`, `ConfigStore`, `public_config`; `web.py`, `static/app.js`, `static/index.html` | `test_backend.py`, `test_web.py` |
| Start, stop, apply, reconnect or measurement freshness | `__main__.py`; `runtime.py`: `Runtime.start`, `apply`, `observe`, `tick`, `close` | `test_backend.py`, `test_audit_regressions.py` |
| V5 framing, checksum or local ACK | `protocol.py`: `Frame`, `Framer`, `local_ack` | `test_backend.py`, `test_audit_regressions.py` |
| Cloud relay, ACK routing, reconnect or concurrent sessions | `relay.py`: `Session`, `CloudLink`; lifecycle in `runtime.py` | `test_backend.py`, `test_audit_regressions.py` |
| Measurement map or decoder field | `builtin_profiles/*.json`; `profiles.py`: `Profile.decode`, `ProfileStore` | `test_backend.py`; `fixtures/sofar-report.hex`, `fixtures/sofar-expected.json`; MQTT/browser count checks |
| Profile import, clone or ESP32 bundle | `bundles.py`: `Bundle`, `preview`, `install`; `profiles.py`, `web.py`, `static/app.js` | `test_bundles_guides.py`, `test_web.py`, `test_browser.py` |
| MQTT connection, publishing, HA Discovery or availability | `mqtt.py`: `Publisher`; `runtime.py`, `config.py` | `test_backend.py`, `test_audit_regressions.py`; opt-in `test_mqtt_integration.py` |
| MQTT test button or its error message | `mqtt_probe.py`: `probe`; `web.py`: `mqtt_test`; `static/app.js`: `api`, `test-mqtt` handler | `test_web.py`, `test_browser.py`; opt-in broker test |
| History storage, retention, import or chart queries | `history.py`: `History`; `config.py`: `Storage`; API handlers in `web.py` | `test_history.py`, `test_audit_regressions.py` |
| History navigation or chart rendering | `static/history.js`: `HistoryUI`; `static/index.html`, `static/style.css`, history API | `test_browser.py`, `test_history.py` |
| Device identity or Devices page | `identity.py`: `observed_identity`; `runtime.py`, `static/devices.js` | `test_history.py`, `test_browser.py` |
| Raw archive, event logs, rotation or disk failure | `archive.py`: `Archive`; `config.py`: `Storage` | `test_backend.py`, `test_audit_regressions.py` |
| Password, token, session, CSRF or API permissions | `auth.py`; `web.py`: `admin_token`, `create_app`; password CLI in `__main__.py` | `test_password_auth.py`, `test_web.py`, `test_browser.py` |
| General UI, navigation, layout or notifications | `static/index.html`, `static/style.css`, `static/app.js`; feature-specific JS above | `test_browser.py`; syntax-check changed JavaScript |
| Interface language or new UI wording | `static/i18n.js`: `I18n`; `static/locales.json`; source messages in HTML/JS/API | `test_i18n.py`, nine-language `test_browser.py` |
| User guide, contents or firmware instructions | `guides.py`: `render_guide`, `CHAPTERS`; `guides/*.md`, `static/guide.js` | `test_bundles_guides.py`, `test_browser.py` |
| README / Proxmox prose | Root `README.md` → `docs/readme/*.md`; `docs/proxmox/en.md` → its eight translations | Check local links, matching fenced commands and complete language navigation |
| Proxmox wizard, network questions or first-boot setup | Root `scripts/proxmox-vm.sh`: `main`, `configure_network`, `build_cloud_config`; embedded guest bootstrap | `test_proxmox_installer.py`; a real VM is a separate operator test |
| Docker build, port mapping or package contents | Root `Dockerfile`, `compose.yaml`, `.dockerignore`, `pyproject.toml`; flash tool `Dockerfile.flash` | Separate-port image smoke test; `test_bundles_guides.py` for bundled resources |
| ESP32 configuration, setup Wi-Fi, HTTP routes, NVS or OTA | `src/main.cpp`, `include/companion.h`, `include/web_ui.h`, `include/bounded_web_server.h` | Build firmware; opt-in `test_esp32_hardware.py` |
| ESP32 V5 receiver/relay or passive PCAP | `src/receiver.cpp`, `src/capture.cpp`, `include/v5_protocol.h` | `test_firmware_protocol.py`; build; isolated hardware tests as appropriate |
| Firmware dependencies, embedded map or downloads | `platformio.ini`, `tools/resources.py`, `tools/package.py`, `dist/`; Hub download routes in `web.py` | Build/package, verify hashes; `test_bundles_guides.py` |
| Dependency, app version or CI change | Root `pyproject.toml`, `src/solarman_hub/__init__.py`, `.github/workflows/ci.yml`; firmware version in `src/main.cpp` | Relevant CI jobs; inspect packaging/firmware consumers before changing versions |

## Runtime and persistent data

- Startup: `__main__.run` creates `Runtime` and `web.create_app`; `Runtime.start` starts the TCP listener and background workers. All HTTP routes are registered at the end of `web.create_app`.
- Reports: TCP → `Session`/`Framer` → cloud exchange or one local ACK. `Runtime.observe` separately decodes and submits history/archive/MQTT work. Do not make forwarding wait for storage, decoding or MQTT.
- Configuration: save through `ConfigStore`; apply through `Runtime.apply`. Listener changes require a process restart. Use the configuration model as the source of defaults and validation, not this index.
- MQTT: Paho callbacks hand work back to asyncio. HA entity IDs derive from logger serial and field ID in `Publisher.discovery`; preserve them when extending a profile. Distinct simultaneous Hub instances need distinct MQTT client IDs.
- Docker mounts a named volume at `/data`; the CLI can choose another directory with `--data-dir`. Files include `config.json`, `admin-token.txt`, optional `admin-password.json`, custom `profiles/`, `history.sqlite3`, `mqtt-discovery.json` and `archive/` (events, frames, measurements, latest samples and observed identity).
- Runtime state and credentials are not source fixtures. Do not infer access, live addresses or deployment state from conversation history. See AGENTS for authorization and secret-handling rules.

## Sources and generated files

| Source | Consumers / required companion changes |
|---|---|
| `config.py` models | Configuration API, UI form/read/save, defaults, documentation and validation tests; preserve password redaction/blank-edit semantics |
| `builtin_profiles/sofar-hyd-g3-2115.json` | Hub decoder and ESP32 `tools/resources.py`; update sanitized expected values, field-count assertions and relevant docs when fields change |
| Profile IDs and field IDs | Profile revisions distinguish historical decoding; MQTT IDs must remain stable for unchanged sensors. Built-ins are immutable via the UI; custom imports use another profile ID |
| Firmware source + canonical profile | PlatformIO generates ignored `include/builtin_profile.h` and `.pio/`; `tools/package.py` produces committed factory/OTA binaries, `SHA256SUMS` and `manifest.json` in `dist/` |
| Firmware `dist/` | Hub package resource symlink `src/solarman_hub/firmware` and Docker COPY; do not remove binaries as temporary build output |
| English source messages | All nine catalogs in `static/locales.json`; preserve keys/placeholders and unsaved form values on language changes |
| `guides/en.md` | Eight translations in the same directory; preserve `CHAPTERS` IDs and fenced commands. Web manual and firmware page reuse these files |
| Root README / English Proxmox guide | Their translated counterparts; keep commands and links consistent. Agent/engineering docs remain English |

Ignore `.venv/`, `.pio/`, `*.egg-info/`, caches and generated headers during navigation. The firmware resource symlink points inside this repository. No sibling folder, private capture or machine-specific tool cache is required to build the project.

## Verification commands

Run from the repository root. Install the development environment as described in [DEVELOPMENT.md](DEVELOPMENT.md); do not assume one already exists.

```sh
.venv/bin/pytest -q tests/test_web.py
node --check src/solarman_hub/static/app.js
bash -n scripts/proxmox-vm.sh
```

Replace the test filename with the focused suite above. For UI changes, install Playwright Chromium and run:

```sh
HUB_TEST_BROWSER=1 .venv/bin/pytest -q tests/test_browser.py
```

For firmware changes, use the pinned PlatformIO dependencies, then package and verify the distributable artifacts:

```sh
python -m platformio run -d firmware/esp32-companion
python firmware/esp32-companion/tools/package.py
sha256sum -c firmware/esp32-companion/dist/SHA256SUMS
```

Install PlatformIO/esptool tooling separately from the Hub runtime; see firmware [README](../firmware/esp32-companion/README.md) and [CI](../.github/workflows/ci.yml). For final validation, run the relevant suites and required checks; broaden only for new failures or unresolved concerns. CI runs browser-enabled pytest plus JS syntax checks and a separate firmware build/package/flash-tool check.

`test_mqtt_integration.py` requires an isolated broker through `HUB_TEST_MQTT_PORT`. `test_esp32_hardware.py` requires explicitly authorized spare hardware and private credentials; OTA writes require `HUB_TEST_ESP_OTA=1`. Proxmox tests validate provisioning without creating a VM. Never aim synthetic reports at the real cloud or use a running production receiver as a test fixture. See [AUDIT.md](AUDIT.md) for known limits and regression rationale.

## Keep this index current

Before completing **every change**, review this file. Update affected rows in the **same change** whenever files, entry points, responsibilities, test locations, commands, generated artifacts or cross-file dependencies change. This applies to renames and removals as well as additions. If none of those change, leave the index unchanged.

For a new area, add one task row with its entry point and concrete tests. For a moved file, repair links here and in AGENTS/development documentation. Verify paths, symbols and commands against the source, not memory. Keep explanations in ARCHITECTURE, user instructions in the guides and enforceable rules in AGENTS; link rather than duplicate. Do not turn this index into a changelog, function inventory or deployment diary.
