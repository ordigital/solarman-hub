# Solarman Hub: Benutzerhandbuch

**Solarman Hub ist ein unabhängiges Hobbyprojekt und steht in keiner Verbindung zu SOFAR (SofarSolar).**

Dieses Handbuch hilft Ihnen, den Hub einzurichten, Ihren Logger anzuschließen und bei Bedarf den ESP32 Companion zu nutzen. Die Sprachauswahl im Hub gilt für Oberfläche und Handbuch. Der Companion hat eine eigene englische Oberfläche.

## [hub] Den Hub verwenden

Melden Sie sich mit Ihrem Web-Passwort oder Administrator-Token an. Die Übersicht zeigt Messwerte sowie den Zustand von Logger, Cloud-Verbindung, MQTT und lokalem Speicher. Prüfen Sie sowohl die Logger-Verbindung als auch den Zeitpunkt des letzten Messwerts: Ein verbundener Logger hat möglicherweise noch keinen Bericht gesendet.

Die Sprache ändern Sie neben der Aktualisierungsanzeige. Der Browser merkt sich Ihre Auswahl.

Wählen Sie unter **Übersicht** einen Logger und dann **Neueste Messung** oder **Verlauf**. Historische Messwerte behalten ihre ursprünglichen Feldnamen, Einheiten und Profilrevisionen. Klicken Sie auf einen Messwertnamen, um das Zeitdiagramm zu öffnen. Wählen Sie einen Zeitraum und bewegen Sie den Zeiger über das Diagramm oder bedienen Sie den Datenpunkt-Schieberegler mit der Tastatur. Empfangslücken erscheinen als Unterbrechungen der Linie. Bei größeren Zeiträumen werden weniger Punkte angezeigt; die niedrigsten und höchsten Werte bleiben erhalten.

Speichern Sie Änderungen unter **Konfiguration** zuerst und wählen Sie dann **Anwenden und erneut verbinden**. Dabei werden die laufenden Logger-Sitzungen geschlossen, damit sich die Logger mit den neuen Einstellungen verbinden. Änderungen an einer Empfangsadresse oder einem Port erfordern zusätzlich einen Hub-Neustart und passende Docker-Portzuordnungen.

Unter **Geräte** werden vom Logger empfangene Angaben getrennt von Hersteller und Modell des Profils angezeigt. Noch nicht empfangene Informationen sind mit „Nicht empfangen“ gekennzeichnet.

## [install] Installation und erste Verbindung

**Automatische VM-Installation**

Führen Sie den folgenden Befehl als **root in der Shell des Proxmox-Knotens** aus, nicht in einer VM. Der Assistent führt Sie Schritt für Schritt durch die Einrichtung. Prüfen Sie die Zusammenfassung vor der Bestätigung.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Geben Sie eine IPv4-Adresse mit Maske ein (z. B. `192.168.1.50/24` oder `192.168.1.50/255.255.255.0`), oder lassen Sie das Feld für DHCP leer. Gateway und DNS werden nur bei einer statischen Adresse abgefragt.

Der Assistent fragt nach einer freien VM-ID, Name, Festplattenspeicher, Verzeichnisspeicher für Cloud-Init-Snippets, LAN-Bridge/VLAN, DHCP oder statischem IPv4 (Adresse/Präfix, Gateway und DNS), Ressourcen, optionaler SSH-Schlüsseldatei und einem Web-Passwort mit mindestens 8 Zeichen. Standard: Debian 13, 2 vCPU, 2 GB RAM und 20 GB Festplatte. Er prüft die SHA-512-Prüfsumme des offiziellen Images und installiert Docker und das bestehende Compose-Projekt in der neuen VM. Falls nötig, ergänzt er beim Verzeichnisspeicher den Inhaltstyp snippets und erhält die übrigen Typen. Bestehende VMs bleiben unverändert.

Empfohlen wird Docker Compose. Unter Proxmox betreiben Sie Docker in einer Debian-VM. Alternativ lässt sich der Hub direkt mit Python ab Version 3.12 starten.

Im Repository-Verzeichnis:

```sh
docker compose up -d --build
docker compose exec hub solarman-hub token --data-dir /data
```

