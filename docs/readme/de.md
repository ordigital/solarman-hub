# Solarman Hub

![Solarman Hub](../images/solarman-hub.png)

**Solarman Hub ist ein unabhängiges Hobbyprojekt und steht in keiner Verbindung zu SOFAR (SofarSolar).**

[English](../../README.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

Solarman Hub verbindet Ihren Solarman-V5-Logger mit der Cloud des Herstellers und stellt die Messwerte gleichzeitig lokal bereit. In der Weboberfläche können Sie aktuelle Werte und Diagramme ansehen, Messdaten speichern, Decoderprofile verwalten und Home Assistant über MQTT anbinden. Oberfläche und Handbuch sind in neun Sprachen verfügbar.

Das mitgelieferte Profil für Sofar HYD G3 / LSW3 dekodiert 48 Messfelder. Andere Berichtsformate benötigen ein passendes, unabhängig geprüftes Profil. Auch wenn sich ein Bericht nicht dekodieren lässt, wird er weitergeleitet.

## Installation wählen

| Umgebung | Einstieg |
|---|---|
| Linux mit Docker Engine und Compose v2 | Schnellstart weiter unten |
| Proxmox VE | [Debian-13-VM Schritt für Schritt einrichten](../proxmox/de.md) |
| Python 3.12+ ohne Docker | [Benutzerhandbuch](../../src/solarman_hub/guides/de.md) |

Für Proxmox empfiehlt sich zum Einstieg eine Debian-13-VM mit 2 vCPU, 2 GB RAM und 20 GB Festplattenspeicher. Reservieren Sie ihre LAN-Adresse und aktivieren Sie den automatischen Start. Planen Sie mehr Speicherplatz ein, wenn Sie Messdaten länger aufbewahren möchten.

**[Automatische VM-Installation](../proxmox/de.md)**

Führen Sie den folgenden Befehl als **root in der Shell des Proxmox-Knotens** aus, nicht in einer VM. Der Assistent führt Sie Schritt für Schritt durch die Einrichtung. Prüfen Sie die Zusammenfassung vor der Bestätigung.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

## Docker-Schnellstart

Wenn Docker Engine und Compose v2 bereits installiert sind:

```sh
git clone https://github.com/ordigital/solarman-hub.git
cd solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose exec hub solarman-hub token --data-dir /data
```

Ergänzen Sie bei den Docker-Befehlen `sudo`, falls Ihre Installation dies erfordert.

Öffnen Sie `http://SERVER_IP:8080` mit der Adresse des Docker-Hosts oder der VM. Melden Sie sich mit dem angezeigten Token an. Solange das Datenvolume erhalten bleibt, ändert sich der Token auch nach Neustarts und Updates nicht. Tragen Sie die numerische **Logger-Seriennummer** ein, wählen Sie ein passendes Profil und speichern Sie die Einstellungen. Wenden Sie sie anschließend an. Stellen Sie das entfernte TCP-Ziel des Loggers auf dieselbe Adresse und Port `10000` ein. Nur eingerichtete Logger dürfen sich verbinden. Verwenden Sie unter Proxmox die Adresse der VM, nicht die Verwaltungsadresse von Proxmox.

Einstellungen, Token und Verlauf liegen im Docker-Volume unter `/data`. Sie benötigen weder ein Solarman-Konto noch Cookies oder ein WLAN-Passwort. Für Home Assistant verwenden Sie die Adresse und Zugangsdaten Ihres MQTT-Brokers.

Hinweise zu eigenen Ports und vorhandenen Installationen mit `docker run` finden Sie im Handbuch.

[Logger-Server ändern: Schritt-für-Schritt-Anleitung mit der versteckten Einstellungsseite.](../../src/solarman_hub/guides/de.md)

## Betrieb und Dokumentation

[Vollständiges Benutzerhandbuch](../../src/solarman_hub/guides/de.md) · [Proxmox-Installation](../proxmox/de.md) · [Entwicklung](../DEVELOPMENT.md) · [Architektur](../ARCHITECTURE.md) · [Prüfung und Einschränkungen](../AUDIT.md)

Das Handbuch ist auch in der Weboberfläche verfügbar. Es erklärt Cloud-Weiterleitung, lokale Empfangsbestätigungen, MQTT, Verlauf, Profile und die ESP32-Einrichtung.

**Während eines Ausfalls lokal bestätigte Berichte werden später nicht in den Cloud-Verlauf hochgeladen.** Speichergrenzen können auch im lokalen Verlauf zu Lücken führen. Wenn Sie den Hub stoppen, wird die Weiterleitung unterbrochen. Betreiben Sie Verwaltungs- und Logger-Ports nur in einem vertrauenswürdigen LAN oder VPN.

## Optionaler ESP32 Companion

[Quellcode](../../firmware/esp32-companion) · [Firmware und Prüfsummen](../../firmware/esp32-companion/dist)

Der Companion kann V5-Berichte empfangen und weiterleiten, WLAN-Verkehr mitschneiden und Decoderprofile exportieren. Er läuft auf einem klassischen ESP32 mit 4 MB Flash und hat eine englische Oberfläche. Der ESP32 ist optional; der Hub funktioniert auch ohne ihn.

Unter **ESP32 / Flashen** finden Sie Firmware-Downloads und USB-/OTA-Anleitungen. Das Flashen des Factory-Images kann die Einstellungen des Boards zurücksetzen. Reichen Sie unter Proxmox zuerst das USB-Gerät an die VM durch.

Profile aus unbekannten Berichten müssen von Hand geprüft werden. Der Companion kann aus beliebigen Bytes weder elektrische Messgrößen erkennen noch WLAN-Verkehr automatisch entschlüsseln.

[♡ Buy me a coffee](https://buymeacoffee.com/adamstrad)
