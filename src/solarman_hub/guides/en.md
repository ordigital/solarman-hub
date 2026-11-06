# Solarman Hub user guide

**Solarman Hub is an independent hobby project. It is not affiliated with SOFAR (SofarSolar).**

Use this guide to set up the Hub, connect your logger and, optionally, use the ESP32 Companion. Choose a language in the Hub to change both the panel and guide. The Companion has its own English interface.

## [hub] Using the Hub

Sign in with your web password or administrator token. The dashboard shows measurements and the status of your logger, cloud connection, MQTT and local storage. Check both the logger connection and the time of the last measurement: a connected logger may not yet have sent a report.

Change the language beside the refresh indicator. The browser remembers your choice.

In **Overview**, select a logger and choose **Latest sample** or **History**. Historical samples retain their original field labels, units and profile revision. Click a measurement name to open its time chart. Choose a time range, move the pointer over the chart, or use the data-point slider with the keyboard. Gaps in reception appear as breaks in the chart. Wider time ranges show fewer points while retaining the lowest and highest readings.

In **Configuration**, save your changes first, then select **Apply and reconnect** to activate them. Applying closes current logger sessions so they can reconnect with the new settings. Changing a listening address or port also requires a Hub restart and matching Docker port mappings.

**Devices** shows information received from the logger separately from the manufacturer and model listed in its profile. Information that has not been received is marked as unobserved.

## [install] Installation and first connection

**Automatic VM installation**

Run the following command as **root in the Proxmox node’s Shell**, not inside a VM. It opens a step-by-step installer; review its summary before confirming.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Enter an IPv4 address/mask (for example `192.168.1.50/24` or `192.168.1.50/255.255.255.0`), or leave the field empty for DHCP. Gateway and DNS questions appear only for a static address.

The wizard asks for an unused VM ID, name, disk storage, directory storage for Cloud-Init snippets, LAN bridge/VLAN, DHCP or static IPv4 (address/prefix, gateway and DNS), resources, an optional SSH public-key file and a web-panel password of at least 8 characters. Defaults are Debian 13, 2 vCPU, 2 GB RAM and a 20 GB disk. It checks the official image’s SHA-512 checksum and installs Docker and the existing Hub Compose project inside the new VM. If necessary, it adds snippet support to the chosen directory storage while preserving its other content types. Existing VMs are not modified.

Docker Compose is the recommended installation method. On Proxmox, run Docker inside a Debian VM. You can also run the Hub directly with Python 3.12 or newer.

From the repository directory:

```sh
docker compose up -d --build
docker compose exec hub solarman-hub token --data-dir /data
```

Open `http://SERVER_IP:8080` and sign in with the token. The token is stored in `/data/admin-token.txt` and stays the same after restarts and updates. A new one is generated only if that file is missing, for example when starting with an empty data volume. The default published logger port is `10000/TCP`. If using an existing container launched with `docker run`, Compose does not manage it: use its actual name, for example:

```sh
docker exec solarman-hub solarman-hub token --data-dir /data
```

An alternative host-port mapping avoids conflicts:

```sh
HUB_LOGGER_PORT=18899 HUB_WEB_PORT=18080 docker compose up -d --build
```

Add the numeric **logger serial**, not the inverter serial. Optionally restrict the source IP and reserve it in DHCP. Select a compatible decoder profile, save, then apply. A fresh installation accepts no unknown logger serials. Configure the logger's remote TCP destination to the Hub host IP and published logger port. For detailed steps, see “Spoofing your own logger: a local V5 endpoint” below.