Öffnen Sie `http://SERVER_IP:8080` und melden Sie sich mit dem Token an. Er liegt in `/data/admin-token.txt` und bleibt bei Neustarts und Updates gleich. Ein neuer Token wird nur erzeugt, wenn diese Datei fehlt, etwa beim Start mit einem leeren Datenvolume. Der veröffentlichte Logger-Port ist standardmäßig `10000/TCP`. Einen vorhandenen, mit `docker run` gestarteten Container verwaltet Compose nicht. Verwenden Sie dessen tatsächlichen Namen, zum Beispiel:

```sh
docker exec solarman-hub solarman-hub token --data-dir /data
```

Andere Host-Ports vermeiden Konflikte:

```sh
HUB_LOGGER_PORT=18899 HUB_WEB_PORT=18080 docker compose up -d --build
```

Tragen Sie die numerische **Logger-Seriennummer** ein, nicht die des Wechselrichters. Optional können Sie die Quell-IP einschränken und per DHCP reservieren. Wählen Sie ein passendes Decoderprofil, speichern Sie und wenden Sie die Einstellungen an. Eine frische Installation nimmt keine unbekannten Logger-Seriennummern an. Stellen Sie das entfernte TCP-Ziel des Loggers auf die Host-IP des Hubs und den veröffentlichten Logger-Port ein. Eine ausführliche Schritt-für-Schritt-Anleitung finden Sie unten unter „Den eigenen Logger an einen lokalen V5-Server anschließen“.

