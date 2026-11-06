# Proxmox deployment: Debian 13 VM + Docker

**Solarman Hub is an independent hobby project. It is not affiliated with SOFAR (SofarSolar).**

[English](en.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

[README](../../README.md) · [Full user guide](../../src/solarman_hub/guides/en.md)

## Automatic VM installation

Run the following command as **root in the Proxmox node’s Shell**, not inside a VM. It opens a step-by-step installer; review its summary before confirming.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Enter an IPv4 address/mask (for example `192.168.1.50/24` or `192.168.1.50/255.255.255.0`), or leave the field empty for DHCP. Gateway and DNS questions appear only for a static address.

The wizard asks for an unused VM ID, name, disk storage, directory storage for Cloud-Init snippets, LAN bridge/VLAN, DHCP or static IPv4 (address/prefix, gateway and DNS), resources, an optional SSH public-key file and a web-panel password of at least 8 characters. Defaults are Debian 13, 2 vCPU, 2 GB RAM and a 20 GB disk. It checks the official image’s SHA-512 checksum and installs Docker and the existing Hub Compose project inside the new VM. If necessary, it adds snippet support to the chosen directory storage while preserving its other content types. Existing VMs are not modified.

Installation may take several minutes. On completion, open the displayed `http://VM_IP:8080` and enter your chosen web password. Set up the logger, decoder profile, cloud and MQTT in the panel. The script does not change your logger. For DHCP, reserve the VM address; for a static address, choose an unused address outside the DHCP pool. Console credentials and a recovery-token command are saved on the Proxmox host in `/root/solarman-hub-VMID-access.txt`, readable only by root. SSH accepts keys, not passwords. If the 15-minute wait expires, the VM stays running and guest installation retries every minute. Use `qm terminal VMID` and, inside Debian, `journalctl -u solarman-hub-install` to investigate.

Keep the Cloud-Init snippet as well as the VM backup. Its location is listed in the access file; it contains password hashes and an optional public key. It must be available on every destination node before migration or restore. The script supports Proxmox VE 8/9 on amd64, a Linux bridge and directory storage for snippets. It has automated configuration tests, but has not yet been verified by creating a VM on a real Proxmox host. You can inspect [the installer source](../../scripts/proxmox-vm.sh) before running it.

## Manual installation

This guide walks you through installing Solarman Hub in a **Debian 13 (Trixie), amd64** virtual machine on Proxmox. Create the VM in the Proxmox web interface, then run all commands below **inside Debian**.

## 1. Create the VM

1. Download the [official Debian netinst amd64 ISO](https://www.debian.org/distrib/netinst). In Proxmox, select your node → ISO-capable storage → **ISO Images → Upload**.
2. Click **Create VM**, name it `solarman-hub` and select the uploaded ISO under **OS**. Start with **2 vCPU, 2048 MB RAM and a 20 GB disk**. Choose a virtual disk on storage included in your backups. Longer history needs more disk space.
3. Under **Network**, choose **VirtIO** and your existing LAN bridge, usually `vmbr0`. Choose a bridge and VLAN that let the logger reach the VM.
4. Finish, start the VM, and open **Console**. Install Debian without a graphical desktop. Select standard system utilities; SSH server is optional. Set a root password during installation so you can use the root console below.
5. After installation, detach the ISO and boot from the virtual disk. Under VM → **Options**, enable **Start at boot** and **QEMU Guest Agent**. Shut down and start the VM after enabling the agent so its virtual channel is available; the agent package will be installed in the next step.
6. Reserve the VM's address in your router's DHCP settings. Use `hostname -I` inside Debian to find its current address. Use this address wherever the guide says `VM_IP`. It is different from the Proxmox management address and the logger’s address.

A VM keeps Docker setup and full-system backups straightforward. Running Docker in LXC requires additional configuration; see the [Proxmox container documentation](https://github.com/proxmox/pve-docs/blob/master/pct.adoc) if you choose that route.

## 2. Install Docker inside Debian

Log in as **root** in the Debian VM console. On this fresh Debian 13 installation, run:

```sh
apt update
apt install -y docker.io docker-cli docker-compose docker-buildx git ca-certificates qemu-guest-agent curl
systemctl enable --now docker
systemctl start qemu-guest-agent
docker compose version
docker buildx version
```

The last two commands should display the Compose **v2** and Buildx versions. This setup uses Debian 13’s [Docker](https://packages.debian.org/trixie/docker.io), [Compose](https://packages.debian.org/trixie/docker-compose) and [Buildx](https://packages.debian.org/trixie/docker-buildx) packages. If your VM already has Docker CE, skip these commands and use its [Debian installation instructions](https://docs.docker.com/engine/install/debian/). Do not mix the two sets of packages.

## 3. Download and start the Hub

```sh
git clone https://github.com/ordigital/solarman-hub.git /opt/solarman-hub
cd /opt/solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
docker compose exec hub solarman-hub token --data-dir /data
```

The first build downloads dependencies and can take several minutes. Wait until `hub` is running; its health status should become `healthy`. The final command prints your administrator token. Keep it private. It stays the same after restarts and updates while you keep the data volume. Later commands must use this same directory so Compose finds the same project and data volume.

## 4. First connection and networking

Open **`http://VM_IP:8080`** from a computer on your LAN and sign in with the token. Add the numeric **logger serial**, choose a compatible profile, save and apply. Then configure the logger's remote TCP destination to **`VM_IP:10000`**. Save the logger’s original server settings first. Server A/B behavior varies by firmware, and a restart may be needed after changing the destination; see the user guide if reports do not arrive.

| Connection | Destination |
|---|---|
| Logger → Hub | VM IP, TCP `10000` |
| Browser → panel | VM IP, TCP `8080` |
| Hub → cloud | Configured cloud host and port, default `access3.solarmanpv.com:10000` |
| Hub → MQTT | Your existing broker host/port; usually `1883`, or the broker's TLS port |

The VM also needs working DNS, a correct clock and Internet access for installation and cloud forwarding. MQTT requires a separate broker, such as the one already used by Home Assistant; this Compose file does not create a broker. Enable HA's MQTT integration and configure the same broker in the Hub.

If a Proxmox, guest or router firewall is enabled, allow the appropriate traffic from the logger and your management LAN. Docker-published ports can bypass guest UFW rules; apply restrictions at the Proxmox/router boundary or using Docker's documented firewall mechanism. Do not forward the Hub ports from the Internet. No port forwarding from the Proxmox host is needed with the bridged LAN arrangement above. Use the VM IP, not the container's private Docker IP.

To keep alternative published ports across updates, create `/opt/solarman-hub/.env` before starting the Hub:

```dotenv
HUB_WEB_PORT=18080
HUB_LOGGER_PORT=18899
```

Then run `docker compose up -d --wait --wait-timeout 120` again and use `http://VM_IP:18080` and logger destination `VM_IP:18899`. Keep the panel’s listener settings at their defaults: these variables change the ports exposed by Docker. Keep `.env` private.

## 5. Verify and troubleshoot

From `/opt/solarman-hub`, inside the VM:

```sh
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail 100 hub
```

Replace `8080` with the published web port if changed. A successful health check means the web server is responding. In the panel, also check the logger connection, last measurement, cloud and MQTT status. Measurements appear once a configured logger sends a compatible report. Logs and exports can contain device identifiers, so keep them private.

If `docker compose` is missing, check the OS is Debian 13 and that `docker-cli` and `docker-compose` installed successfully. If `hub` exited, inspect its logs before requesting the token. If the browser cannot connect, check the VM's current IP, bridge/VLAN, firewall and published port. Reserve the address before pointing the logger at it.

## 6. Backup, update and restore

The Compose named volume `hub-data`, mounted at `/data`, stores tokens, settings, profiles and history under Docker's data directory inside this VM. Rebuilding the container preserves it. **Never run `docker compose down -v` or remove that volume when keeping your data.** Do not put it on a temporary filesystem or exclude its virtual disk from backup.

For a simple consistent backup, use VM → **Backup → Backup now**, choose separate backup storage and **Stop** mode. This briefly stops the VM and collection; make sure it is running afterwards. Schedule regular VM backups in Proxmox and test a restore. A snapshot alone is not a backup. Backups contain credentials, so restrict access. See [Proxmox backup/restore documentation](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

Before an update, create a backup. Then, inside the VM:

```sh
cd /opt/solarman-hub
git pull --ff-only
docker compose build --pull hub
docker compose up -d --wait --wait-timeout 120
docker compose ps
```

These commands download the latest source and rebuild the Hub. Forwarding pauses briefly while the container is replaced. Keep the same project directory, Compose project name and data volume. Install Debian and Docker security updates separately through APT.

To recover, shut down the broken VM and restore the chosen full VM backup through Proxmox. Keep the original VM powered off when starting the restored copy so IP addresses, logger sessions and MQTT client IDs do not conflict. Verify its LAN address, service health and last received sample. Data after the backup point is lost; locally acknowledged outage reports are not automatically backfilled to the cloud.

## 7. Optional ESP32 USB passthrough

Normal Hub operation does not require ESP32 or USB. To use the optional flashing tool, attach the board to the Proxmox host and select VM → **Hardware → Add → USB Device**. Choose that board and pass it through; reboot the VM if required. Inside Debian, verify the actual device path:

```sh
ls -l /dev/serial/by-id/
```

Then follow **ESP32 / Flashing** in the Hub panel or the [user guide](../../src/solarman_hub/guides/en.md). USB attached only to the computer showing the panel is unavailable to the VM. The flashing command runs a separate tool container. **Factory flashing can reset board settings.**