For operation without Docker:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/solarman-hub serve --data-dir ./data
# In a second terminal:
.venv/bin/solarman-hub token --data-dir ./data
```

Use a process supervisor for a permanent Python installation. `solarman-hub check-config --data-dir ./data` validates configuration and profile references.

## [cloud] Cloud forwarding, local ACKs and MQTT

The default cloud destination is `access3.solarmanpv.com:10000`. The Hub forwards V5 reports and cloud responses without changing them. It needs no Solarman account password, cookies or Wi-Fi password. Frames still contain device identifiers and protocol metadata; they are private installation data.

An ACK tells the logger that a report was received. For supported report types, the Hub sends either the cloud’s ACK or, if the cloud connection fails or times out, one local ACK. It then closes the failed cloud session and ignores late ACKs. Unknown valid frames can pass through, but receive no local ACK. Traffic travels in both directions, including commands from the manufacturer’s cloud.

With Internet unavailable but LAN intact, local readings and MQTT can continue. **Locally acknowledged outage reports are not automatically uploaded to the cloud later. Cloud history can contain gaps.** Stopping the Hub interrupts the configured forwarding path. Restore the original logger destinations when reverting to direct cloud service.

For Home Assistant, connect both applications to the same MQTT broker. In the Hub, enter broker host, port, optional username/password and TLS settings; enable MQTT Discovery. In HA, configure the official MQTT integration. No HA API token is required. The broker test checks connection and authentication, not publication ACLs.

Discovery appears after the first compatible sample. Stable sensor identities use logger serial and field ID. MQTT availability, the age of the latest logger reading and the cloud connection are tracked separately. Choose appropriate energy counters in HA's Energy dashboard yourself. Changing broker or topic prefix can require clearing stale retained Discovery topics on the old broker.

## [history] History, charts and retention

Measurement history is stored in `/data/history.sqlite3`. Storage problems do not stop cloud forwarding. If an older installation has measurement JSONL archives, the Hub imports them once in the background while continuing to receive new reports. Check import progress and storage errors in **Configuration**.

Set **History retention** in days and **History size limit** in MB. Both apply; the first reached removes the oldest data. Age is based on reception time so an incorrect inverter clock cannot retain data forever. Zero days disables only the age limit. Disabling history stops new history writes; it does not delete retained history.

The size limit includes the database and its journal files, with room reserved for database maintenance. Temporary writes may briefly exceed it, so leave free disk space. Raw frames, JSONL archives and event logs have separate limits. **Lowering the history limit deletes older history.** Back up any data you want to keep first.

Charts use sample time when available, otherwise reception time. Separate profile revisions prevent combining incompatible scales or units. Large ranges return at most 1500 representative points; queries exceeding the scan limit ask you to narrow the range. Out-of-order samples may appear in history without replacing the newest live state. Repeated samples are deduplicated.

## [devices] Device information and decoder profiles

The Hub observes logger serial and peer IP from the V5/TCP session. Verified LSW3 handshake layouts can expose firmware; the supported Sofar HYD report exposes inverter serial. Each decoded identity value shows its source and observation time. The Hub does not infer a MAC address from a TCP connection or guess arbitrary text fields.

The built-in Sofar HYD G3 profile decodes 48 fields from a 2115-byte report, validated against a HYD 15KTL-3PH/LSW3 installation. Other hardware needs independent validation. A report can have the expected code and length while using a different measurement layout.

Profiles are declarative JSON: code, full-frame length, timestamp mapping and fields. Offset zero is the first `A5` byte of the complete V5 frame. Fields specify offset, width, endian, signedness, scale, unit and optional HA classes. Register references are notes; the Hub does not use them to poll the inverter.

Clone built-in profiles to edit them. Use the HEX preview and compare several samples against independent readings before assigning a map. A different V5 layout may require only a profile; a different wire protocol requires code. **Forward only** relays without decoding.

Import a standalone profile JSON or an ESP32 bundle on the Profiles page. Review the summary, verification status and conflicts. Import saves a profile and, where appropriate, a new logger entry; it does not apply changes or reconfigure a logger. Raw-word drafts contain unverified values without assigned units or energy classes.

## [spoofing] Spoofing your own logger: a local V5 endpoint

To receive reports locally, change your logger’s remote-server settings to point to the Hub or Companion. In this guide, “spoofing” simply means using that local server in place of the cloud endpoint.

For normal use:

```text
Logger → Hub → manufacturer cloud
             ↘ local history and MQTT