Ohne Docker:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/solarman-hub serve --data-dir ./data
# In a second terminal:
.venv/bin/solarman-hub token --data-dir ./data
```

Für einen dauerhaften Python-Betrieb verwenden Sie einen Prozessmanager. `solarman-hub check-config --data-dir ./data` prüft Einstellungen und Profilverweise.

## [cloud] Cloud-Weiterleitung, lokale ACKs und MQTT

Das voreingestellte Cloud-Ziel ist `access3.solarmanpv.com:10000`. Der Hub leitet V5-Berichte und Cloud-Antworten unverändert weiter. Er benötigt weder Solarman-Passwort noch Cookies oder WLAN-Passwort. Die Frames enthalten weiterhin Gerätekennungen und Protokollmetadaten und gehören damit zu den privaten Daten Ihrer Anlage.

Ein ACK bestätigt dem Logger den Empfang eines Berichts. Bei unterstützten Berichtstypen sendet der Hub entweder das Cloud-ACK oder bei einem Verbindungsfehler bzw. Zeitablauf genau ein lokales ACK. Danach schließt er die fehlgeschlagene Cloud-Sitzung und ignoriert verspätete ACKs. Unbekannte, gültige Frames können weitergeleitet werden, erhalten aber kein lokales ACK. Die Verbindung überträgt Daten in beide Richtungen, auch Befehle aus der Hersteller-Cloud.

Fällt das Internet aus, während das LAN weiter funktioniert, können lokale Messwerte und MQTT weiterhin verfügbar sein. **Während des Ausfalls lokal bestätigte Berichte werden später nicht automatisch in die Cloud hochgeladen. Im Cloud-Verlauf können Lücken entstehen.** Wird der Hub gestoppt, ist der eingerichtete Weiterleitungsweg unterbrochen. Für eine Rückkehr zur direkten Cloud-Verbindung stellen Sie die ursprünglichen Logger-Ziele wieder her.

Verbinden Sie für Home Assistant beide Anwendungen mit demselben MQTT-Broker. Tragen Sie im Hub Host, Port, gegebenenfalls Benutzername und Passwort sowie TLS-Einstellungen ein und aktivieren Sie MQTT Discovery. Richten Sie in HA die offizielle MQTT-Integration ein. Ein HA-API-Token ist nicht nötig. Der Brokertest prüft Verbindung und Anmeldung, aber keine Veröffentlichungsrechte (ACLs).

Discovery wird nach dem ersten kompatiblen Messwert verfügbar. Die stabilen Sensor-IDs setzen sich aus Logger-Seriennummer und Feld-ID zusammen. MQTT-Verfügbarkeit, Alter des letzten Logger-Messwerts und Cloud-Verbindung werden getrennt erfasst. Wählen Sie geeignete Energiezähler für das HA-Energie-Dashboard selbst aus. Nach einem Wechsel von Broker oder Themenpräfix müssen möglicherweise alte gespeicherte Discovery-Themen auf dem bisherigen Broker gelöscht werden.

## [history] Verlauf, Diagramme und Aufbewahrung

Der Messverlauf liegt in `/data/history.sqlite3`. Speicherprobleme unterbrechen die Cloud-Weiterleitung nicht. Enthält eine ältere Installation JSONL-Messarchive, importiert der Hub diese einmalig im Hintergrund und empfängt gleichzeitig weiter Berichte. Importfortschritt und Speicherfehler finden Sie unter **Konfiguration**.

Stellen Sie die **Aufbewahrungsdauer** in Tagen und die **Größenbegrenzung des Verlaufs** in MB ein. Beide Grenzen gelten gleichzeitig; die zuerst erreichte Grenze führt zum Löschen der ältesten Daten. Maßgeblich ist die Empfangszeit, damit eine falsche Wechselrichteruhr Daten nicht unbegrenzt aufbewahren lässt. Null Tage deaktiviert nur die Altersgrenze. Wenn Sie den Verlauf abschalten, werden keine neuen Messwerte gespeichert; vorhandene Daten bleiben erhalten.

Die Größenbegrenzung umfasst Datenbank und Journaldateien sowie eine Reserve für die Datenbankwartung. Bei Schreibvorgängen kann sie kurzfristig überschritten werden. Lassen Sie daher freien Speicherplatz. Für Rohframes, JSONL-Archive und Ereignisprotokolle gelten eigene Grenzen. **Eine kleinere Verlaufsgrenze löscht ältere Daten.** Sichern Sie vorher alles, was Sie behalten möchten.

Diagramme verwenden die Messzeit, sofern verfügbar, sonst die Empfangszeit. Getrennte Profilrevisionen verhindern, dass inkompatible Skalen oder Einheiten vermischt werden. Große Zeiträume liefern höchstens 1500 repräsentative Punkte. Überschreitet eine Abfrage die Suchgrenze, werden Sie aufgefordert, den Zeitraum zu verkleinern. Verspätete Messwerte können im Verlauf erscheinen, ohne den neuesten Live-Wert zu ersetzen. Doppelte Messwerte werden zusammengeführt.

## [devices] Geräteinformationen und Decoderprofile

Der Hub erfasst Logger-Seriennummer und Gegenstellen-IP aus der V5/TCP-Sitzung. Bekannte LSW3-Handshake-Formate können die Firmwareversion liefern; der unterstützte Sofar-HYD-Bericht enthält die Wechselrichter-Seriennummer. Zu jeder dekodierten Geräteangabe werden Quelle und Beobachtungszeit angezeigt. Aus einer TCP-Verbindung lässt sich keine MAC-Adresse ableiten; beliebige Textfelder werden nicht erraten.

Das integrierte Sofar-HYD-G3-Profil dekodiert 48 Felder aus einem 2115 Byte langen Bericht. Es wurde an einer HYD-15KTL-3PH-/LSW3-Anlage geprüft. Andere Hardware muss unabhängig validiert werden. Auch ein Bericht mit erwartetem Code und erwarteter Länge kann die Messwerte anders anordnen.

Profile sind deklarative JSON-Dateien mit Code, Gesamtlänge des Frames, Zeitstempelzuordnung und Feldern. Offset null bezeichnet das erste `A5`-Byte des vollständigen V5-Frames. Pro Feld werden Offset, Breite, Byte-Reihenfolge, Vorzeichen, Skalierung, Einheit und optionale HA-Klassen festgelegt. Registerverweise dienen nur als Hinweise; der Hub fragt damit keine Wechselrichterregister ab.

Klonen Sie integrierte Profile, bevor Sie sie bearbeiten. Prüfen Sie die HEX-Vorschau und vergleichen Sie mehrere Berichte mit unabhängigen Messwerten, bevor Sie eine Zuordnung verwenden. Für ein anderes V5-Layout genügt möglicherweise ein neues Profil; ein anderes Übertragungsprotokoll erfordert Codeänderungen. **Nur weiterleiten** überträgt Berichte ohne Dekodierung.

Auf der Profilseite können Sie eine einzelne Profil-JSON-Datei oder ein ESP32-Paket importieren. Prüfen Sie Zusammenfassung, Prüfstatus und Konflikte. Der Import speichert ein Profil und gegebenenfalls einen neuen Logger-Eintrag. Er wendet keine Einstellungen an und konfiguriert keinen Logger um. Rohwort-Entwürfe enthalten ungeprüfte Werte ohne zugewiesene Einheiten oder Energieklassen.

## [spoofing] Den eigenen Logger an einen lokalen V5-Server anschließen

Um Berichte lokal zu empfangen, stellen Sie den entfernten Server Ihres Loggers auf den Hub oder Companion um. „Spoofing“ bedeutet in diesem Handbuch lediglich, diesen lokalen Server anstelle des Cloud-Endpunkts zu verwenden.

Im normalen Betrieb:

```text
Logger → Hub → manufacturer cloud
             ↘ local history and MQTT
