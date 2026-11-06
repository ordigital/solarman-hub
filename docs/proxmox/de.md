# Installation auf Proxmox: Debian-13-VM mit Docker

**Solarman Hub ist ein unabhängiges Hobbyprojekt und steht in keiner Verbindung zu SOFAR (SofarSolar).**

[English](en.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

[README](../readme/de.md) · [Vollständiges Benutzerhandbuch](../../src/solarman_hub/guides/de.md)

## Automatische VM-Installation

Führen Sie den folgenden Befehl als **root in der Shell des Proxmox-Knotens** aus, nicht in einer VM. Der Assistent führt Sie Schritt für Schritt durch die Einrichtung. Prüfen Sie die Zusammenfassung vor der Bestätigung.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Geben Sie eine IPv4-Adresse mit Maske ein (z. B. `192.168.1.50/24` oder `192.168.1.50/255.255.255.0`), oder lassen Sie das Feld für DHCP leer. Gateway und DNS werden nur bei einer statischen Adresse abgefragt.

Der Assistent fragt nach einer freien VM-ID, Name, Festplattenspeicher, Verzeichnisspeicher für Cloud-Init-Snippets, LAN-Bridge/VLAN, DHCP oder statischem IPv4 (Adresse/Präfix, Gateway und DNS), Ressourcen, optionaler SSH-Schlüsseldatei und einem Web-Passwort mit mindestens 8 Zeichen. Standard: Debian 13, 2 vCPU, 2 GB RAM und 20 GB Festplatte. Er prüft die SHA-512-Prüfsumme des offiziellen Images und installiert Docker und das bestehende Compose-Projekt in der neuen VM. Falls nötig, ergänzt er beim Verzeichnisspeicher den Inhaltstyp snippets und erhält die übrigen Typen. Bestehende VMs bleiben unverändert.

Die Installation dauert einige Minuten. Öffnen Sie anschließend die angezeigte Adresse `http://VM_IP:8080` und melden Sie sich mit Ihrem Passwort an. Logger, Profil, Cloud und MQTT richten Sie im Panel ein; der Logger wird vom Skript nicht geändert. Reservieren Sie bei DHCP die VM-Adresse; wählen Sie für eine statische Adresse eine freie IP außerhalb des DHCP-Pools. Konsolenzugang und Befehl für das Wiederherstellungs-Token stehen auf dem Proxmox-Host in `/root/solarman-hub-VMID-access.txt`, nur für root lesbar. SSH erlaubt nur Schlüssel. Nach 15 Minuten endet das Warten; die VM läuft weiter und die Installation versucht es jede Minute erneut. Diagnose: `qm terminal VMID`, dann in Debian `journalctl -u solarman-hub-install`.

Bewahren Sie neben dem VM-Backup auch das Cloud-Init-Snippet auf. Sein Pfad steht in der Zugangsdatei; es enthält Passwort-Hashes und gegebenenfalls den öffentlichen Schlüssel. Vor Migration oder Wiederherstellung muss es auf dem Zielknoten verfügbar sein. Unterstützt werden Proxmox VE 8/9 auf amd64, Linux-Bridges und Verzeichnisspeicher für Snippets. Die Konfiguration wird automatisch getestet; eine VM-Erstellung auf einem echten Proxmox-Host wurde noch nicht geprüft. Sie können den [Quellcode des Installers](../../scripts/proxmox-vm.sh) vorab lesen.

## Manuelle Installation

Diese Anleitung führt Sie durch die Installation von Solarman Hub in einer virtuellen Maschine mit **Debian 13 (Trixie), amd64** unter Proxmox. Erstellen Sie die VM in der Proxmox-Weboberfläche. Alle folgenden Befehle führen Sie **innerhalb von Debian** aus.

## 1. VM erstellen

1. Laden Sie das [offizielle Debian-netinst-ISO für amd64](https://www.debian.org/distrib/netinst) herunter. Wählen Sie in Proxmox Ihren Knoten → einen Speicher für ISO-Dateien → **ISO Images → Upload**.
2. Klicken Sie auf **Create VM**, nennen Sie die VM `solarman-hub` und wählen Sie unter **OS** das hochgeladene ISO. Beginnen Sie mit **2 vCPU, 2048 MB RAM und 20 GB Festplattenspeicher**. Legen Sie die virtuelle Festplatte auf einem Speicher ab, der in Ihren Sicherungen enthalten ist. Ein längerer Messverlauf braucht mehr Platz.
3. Wählen Sie unter **Network** das Modell **VirtIO** und Ihre vorhandene LAN-Bridge, meist `vmbr0`. Über die gewählte Bridge und das VLAN muss der Logger die VM erreichen können.
4. Schließen Sie den Assistenten ab, starten Sie die VM und öffnen Sie **Console**. Installieren Sie Debian ohne grafische Desktopumgebung. Wählen Sie die Standard-Systemwerkzeuge; der SSH-Server ist optional. Vergeben Sie bei der Installation ein Root-Passwort für die nachfolgend verwendete Root-Konsole.
5. Entfernen Sie nach der Installation das ISO aus dem virtuellen Laufwerk und starten Sie von der Festplatte. Aktivieren Sie unter VM → **Options** die Optionen **Start at boot** und **QEMU Guest Agent**. Fahren Sie die VM nach dem Aktivieren des Agents herunter und starten Sie sie erneut, damit sein virtueller Kanal verfügbar ist. Das Agent-Paket installieren Sie im nächsten Schritt.
6. Reservieren Sie die VM-Adresse in den DHCP-Einstellungen Ihres Routers. Mit `hostname -I` sehen Sie in Debian die aktuelle Adresse. Diese setzen Sie überall dort ein, wo die Anleitung `VM_IP` verwendet. Sie ist weder die Proxmox-Verwaltungsadresse noch die Adresse des Loggers.

Eine VM vereinfacht die Docker-Einrichtung und Sicherungen des gesamten Systems. Docker in LXC benötigt zusätzliche Einstellungen. Falls Sie diesen Weg wählen, lesen Sie die [Proxmox-Dokumentation zu Containern](https://github.com/proxmox/pve-docs/blob/master/pct.adoc).

## 2. Docker in Debian installieren

Melden Sie sich in der Konsole der Debian-VM als **root** an. Führen Sie auf der frisch installierten Debian-13-VM folgende Befehle aus:

```sh
apt update
apt install -y docker.io docker-cli docker-compose docker-buildx git ca-certificates qemu-guest-agent curl
systemctl enable --now docker
systemctl start qemu-guest-agent
docker compose version
docker buildx version
```

Die letzten beiden Befehle sollten die Versionen von Compose **v2** und Buildx anzeigen. Diese Installation verwendet die Debian-13-Pakete für [Docker](https://packages.debian.org/trixie/docker.io), [Compose](https://packages.debian.org/trixie/docker-compose) und [Buildx](https://packages.debian.org/trixie/docker-buildx). Ist Docker CE bereits installiert, überspringen Sie diese Befehle und folgen Sie dessen [Debian-Installationsanleitung](https://docs.docker.com/engine/install/debian/). Mischen Sie die beiden Paketquellen nicht.

## 3. Hub herunterladen und starten

```sh
git clone https://github.com/ordigital/solarman-hub.git /opt/solarman-hub
cd /opt/solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
docker compose exec hub solarman-hub token --data-dir /data
```

Beim ersten Build werden Abhängigkeiten heruntergeladen; das kann einige Minuten dauern. Warten Sie, bis `hub` läuft und der Zustand `healthy` angezeigt wird. Der letzte Befehl gibt Ihren Administrator-Token aus. Bewahren Sie ihn vertraulich auf. Er bleibt bei Neustarts und Updates gleich, solange das Datenvolume erhalten bleibt. Führen Sie spätere Befehle im selben Verzeichnis aus, damit Compose dasselbe Projekt und Datenvolume verwendet.

## 4. Erste Verbindung und Netzwerk

Öffnen Sie von einem Rechner im LAN **`http://VM_IP:8080`** und melden Sie sich mit dem Token an. Tragen Sie die numerische **Logger-Seriennummer** ein, wählen Sie ein passendes Profil, speichern Sie und wenden Sie die Einstellungen an. Stellen Sie dann das entfernte TCP-Ziel des Loggers auf **`VM_IP:10000`**. Notieren Sie vorher seine ursprünglichen Servereinstellungen. Das Verhalten von Server A/B hängt von der Firmware ab; nach einer Änderung kann ein Neustart nötig sein. Falls keine Berichte eintreffen, hilft das Benutzerhandbuch weiter.

| Verbindung | Ziel |
|---|---|
| Logger → Hub | VM-IP, TCP `10000` |
| Browser → Weboberfläche | VM-IP, TCP `8080` |
| Hub → Cloud | Eingestellter Cloud-Host und Port, standardmäßig `access3.solarmanpv.com:10000` |
| Hub → MQTT | Host und Port Ihres vorhandenen Brokers, meist `1883` oder dessen TLS-Port |

Die VM benötigt außerdem funktionierendes DNS, eine korrekte Uhrzeit und Internetzugang für Installation und Cloud-Weiterleitung. Für MQTT ist ein separater Broker erforderlich, etwa der bereits von Home Assistant verwendete. Diese Compose-Datei richtet keinen Broker ein. Aktivieren Sie in HA die MQTT-Integration und tragen Sie im Hub denselben Broker ein.

Falls eine Firewall in Proxmox, Debian oder dem Router aktiv ist, erlauben Sie die benötigten Verbindungen vom Logger und aus Ihrem Verwaltungs-LAN. Von Docker veröffentlichte Ports können UFW-Regeln im Gastsystem umgehen. Beschränken Sie den Zugriff daher an Proxmox bzw. dem Router oder mit dem dokumentierten Firewall-Verfahren von Docker. Geben Sie die Hub-Ports nicht zum Internet frei. Bei der oben beschriebenen LAN-Bridge ist keine Portweiterleitung am Proxmox-Host nötig. Verwenden Sie die VM-IP, nicht die private Docker-IP des Containers.

Um andere veröffentlichte Ports auch nach Updates beizubehalten, erstellen Sie vor dem Start `/opt/solarman-hub/.env`:

```dotenv
HUB_WEB_PORT=18080
HUB_LOGGER_PORT=18899
```

Führen Sie danach erneut `docker compose up -d --wait --wait-timeout 120` aus. Verwenden Sie nun `http://VM_IP:18080` und für den Logger `VM_IP:18899`. Lassen Sie die Listener-Einstellungen in der Weboberfläche auf ihren Standardwerten: Die Variablen ändern nur die von Docker veröffentlichten Ports. Halten Sie `.env` vertraulich.

## 5. Funktion prüfen und Fehler beheben

Führen Sie in der VM aus dem Verzeichnis `/opt/solarman-hub` Folgendes aus:

```sh
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail 100 hub
```

Wenn Sie den Web-Port geändert haben, ersetzen Sie `8080` durch diesen Port. Ein erfolgreicher Healthcheck bedeutet, dass der Webserver antwortet. Prüfen Sie in der Oberfläche zusätzlich die Logger-Verbindung, den letzten Messwert sowie Cloud- und MQTT-Status. Messwerte erscheinen, sobald ein eingerichteter Logger einen kompatiblen Bericht sendet. Protokolle und Exporte können Gerätekennungen enthalten; behandeln Sie sie vertraulich.

Fehlt `docker compose`, prüfen Sie, ob Debian 13 läuft und `docker-cli` sowie `docker-compose` erfolgreich installiert wurden. Falls `hub` beendet wurde, lesen Sie zuerst die Logs, bevor Sie den Token abrufen. Wenn der Browser keine Verbindung bekommt, prüfen Sie die aktuelle VM-IP, Bridge/VLAN, Firewall und den veröffentlichten Port. Reservieren Sie die Adresse, bevor Sie den Logger darauf einstellen.

## 6. Sichern, aktualisieren und wiederherstellen

Das benannte Compose-Volume `hub-data` ist unter `/data` eingebunden. Es speichert Token, Einstellungen, Profile und Verlauf im Docker-Datenverzeichnis dieser VM. Ein Neubau des Containers erhält diese Daten. **Führen Sie niemals `docker compose down -v` aus und löschen Sie das Volume nicht, wenn Sie Ihre Daten behalten möchten.** Verwenden Sie kein temporäres Dateisystem und nehmen Sie die virtuelle Festplatte in die Sicherung auf.

Für eine einfache, konsistente Sicherung wählen Sie VM → **Backup → Backup now**, einen separaten Sicherungsspeicher und den Modus **Stop**. Dadurch werden VM und Datenerfassung kurz angehalten. Prüfen Sie danach, ob die VM wieder läuft. Planen Sie regelmäßige VM-Sicherungen in Proxmox und testen Sie eine Wiederherstellung. Ein Snapshot allein ist keine Sicherung. Da Sicherungen Zugangsdaten enthalten, muss ihr Zugriff eingeschränkt sein. Weitere Informationen bietet die [Proxmox-Dokumentation zu Sicherung und Wiederherstellung](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

Erstellen Sie vor jedem Update eine Sicherung. Führen Sie dann in der VM aus:

```sh
cd /opt/solarman-hub
git pull --ff-only
docker compose build --pull hub
docker compose up -d --wait --wait-timeout 120
docker compose ps
```

Diese Befehle laden den aktuellen Quellcode und bauen den Hub neu. Während der Container ersetzt wird, pausiert die Weiterleitung kurz. Behalten Sie Projektverzeichnis, Compose-Projektnamen und Datenvolume bei. Sicherheitsupdates für Debian und Docker installieren Sie separat über APT.

Zur Wiederherstellung fahren Sie die defekte VM herunter und spielen über Proxmox die gewünschte vollständige VM-Sicherung ein. Lassen Sie die ursprüngliche VM beim Start der wiederhergestellten Kopie ausgeschaltet, damit IP-Adressen, Logger-Sitzungen und MQTT-Client-IDs nicht kollidieren. Prüfen Sie LAN-Adresse, Dienstzustand und zuletzt empfangenen Messwert. Daten seit der Sicherung gehen verloren. Während eines Ausfalls lokal bestätigte Berichte werden nicht automatisch in die Cloud nachgeladen.

## 7. Optional: ESP32 per USB durchreichen

Der normale Hub-Betrieb benötigt weder ESP32 noch USB. Für das optionale Flash-Werkzeug schließen Sie das Board an den Proxmox-Host an und wählen VM → **Hardware → Add → USB Device**. Wählen Sie das Board und reichen Sie es durch. Starten Sie die VM bei Bedarf neu. Ermitteln Sie in Debian den tatsächlichen Gerätepfad:

```sh
ls -l /dev/serial/by-id/
```

Folgen Sie anschließend **ESP32 / Flashen** in der Hub-Oberfläche oder dem [Benutzerhandbuch](../../src/solarman_hub/guides/de.md). Ein USB-Gerät, das nur am Rechner mit dem Browser angeschlossen ist, steht der VM nicht zur Verfügung. Der Flash-Befehl startet einen separaten Werkzeug-Container. **Das Flashen des Factory-Images kann die Board-Einstellungen zurücksetzen.**