```

For temporary analysis:

```text
Logger → ESP32 Companion → Hub → manufacturer cloud
```

### Change the logger’s remote server

The following steps are for an LSW3 logger with a hidden server-settings page. Menu names and restart behavior can vary with firmware.

1. **Find both addresses.** In your router’s DHCP client list, find the logger’s LAN IP and the Hub server’s LAN IP. For example, the logger could be `192.168.100.205` and the Hub `192.168.100.50`; replace these examples with your own addresses. Reserve both addresses. The logger address opens its settings; the Hub address is where reports will be sent. On Proxmox, use the Debian VM address for the Hub.
2. **Prepare the Hub first.** Add the numeric logger serial in **Configuration**, select a compatible profile, save, then select **Apply and reconnect**. Enable cloud forwarding if you want to keep cloud reporting, using the logger’s original cloud destination. Check the logger port published by Docker; the default is `10000/TCP`.
3. **Open the logger’s own settings.** In a browser on the same LAN, open `http://LOGGER_IP/config_hide.html`. Replace `LOGGER_IP` with the logger address. Sign in with the logger’s administrator credentials, not your Solarman account or Hub token. The tested logger used the factory username `admin` and password `admin`. If these do not work, check the logger label or manual, or use the credentials set by the installer. The hidden settings form is loaded inside this page; opening `hide_set_edit.html` directly may leave it unable to load or save settings.
4. **Save a copy of both server configurations.** Before editing, record every setting under **Server A Setting** and **Optional Server Setting(B)**, including IP address, domain name, port and connection type. Screenshots are useful. Keep these details so you can restore direct cloud reporting.
5. **Set the primary destination.** Under **Server A Setting**, enter the Hub’s LAN IP in **IP address**, clear **Domain name**, enter the Hub’s published logger port in **Port**, and choose **TCP** under **Connection**. Normally, this makes A the Hub destination. Use the logger port, not the web-panel port `8080`, port `8899`, or a private Docker container IP. Keep B unchanged initially unless your firmware needs the fallback arrangement below.
6. **Save each form you changed.** A and B have separate **Save** buttons. Save A, and save B separately if you edited it. Reopen the settings and check the saved values.
7. **Restart the logger.** Use the logger’s restart option first. Some firmware keeps the old TCP session even after a restart request from the panel. If it still sends to the old destination, restart only the logger physically, and only when its installation instructions say it is safe to do so. Do not change inverter operating settings or disconnect inverter power cables to restart the logger.
8. **Check actual reports.** In the Hub, confirm that the logger connects and that newly received measurements have current timestamps and continue to update. A connection alone is not enough. If cloud forwarding is enabled, check that the Hub receives cloud acknowledgements (ACKs), then check that new readings also appear on the manufacturer’s cloud page. Allow for the logger’s normal reporting interval.

### If your LSW3 needs server B as fallback

On the tested LSW3 firmware, setting only A to the Hub did not reliably send reports. This arrangement worked:

| Setting | Server A | Server B |
|---|---|---|
| IP address | Hub LAN IP | Hub LAN IP |
| Domain name | Empty | Empty |
| Port | `10001`, with no listener on that port | Hub’s published logger port, normally `10000` |
| Connection | TCP | TCP |

A deliberately points to a closed local port so the logger falls back to B. **B is a fallback destination, not a second simultaneous copy of every report.** Ensure nothing listens on the chosen A port. Save both forms separately, restart the logger and repeat the measurement and cloud checks above. This behavior is specific to the tested firmware; use it if the normal A configuration does not work.

### Return to direct cloud reporting

Restore the complete original A and B settings, including their domain names, ports and connection types. Save each form and restart only the logger. Check for new measurements in the manufacturer’s cloud before stopping the Hub. Reports acknowledged locally during the interruption will not be uploaded to cloud history later.

### Use the Companion between the logger and Hub