```

Für eine vorübergehende Analyse:

```text
Logger → ESP32 Companion → Hub → manufacturer cloud
```

### Den entfernten Server des Loggers ändern

Die folgenden Schritte gelten für einen LSW3-Logger mit einer versteckten Seite für die Servereinstellungen. Menünamen und Verhalten beim Neustart können je nach Firmware abweichen.

1. **Beide Adressen ermitteln.** Suchen Sie in der DHCP-Geräteliste Ihres Routers die LAN-IP des Loggers und des Hub-Servers. Beispielsweise könnte der Logger `192.168.100.205` und der Hub `192.168.100.50` verwenden. Ersetzen Sie diese Beispiele durch Ihre eigenen Adressen und reservieren Sie beide. Über die Logger-Adresse öffnen Sie dessen Einstellungen; an die Hub-Adresse werden die Berichte gesendet. Verwenden Sie unter Proxmox für den Hub die Adresse der Debian-VM.
2. **Zuerst den Hub vorbereiten.** Tragen Sie unter **Konfiguration** die numerische Logger-Seriennummer ein, wählen Sie ein passendes Profil und speichern Sie. Wählen Sie anschließend **Anwenden und erneut verbinden**. Wenn weiterhin Berichte in der Cloud ankommen sollen, aktivieren Sie die Cloud-Weiterleitung und verwenden Sie das ursprüngliche Cloud-Ziel des Loggers. Prüfen Sie den von Docker veröffentlichten Logger-Port; standardmäßig ist dies `10000/TCP`.
3. **Die Einstellungen des Loggers öffnen.** Öffnen Sie in einem Browser im selben LAN `http://LOGGER_IP/config_hide.html`. Ersetzen Sie `LOGGER_IP` durch die Logger-Adresse. Melden Sie sich mit den Administrator-Zugangsdaten des Loggers an, nicht mit Ihrem Solarman-Konto oder Hub-Token. Beim getesteten Logger lauteten die werkseitigen Zugangsdaten Benutzername `admin` und Passwort `admin`. Falls diese nicht funktionieren, prüfen Sie das Geräteetikett und die Anleitung oder verwenden Sie die vom Installateur bereitgestellten Zugangsdaten. Wurde das Passwort geändert, verwenden Sie das aktuelle Passwort. Das versteckte Einstellungsformular wird innerhalb dieser Seite geladen. Beim direkten Öffnen von `hide_set_edit.html` lassen sich die Einstellungen möglicherweise nicht laden oder speichern.
4. **Beide Serverkonfigurationen sichern.** Notieren Sie vor Änderungen alle Angaben unter **Server A Setting** und **Optional Server Setting(B)**, einschließlich IP-Adresse, Domainname, Port und Verbindungstyp. Screenshots sind dabei hilfreich. Bewahren Sie diese Angaben auf, damit Sie die direkte Cloud-Verbindung wiederherstellen können.
5. **Das Hauptziel einstellen.** Tragen Sie unter **Server A Setting** die LAN-IP des Hubs in **IP address** ein, leeren Sie **Domain name**, setzen Sie **Port** auf den veröffentlichten Logger-Port des Hubs und wählen Sie unter **Connection** die Option **TCP**. Normalerweise zeigt A damit auf den Hub. Verwenden Sie den Logger-Port, nicht den Web-Port `8080`, Port `8899` oder eine private Docker-Container-IP. Lassen Sie B zunächst unverändert, sofern Ihre Firmware nicht die unten beschriebene Ausweichkonfiguration benötigt.
6. **Jedes geänderte Formular speichern.** A und B besitzen separate **Save**-Schaltflächen. Speichern Sie A und, falls geändert, B zusätzlich separat. Öffnen Sie die Einstellungen erneut und prüfen Sie die gespeicherten Werte.
7. **Den Logger neu starten.** Verwenden Sie zuerst die Neustartfunktion des Loggers. Manche Firmware hält die alte TCP-Sitzung auch nach einer Neustartanforderung aus der Oberfläche offen. Sendet der Logger weiterhin an das alte Ziel, starten Sie ausschließlich den Logger physisch neu, und nur wenn seine Installationsanleitung dies gefahrlos erlaubt. Ändern Sie keine Betriebsparameter des Wechselrichters und trennen Sie keine Leistungskabel des Wechselrichters, um den Logger neu zu starten.
8. **Den tatsächlichen Empfang prüfen.** Kontrollieren Sie im Hub, ob sich der Logger verbindet und ob neu empfangene Messwerte aktuelle Zeitstempel haben und fortlaufend aktualisiert werden. Eine Verbindung allein genügt nicht. Bei aktivierter Cloud-Weiterleitung prüfen Sie, ob der Hub Cloud-Empfangsbestätigungen (ACKs) erhält. Prüfen Sie anschließend auch, ob neue Messwerte auf der Cloud-Seite des Herstellers erscheinen. Berücksichtigen Sie dabei das normale Sendeintervall des Loggers.

