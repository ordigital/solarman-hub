# Solarman Hub

![Solarman Hub](docs/images/solarman-hub.png)

**Solarman Hub is an independent hobby project. It is not affiliated with SOFAR (SofarSolar).**

[English](README.md) · [Polski](docs/readme/pl.md) · [Deutsch](docs/readme/de.md) · [Français](docs/readme/fr.md) · [Čeština](docs/readme/cs.md) · [Slovenčina](docs/readme/sk.md) · [Lietuvių](docs/readme/lt.md) · [Українська](docs/readme/uk.md) · [Русский](docs/readme/ru.md)

Solarman Hub connects your Solarman V5 logger to the manufacturer’s cloud while making measurements available locally. Use the web panel to view live readings and charts, keep measurement history, manage decoder profiles and connect to Home Assistant through MQTT. The panel and guide are available in nine languages.

The included Sofar HYD G3 / LSW3 profile decodes 48 measurement fields. Other report formats need a compatible, independently checked profile. Forwarding continues even if a report cannot be decoded.

## Choose your installation

| Environment | Start here |
|---|---|
| Linux with Docker Engine and Compose v2 | Quick start below |
| Proxmox VE | [Debian 13 VM setup, step by step](docs/proxmox/en.md) |
| Python 3.12+ without Docker | [User guide](src/solarman_hub/guides/en.md) |

For Proxmox, start with a Debian 13 VM, 2 vCPU, 2 GB RAM and a 20 GB disk. Reserve its LAN address and enable automatic startup. Allow more disk space if you want to keep a longer history.

**[Automatic VM installation](docs/proxmox/en.md)**

Run the following command as **root in the Proxmox node’s Shell**, not inside a VM. It opens a step-by-step installer; review its summary before confirming.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

## Docker quick start

With Docker Engine and Compose v2 already installed:

```sh
git clone https://github.com/ordigital/solarman-hub.git
cd solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose exec hub solarman-hub token --data-dir /data
```

Add `sudo` to Docker commands if your installation requires it.

Open `http://SERVER_IP:8080`, using the Docker host or VM address. Sign in with the displayed token. It stays the same after restarts and updates while you keep the data volume. Add the numeric **logger serial**, choose a compatible profile, then save and apply. Set the logger’s remote TCP destination to the same address, port `10000`. Only configured loggers can connect. On Proxmox, use the VM address, not the Proxmox management address.

Settings, tokens and history are stored in the Docker volume mounted at `/data`. You do not need a Solarman account, cookies or a Wi-Fi password. For Home Assistant, use your MQTT broker’s address and credentials.

See the guide for custom ports and existing installations created with `docker run`.

[Changing the logger server, step by step](src/solarman_hub/guides/en.md), including the hidden settings page, is described in the guide’s spoofing chapter.

## Operation and documentation

[Full user guide](src/solarman_hub/guides/en.md) · [Proxmox deployment](docs/proxmox/en.md) · [Development](docs/DEVELOPMENT.md) · [Architecture](docs/ARCHITECTURE.md) · [Agent project index](docs/AGENT_INDEX.md) · [Audit and limitations](docs/AUDIT.md)

The guide is also available inside the panel. It covers cloud forwarding, local acknowledgements, MQTT, history, profiles and ESP32 setup.

**Reports acknowledged locally during an outage are not uploaded to cloud history later.** Storage limits can also cause gaps in local history. Stopping the Hub interrupts forwarding. Keep its management and logger ports on a trusted LAN or VPN.

## Optional ESP32 Companion

[Sources](firmware/esp32-companion) · [Firmware and checksums](firmware/esp32-companion/dist)

The Companion can receive and forward V5 reports, capture Wi-Fi traffic and export decoder profiles. It runs on a classic ESP32 with 4 MB flash and has an English interface. ESP32 is optional; the Hub works without it.

Open **ESP32 / Flashing** in the Hub for firmware downloads and USB/OTA instructions. Factory flashing can reset board settings. On Proxmox, pass the board’s USB device through to the VM first.

Profiles created from unknown reports need manual verification. The Companion cannot identify electrical measurements from arbitrary bytes or automatically decrypt Wi-Fi traffic.

[♡ Buy me a coffee](https://buymeacoffee.com/adamstrad)
