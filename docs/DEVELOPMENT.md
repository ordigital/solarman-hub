# Development

Run the commands below from the repository root. User entry points are in [README](../README.md); deployment instructions are in the [Proxmox guide](proxmox/en.md).


The [engineering review](AUDIT.md) records resolved issues, validation and scope limits.

Start with [AGENTS.md](../AGENTS.md) and the [agent index](AGENT_INDEX.md); follow its task table to the relevant files and tests. Read [architecture](ARCHITECTURE.md) when changing behavior or module boundaries. Review and update the index as required by AGENTS before completing changes. Keep captures, credentials and installation data out of source control.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q
.venv/bin/playwright install chromium
HUB_TEST_BROWSER=1 .venv/bin/pytest -q tests/test_browser.py
```

Set `HUB_TEST_MQTT_PORT` to an isolated local broker for the optional real-broker test. Browser tests exercise all nine languages, draft preservation, login viewport height and responsive layout. TCP tests use local fake upstream servers and synthetic frames, never the real cloud.

The frontend uses local HTML/CSS/JavaScript without a runtime framework, CDN or build chain. SQLite comes from Python's standard library. English guide source is `src/solarman_hub/guides/en.md`; other languages preserve the same chapter IDs and command blocks.

Optional hardware regression tests require a spare, idle ESP32 in receiver mode, with upstream forwarding disabled and learn-first or synthetic serial configuration. Keep its private credentials file outside the repository:

```sh
HUB_TEST_ESP_CREDENTIALS=/private/device.json .venv/bin/pytest -q tests/test_esp32_hardware.py
# Explicitly authorize OTA writes to that test board:
HUB_TEST_ESP_CREDENTIALS=/private/device.json HUB_TEST_ESP_OTA=1 .venv/bin/pytest -q tests/test_esp32_hardware.py
```

The private JSON has `ip` and `admin_password` fields. Tests submit synthetic reports, change the board's clock if unset, and optionally reboot it through OTA; do not run them against a production receiver. Normal test runs skip this suite.