### Wenn Ihr LSW3 Server B als Ausweichziel benötigt

Bei der getesteten LSW3-Firmware wurden Berichte nicht zuverlässig gesendet, wenn nur A auf den Hub zeigte. Folgende Konfiguration funktionierte:

| Einstellung | Server A | Server B |
|---|---|---|
| IP-Adresse | LAN-IP des Hubs | LAN-IP des Hubs |
| Domainname | Leer | Leer |
| Port | `10001`, ohne laufenden Empfänger auf diesem Port | Veröffentlichter Logger-Port des Hubs, normalerweise `10000` |
| Verbindung | TCP | TCP |

A zeigt absichtlich auf einen geschlossenen lokalen Port, damit der Logger auf B ausweicht. **B ist ein Ausweichziel und erhält keine zweite, gleichzeitige Kopie jedes Berichts.** Stellen Sie sicher, dass auf dem gewählten A-Port kein Dienst lauscht. Speichern Sie beide Formulare separat, starten Sie den Logger neu und wiederholen Sie die oben beschriebenen Prüfungen von Messwerten und Cloud-Verbindung. Dieses Verhalten gilt für die getestete Firmware; verwenden Sie es, wenn die normale A-Konfiguration nicht funktioniert.

### Zur direkten Cloud-Verbindung zurückkehren

Stellen Sie die vollständigen ursprünglichen Einstellungen von A und B wieder her, einschließlich Domainnamen, Ports und Verbindungstypen. Speichern Sie jedes Formular und starten Sie nur den Logger neu. Prüfen Sie, ob neue Messwerte in der Hersteller-Cloud ankommen, bevor Sie den Hub stoppen. Während der Unterbrechung lokal bestätigte Berichte werden später nicht in den Cloud-Verlauf hochgeladen.

### Den Companion zwischen Logger und Hub einsetzen

Aktivieren Sie auf dem Companion genau ein Weiterleitungsziel: Hub oder Cloud. Versuchen Sie nicht, einen Bericht an beide zu senden. Für die Weiterleitung an den Hub müssen Sie dort zuerst die Logger-Seriennummer zulassen und den veröffentlichten TCP-Port verwenden. Der Verbindungsaufbau zum Ziel hat ein Zeitlimit von 3 Sekunden. Das ACK-Zeitlimit ist einstellbar und beträgt standardmäßig 30 Sekunden (10–120 Sekunden). Bei Weiterleitung an den Hub muss es länger sein als dessen gesamter Verbindungsaufbau einschließlich Initialisierung und ACK. Ohne Weiterleitungsziel bestätigt der Companion bekannte Frames lokal; eine Übertragung in die Cloud findet dann nicht statt.

