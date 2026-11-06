# Engineering review — 0.2.1

Review date: 2026-11-06. Scope: Python service, relay lifecycle and ACK ownership, configuration/authentication, profiles, history/archive, MQTT Discovery, browser UI, Docker/CI and ESP32 sources/artifacts. A second review by Astra challenged the transport and firmware changes. This is an engineering review and regression pass, not a formal security certification.

## Resolved findings

| Area | Failure and correction |
|---|---|
| Home Assistant Discovery | Attribute-style Jinja access selected the dictionary's `values` method instead of sensor data. Templates now use bracket access; all 48 fields render under StrictUndefined. |
| Cloud reconnect/bootstrap | Parallel forwarding could see an incompletely bootstrapped connection; late cleanup could affect a replacement. Connection setup is serialized and ACK futures/readers/cleanup belong to a specific generation. Bootstrap advances the server sequence. |
| Session lifecycle | Repeated cancellation could interrupt cleanup and leave a serial permanently marked connected. Stop is idempotent; nested cleanup always releases the serial. Independent sessions stop concurrently. |
| Sample timestamps | A future device timestamp could displace live values indefinitely, including after restart. Such samples remain diagnostic history, without replacing current/cache/MQTT state. Cached data is validated. Repeated DST hours use reception time; nonexistent local times are rejected. |
| MQTT shutdown | A publish timeout could still be followed by a clean disconnect, suppressing LWT while retained availability stayed online. Shutdown requires confirmed PUBACK; otherwise the socket is shut down before disconnect so the broker can publish LWT. |
| Archive retention/privacy | Reducing backup count left old files behind. Excess backups are removed when the setting changes; current/rotated files use mode 0600. The directory scan runs on limit changes instead of every write. |
| History charts | Slow requests could overwrite a newer chart selection; invalid ranges could cause an unhandled promise rejection. Request generations and bounded error handling preserve the latest selection and clear stale chart state. |
| ESP32 HTTP/OTA | Arduino's blocking multipart parser could stall the receiver and leave it paused after some malformed uploads. A bounded incremental parser validates authorization/routes/body limits before allocation, accepts one firmware file, applies total/idle deadlines and always performs upload cleanup. Both legal final-boundary endings are supported. Buffered reads avoid per-byte socket calls. |
| ESP32 socket state | Arduino 2.0.17's zero-length receive can interpret stale errno as a new connection failure. Accept/write use descriptor and actual I/O results; receive-side state uses buffered availability and a one-byte peek. |
| ESP32 capture | Partial allocation/task initialization could expose an apparently ready capture mode. Readiness now requires successful initialization, with explicit errors and cleanup. |
| ESP32 DNS | Synchronous hostname resolution could block the receiver far longer than its TCP deadline. A bounded single-result background worker, address cache and initial-resolution wait keep DNS outside the main loop. |

## Verification

- Full Python suite with Chromium browser checks and an isolated real MQTT broker: **49 passed**. Default runs skip opt-in hardware tests.
- Optional ESP32 bench suite: **13 passed**. Checks cover malformed/slow headers and bodies, early authentication/size/type rejection, incomplete and extra-part OTA cleanup, deliberate peer resets, V5 ACK recovery, and complete OTA with both closing-boundary variants.
- Real ESP32 OTA preserves administrator credentials, Wi-Fi configuration and a saved profile. English web UI, export paths and local/fake-upstream ACK behavior are checked separately.
- Firmware builds with the pinned PlatformIO platform; USB/OTA images, SHA256SUMS and manifest are regenerated together.
- Hub and USB flashing Docker images build; the Hub passes its healthcheck as an unprivileged user with a read-only filesystem on isolated ports.
- Python undefined-name/unused-import checks, JavaScript syntax checks and `git diff --check` pass.
- `pip-audit` found no known vulnerabilities in the 54 installed Python packages checked. This does not audit the C/C++ SDK or predict undisclosed vulnerabilities.
- Tracked release files contain none of the known Wi-Fi/admin secrets checked. Captures, credentials and deployment state remain excluded. This is a targeted secret check, not proof that all possible private metadata is absent.

Tests use synthetic reports and fake upstreams; none are sent to the real Solarman cloud. The live Hub and logger configuration are unchanged by this audit.

## Remaining scope limits

- The validated measurement map is still the single Sofar HYD G3 / LSW3 layout. Another inverter requires independently verified fields and fixtures. Draft raw-word exports are not validated sensors.
- The ESP32 tests cover one classic ESP32, 4 MB board. They do not establish compatibility with other chips or every AP/mesh combination.
- DNS failure/local fallback is tested on hardware. The local network rejected the private-address wildcard DNS test; successful hostname forwarding is not claimed from that attempted test. Numeric-address fake-upstream forwarding is tested independently.
- Cloud compatibility is based on observed V5 traffic. Local ACK does not guarantee cloud delivery, replay/backfill or lossless storage. Slow clients, finite queues, disk failures and flash wear remain operational constraints.
- Management HTTP is intended for a trusted LAN/VPN. Internet exposure requires an appropriately configured TLS/authentication boundary. No penetration-test or long-duration soak-test guarantee is made.