Enable exactly one upstream on the Companion. Choose the Hub or the cloud; do not try to duplicate a report to both. If using the Hub upstream, first allow that logger serial in the Hub and use the Hub's published TCP port. The Companion's upstream connection timeout is 3 seconds. Its configurable ACK timeout defaults to 30 seconds (10–120 seconds); keep it longer than the Hub's complete connection/bootstrap/ACK transaction when using the Hub upstream. Without upstream, it acknowledges known frames locally; no cloud delivery occurs.

A correct clock is required for local ACKs. NTP normally supplies it; opening the Companion interface also supplies browser time if no valid clock exists. Until the clock is set, the Companion leaves the report unacknowledged so the logger can retry.

## [esp32] Flashing and configuring ESP32 Companion

The supplied build targets a **classic ESP32 with 4 MB flash**, tested against the ESP32-D0WD-V3 family. It is not an ESP32-C3, S2 or S3 image. Power the development board through USB; it communicates over Wi-Fi.

Prebuilt images and checksums are in `firmware/esp32-companion/dist/`:

- `factory.bin`: first USB installation, including bootloader and partition table;
- `firmware.bin`: application-only image for OTA;
- `SHA256SUMS`: integrity hashes.

Use a data-capable USB cable. Install the flash tool in a virtual environment and identify the correct port:

```sh
python3 -m venv .esp-tools
.esp-tools/bin/pip install esptool==5.6.0
.esp-tools/bin/python -m esptool --port /dev/ttyUSB0 flash-id
sha256sum -c firmware/esp32-companion/dist/SHA256SUMS
.esp-tools/bin/python -m esptool --chip esp32 --port /dev/ttyUSB0 write-flash 0x0 firmware/esp32-companion/dist/factory.bin
```

The serial port may require membership in the operating system's serial-access group. Close serial monitors before flashing. If automatic bootloader entry fails, hold BOOT while starting the tool and release it once connected. A factory flash may reset stored settings; OTA preserves them.

Alternatively, on a **Linux Docker Engine host**, flash directly from a one-shot container. Clone/download this repository and run these commands from its root. Close serial monitors, connect the ESP32 to that Docker host, and identify its serial device; `/dev/ttyUSB0` is an example:

```sh
ls -l /dev/serial/by-id/
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm --build esp-flash flash-id
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm esp-flash
```

The first command builds the tool and checks the connected chip without writing to it. The second verifies the bundled image’s checksum and flashes `factory.bin` at `0x0`. Replace `ESP_PORT` with your board’s `/dev/ttyUSB…`, `/dev/ttyACM…` or `/dev/serial/by-id/…` path. This tool needs no host Python installation and runs separately from the Hub. Use OTA for later updates to preserve settings.

USB must be available **on the machine running the Docker daemon**, not merely on the computer displaying the web panel. In a Proxmox VM, pass the USB device through to that VM first. This command is for Linux Docker Engine; Docker Desktop on Windows/macOS does not expose serial devices this way by default. On those systems use the native esptool instructions above or explicitly configure USB passthrough.

The Hub's **ESP32 / Flashing** page also offers **Firmware for first USB installation**, **Firmware for OTA update** and **SHA-256 checksums** downloads after login. The web panel downloads files; it does not flash the browser computer's USB port.

Read USB serial at **115200 baud**. Boot output includes a unique setup SSID/password and the administrator username `admin` with its unique password. Connect to the setup AP and open `http://192.168.4.1`. Enter the administrator credentials in the browser prompt. Configure your home SSID/password and save. The board restarts; find its LAN IP in USB output or DHCP, or try `http://solarman-companion.local`.

Receiver mode listens on `10000/TCP`. Set the allowed logger serial, optionally choose an upstream, and direct your logger to the ESP32 IP. The receiver supports one active logger, four queued uploads and frames up to 4096 bytes. Its frame buffer, report and passive capture are RAM data, lost on restart.

To build from source, use PlatformIO with `firmware/esp32-companion/platformio.ini`.

## [export] Exporting profiles, settings and captures