Lokale ACKs benötigen eine korrekte Uhrzeit. Normalerweise liefert NTP diese. Hat der Companion noch keine gültige Zeit, übernimmt er beim Öffnen seiner Oberfläche auch die Browserzeit. Bis eine gültige Uhrzeit vorliegt, bestätigt er den Bericht nicht, damit der Logger ihn erneut senden kann.

## [esp32] ESP32 Companion flashen und einrichten

Die mitgelieferte Firmware ist für einen **klassischen ESP32 mit 4 MB Flash** vorgesehen und wurde mit der ESP32-D0WD-V3-Familie getestet. Sie ist nicht für ESP32-C3, S2 oder S3 geeignet. Versorgen Sie das Entwicklungsboard über USB mit Strom; die Kommunikation läuft über WLAN.

Fertige Images und Prüfsummen liegen unter `firmware/esp32-companion/dist/`:

- `factory.bin`: erste USB-Installation, einschließlich Bootloader und Partitionstabelle;
- `firmware.bin`: reines Anwendungsimage für OTA;
- `SHA256SUMS`: Prüfsummen zur Integritätsprüfung.

Verwenden Sie ein USB-Kabel mit Datenübertragung. Installieren Sie das Flash-Werkzeug in einer virtuellen Umgebung und ermitteln Sie den richtigen Port:

```sh
python3 -m venv .esp-tools
.esp-tools/bin/pip install esptool==5.6.0
.esp-tools/bin/python -m esptool --port /dev/ttyUSB0 flash-id
sha256sum -c firmware/esp32-companion/dist/SHA256SUMS
.esp-tools/bin/python -m esptool --chip esp32 --port /dev/ttyUSB0 write-flash 0x0 firmware/esp32-companion/dist/factory.bin
```

Für den seriellen Port müssen Sie eventuell der entsprechenden Benutzergruppe Ihres Betriebssystems angehören. Schließen Sie serielle Monitore vor dem Flashen. Wechselt das Board nicht automatisch in den Bootloader, halten Sie beim Start des Werkzeugs BOOT gedrückt und lassen Sie die Taste nach dem Verbindungsaufbau los. Das Factory-Image kann gespeicherte Einstellungen zurücksetzen; OTA erhält sie.

Alternativ können Sie auf einem **Linux-Host mit Docker Engine** einen einmalig gestarteten Container verwenden. Klonen oder laden Sie dieses Repository herunter und führen Sie die Befehle in dessen Hauptverzeichnis aus. Schließen Sie serielle Monitore, verbinden Sie den ESP32 mit diesem Docker-Host und ermitteln Sie sein serielles Gerät. `/dev/ttyUSB0` ist nur ein Beispiel:

```sh
ls -l /dev/serial/by-id/
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm --build esp-flash flash-id
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm esp-flash
```

Der erste Docker-Befehl baut das Werkzeug und prüft den angeschlossenen Chip, ohne ihn zu beschreiben. Der zweite prüft die Prüfsumme des mitgelieferten Images und schreibt `factory.bin` an Adresse `0x0`. Ersetzen Sie `ESP_PORT` durch den Pfad Ihres Boards unter `/dev/ttyUSB…`, `/dev/ttyACM…` oder `/dev/serial/by-id/…`. Das Werkzeug benötigt keine Python-Installation auf dem Host und läuft getrennt vom Hub. Verwenden Sie für spätere Updates OTA, um Einstellungen zu erhalten.

Das USB-Gerät muss **auf dem Rechner mit dem Docker-Daemon** verfügbar sein, nicht nur auf dem Rechner mit dem Browser. Reichen Sie es bei einer Proxmox-VM zuerst an diese VM durch. Die Befehle gelten für Linux Docker Engine. Docker Desktop unter Windows/macOS stellt serielle Geräte standardmäßig nicht auf diese Weise bereit. Verwenden Sie dort die native esptool-Anleitung oben oder richten Sie USB-Passthrough ausdrücklich ein.

Die Hub-Seite **ESP32 / Flashen** bietet nach der Anmeldung außerdem Downloads für **Firmware für die erste USB-Installation**, **Firmware für das OTA-Update** und **SHA-256-Prüfsummen**. Die Weboberfläche lädt Dateien herunter; sie flasht nicht den USB-Port des Browserrechners.

Lesen Sie die serielle USB-Ausgabe mit **115200 Baud**. Beim Start werden eine individuelle Einrichtungs-SSID samt Passwort und der Administratorname `admin` mit individuellem Passwort ausgegeben. Verbinden Sie sich mit diesem Einrichtungs-WLAN und öffnen Sie `http://192.168.4.1`. Geben Sie die Administrator-Zugangsdaten in der Browserabfrage ein. Tragen Sie SSID und Passwort Ihres Heimnetzes ein und speichern Sie. Das Board startet neu. Seine LAN-IP finden Sie in der USB-Ausgabe oder im DHCP; alternativ versuchen Sie `http://solarman-companion.local`.

Der Empfangsmodus lauscht auf `10000/TCP`. Legen Sie die erlaubte Logger-Seriennummer fest, wählen Sie bei Bedarf ein Weiterleitungsziel und stellen Sie den Logger auf die ESP32-IP ein. Der Empfänger unterstützt einen aktiven Logger, vier wartende Uploads und Frames bis 4096 Byte. Frame-Puffer, Bericht und passiver Mitschnitt liegen im RAM und gehen beim Neustart verloren.

Zum Bauen aus dem Quellcode verwenden Sie PlatformIO mit `firmware/esp32-companion/platformio.ini`.

## [export] Profile, Einstellungen und Mitschnitte exportieren

Empfangen Sie unter **Profile builder and exports** des Companions einen Bericht. Laden Sie dann die bekannte HYD-Zuordnung, einen ungeprüften Rohwort-Entwurf oder ein gespeichertes eigenes Profil. Der Entwurf zeigt bis zu 64 Rohwörter. Ermitteln Sie Bedeutung, Byte-Reihenfolge und Skalierung durch Vergleiche mehrerer Berichte mit unabhängigen Messungen. Erst nach dieser manuellen Zuordnung lassen sich Rohwerte als Messwerte verwenden.

Bearbeiten Sie das JSON und speichern Sie ein eigenes Profil auf dem Board oder laden Sie es direkt herunter. Der Profilspeicher ist auf 12 KiB und 128 Felder begrenzt. Ein Hub-Importpaket enthält zusätzlich den vorgeschlagenen Logger-Eintrag und den Prüfstatus. Die Aufnahme des Rohberichts ist optional, da er Gerätekennungen enthält. Importieren Sie die Datei im Hub, prüfen und speichern Sie sie und wenden Sie die Einstellungen anschließend ausdrücklich an.

**Download ESP32 settings (without passwords)** exportiert Netzwerknamen, Betriebsmodus sowie Mitschnitt- und Weiterleitungsparameter. WLAN- und Administratorpasswörter werden ausgelassen. Verwenden Sie die Datei als Referenz zur Einrichtung. Auf einem frisch gelöschten Board müssen Sie Geheimnisse erneut eingeben. OTA erhält die NVS-Einstellungen und das im Flash gespeicherte Profil.

Im passiven Modus tragen Sie die Logger-MAC und die BSSID des Ziel-Access-Points ein. Die feste Zuordnung zum Access Point des Loggers hilft in Mesh-Netzen: Das einzelne 2,4-GHz-Funkmodul des ESP32 zeichnet dessen Kanal auf. Der klassische ESP32 kann keinen 5-GHz-Verkehr erfassen. Wechselt der Logger den Access Point, passen Sie das Ziel an oder zeichnen Sie auf dem neuen Kanal auf.