In the Companion's **Profile builder and exports**, receive a report, then load either the known HYD map, an unverified raw-word draft, or a saved custom profile. The draft exposes up to 64 raw words; determine meanings, endian and scale by comparing multiple samples and independent measurements. Raw values need manual interpretation before they can be used as measurements.

Edit JSON and save a custom profile on the board, or download the profile directly. Custom storage is limited to 12 KiB and 128 fields. Download a Hub import bundle to include its proposed logger entry and verification status. Raw sample inclusion is optional because it reveals device identifiers. Import the file in the Hub; review, save, then explicitly apply settings when ready.

**Download ESP32 settings (without passwords)** exports network names, mode and capture/upstream parameters. It excludes Wi-Fi and administrator passwords. Keep it as a configuration reference; re-enter secrets when restoring onto a freshly erased board. OTA preserves NVS settings and the saved profile in flash.

In passive mode, configure the logger MAC and target AP BSSID. Pinning the ESP32 to the logger's AP helps with mesh networks: its single 2.4 GHz radio captures the station/AP channel. The classic ESP32 cannot capture a 5 GHz radio. If the logger roams, update the target AP or capture the new channel.

PCAP downloads contain a bounded snapshot of approximately 32 KiB; oldest packets are overwritten and queue drops are counted. Save frequently during analysis, especially across a logger reconnect. Protected Wi-Fi frames remain encrypted. To decrypt WPA2 traffic on a computer, you generally need the Wi-Fi key and a captured handshake. These instructions do not cover WPA3 decryption. Use Wireshark and retain the capture privately. See the [Wireshark decryption guide](https://wiki.wireshark.org/HowToDecrypt802.11).

## [ota] OTA updates and recovery

Download the matching Companion `firmware.bin`, verify its hash and open **Firmware update (OTA)**. Upload one application image while keeping power stable. Do not upload `factory.bin` through OTA. The updater checks your login and the image’s chip and product information, then activates the new image only after the upload completes.

Capture and relay pause during upload, so the logger may reconnect. A failed or interrupted upload keeps the current application and resumes operation. A successful upload restarts the ESP32. The firmware does not automatically roll back if the new application fails to boot. Recover a non-booting board with BOOT/USB and the factory image.

OTA uses HTTP with an administrator login. Firmware images are not cryptographically signed, so use trusted images and update only on a trusted LAN. Anyone with the administrator password can install firmware. Keep the password and exported captures private.

## [operations] Backup, troubleshooting and limits

To set or change the web-panel password, run the following commands from the Compose project directory. Use at least 8 characters. The Hub stores a salted password hash in `/data/admin-password.json`, not the password itself. Restarting activates the change and closes existing web sessions. The administrator token remains valid for recovery and API access.

```sh
docker compose exec hub solarman-hub password --data-dir /data
docker compose restart hub
```

Back up the entire Hub `/data` volume with the service stopped, including SQLite, configuration, profiles, token and archives. Preserve UID/GID `10001` for bind mounts. Do not use `docker compose down -v` when retaining data. Configuration contains the MQTT password in plaintext with restricted filesystem permissions; API responses redact it.

Use the panel's logs and storage counters, plus:

```sh
docker compose logs --tail 100 hub
docker compose restart hub
```

A healthy service status means the web server is responding; check cloud and MQTT status separately. Full disks, slow storage or full queues can cause gaps in recorded data while forwarding continues. Check the storage counters for dropped samples.

If no data arrives, check destination IP/port, Docker mappings, DHCP, serial allowlist and actual logger restart. A handshake alone is not a measurement report. If fields fail to decode, check profile code, length, timestamps and HEX. Old samples do not make a logger fresh. If a chart is empty, check range and profile revision. If the ESP32 is unreachable, check its setup AP, channel, USB output and power.

Keep Hub and Companion HTTP interfaces on a trusted LAN or VPN. For remote Hub access, use HTTPS reverse proxy with `HUB_COOKIE_SECURE=1`. Do not expose the unauthenticated V5 TCP receiver to the public Internet. Logger serial and IP restrictions do not securely authenticate a device.