PCAP-Downloads enthalten einen begrenzten Ausschnitt von etwa 32 KiB. Die ältesten Pakete werden überschrieben; durch volle Warteschlangen verlorene Pakete werden gezählt. Speichern Sie während einer Analyse häufig, insbesondere beim erneuten Verbinden des Loggers. Geschützte WLAN-Frames bleiben verschlüsselt. Um WPA2-Verkehr am Computer zu entschlüsseln, benötigen Sie in der Regel den WLAN-Schlüssel und einen mitgeschnittenen Handshake. WPA3-Entschlüsselung ist nicht Teil dieser Anleitung. Nutzen Sie Wireshark und halten Sie Mitschnitte vertraulich. Siehe die [Wireshark-Anleitung zur Entschlüsselung](https://wiki.wireshark.org/HowToDecrypt802.11).

## [ota] OTA-Updates und Wiederherstellung

Laden Sie die passende Companion-Datei `firmware.bin` herunter, prüfen Sie ihre Prüfsumme und öffnen Sie **Firmware update (OTA)**. Laden Sie ein einzelnes Anwendungsimage hoch und sorgen Sie für eine stabile Stromversorgung. Verwenden Sie bei OTA keine `factory.bin`. Der Updater prüft Ihre Anmeldung sowie Chip- und Produktangaben des Images. Erst nach dem vollständigen Upload aktiviert er das neue Image.

Mitschnitt und Weiterleitung pausieren beim Upload; der Logger kann sich deshalb neu verbinden. Bei einem fehlerhaften oder unterbrochenen Upload bleibt die bisherige Anwendung erhalten und der Betrieb wird fortgesetzt. Nach erfolgreichem Upload startet der ESP32 neu. Falls die neue Anwendung nicht startet, gibt es keine automatische Rückkehr zur vorherigen Firmware. Stellen Sie das Board dann mit BOOT/USB und dem Factory-Image wieder her.

OTA verwendet HTTP mit Administrator-Anmeldung. Die Images sind nicht kryptografisch signiert. Verwenden Sie vertrauenswürdige Images und aktualisieren Sie nur in einem vertrauenswürdigen LAN. Wer das Administratorpasswort kennt, kann Firmware installieren. Halten Sie Passwort und exportierte Mitschnitte vertraulich.

## [operations] Sicherung, Fehlersuche und Grenzen

Zum Festlegen oder Ändern des Web-Passworts führen Sie diese Befehle im Compose-Projektverzeichnis aus. Verwenden Sie mindestens 8 Zeichen. Der Hub speichert einen gesalzenen Hash in `/data/admin-password.json`, nicht das Passwort selbst. Der Neustart aktiviert die Änderung und beendet bestehende Web-Sitzungen. Das Administrator-Token bleibt für Wiederherstellung und API-Zugriff gültig.

```sh
docker compose exec hub solarman-hub password --data-dir /data
docker compose restart hub
```

Sichern Sie bei gestopptem Dienst das gesamte Hub-Volume `/data`, einschließlich SQLite-Datenbank, Einstellungen, Profile, Token und Archive. Behalten Sie bei Bind-Mounts UID/GID `10001` bei. Verwenden Sie nicht `docker compose down -v`, wenn Sie Daten behalten möchten. Die Konfiguration enthält das MQTT-Passwort im Klartext und ist durch Dateisystemrechte geschützt; API-Antworten blenden es aus.

Nutzen Sie Logs und Speicherzähler in der Oberfläche sowie:

```sh
docker compose logs --tail 100 hub
docker compose restart hub
```

Ein gesunder Dienstzustand bedeutet, dass der Webserver antwortet. Prüfen Sie Cloud und MQTT separat. Volle Datenträger, langsamer Speicher und volle Warteschlangen können Lücken in gespeicherten Daten verursachen, während die Weiterleitung weiterläuft. Die Speicherzähler zeigen verworfene Messwerte an.

Kommen keine Daten an, prüfen Sie Ziel-IP und Port, Docker-Portzuordnungen, DHCP, zugelassene Seriennummern und ob der Logger tatsächlich neu gestartet wurde. Ein Handshake allein ist noch kein Messbericht. Werden Felder nicht dekodiert, prüfen Sie Profilcode, Länge, Zeitstempel und HEX-Daten. Alte Messwerte gelten nicht als aktuelle Daten. Ist ein Diagramm leer, prüfen Sie Zeitraum und Profilrevision. Ist der ESP32 unerreichbar, prüfen Sie Einrichtungs-WLAN, Kanal, USB-Ausgabe und Stromversorgung.

Betreiben Sie die HTTP-Oberflächen von Hub und Companion in einem vertrauenswürdigen LAN oder VPN. Für Fernzugriff auf den Hub verwenden Sie einen HTTPS-Reverse-Proxy mit `HUB_COOKIE_SECURE=1`. Geben Sie den V5-TCP-Empfänger ohne Authentifizierung nicht im öffentlichen Internet frei. Seriennummern- und IP-Beschränkungen sind keine sichere Geräteauthentifizierung.
