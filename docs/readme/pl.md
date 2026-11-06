# Solarman Hub

![Solarman Hub](../images/solarman-hub.png)

**Solarman Hub to niezależny projekt hobbystyczny. Nie jest powiązany z SOFAR (SofarSolar).**

[English](../../README.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

Solarman Hub łączy logger Solarman V5 z chmurą producenta i jednocześnie udostępnia pomiary lokalnie. W panelu przeglądasz bieżące odczyty, wykresy i historię, zarządzasz profilami dekodowania oraz łączysz Hub z Home Assistant przez MQTT. Panel i instrukcja są dostępne w dziewięciu językach.

Dołączony profil Sofar HYD G3 / LSW3 odczytuje 48 pól pomiarowych. Inne formaty raportów wymagają zgodnego, niezależnie sprawdzonego profilu. Raporty są przekazywane dalej także wtedy, gdy nie uda się odczytać pomiarów.

## Wybierz sposób instalacji

| Środowisko | Od czego zacząć |
|---|---|
| Linux z Docker Engine i Compose v2 | Szybki start poniżej |
| Proxmox VE | [Maszyna wirtualna z Debianem 13 — krok po kroku](../proxmox/pl.md) |
| Python 3.12+ bez Dockera | [Instrukcja użytkownika](../../src/solarman_hub/guides/pl.md) |

Na Proxmoxie zacznij od maszyny wirtualnej z Debianem 13, 2 vCPU, 2 GB RAM i dyskiem 20 GB. Zarezerwuj jej adres w sieci lokalnej i włącz automatyczny start. Jeśli chcesz przechowywać dłuższą historię, zwiększ dysk maszyny wirtualnej.

**[Automatyczna instalacja VM](../proxmox/pl.md)**

Uruchom poniższą komendę jako **root w konsoli Shell węzła Proxmox**, a nie wewnątrz maszyny wirtualnej. Otworzy się instalator, który przeprowadzi Cię przez kolejne kroki. Przed zatwierdzeniem sprawdź podsumowanie.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

## Szybki start z Dockerem

Po zainstalowaniu Docker Engine i Compose v2:

```sh
git clone https://github.com/ordigital/solarman-hub.git
cd solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose exec hub solarman-hub token --data-dir /data
```

Jeśli wymaga tego Twoja instalacja, dodaj `sudo` przed poleceniami Dockera.

Otwórz `http://SERVER_IP:8080`, podając adres serwera Dockera lub maszyny wirtualnej. Zaloguj się wyświetlonym tokenem. Token nie zmienia się po restartach ani aktualizacjach, dopóki zachowujesz wolumen danych. Dodaj **numer seryjny loggera** (same cyfry), wybierz zgodny profil, zapisz i zastosuj ustawienia. W ustawieniach zdalnego serwera TCP loggera wpisz ten sam adres i port `10000`. Łączyć się mogą tylko dodane loggery. Na Proxmoxie użyj adresu maszyny wirtualnej, nie adresu panelu zarządzania Proxmoxem.

Ustawienia, tokeny i historia są przechowywane w wolumenie Dockera zamontowanym pod `/data`. Nie potrzebujesz konta Solarman, plików cookie ani hasła Wi-Fi. Do połączenia z Home Assistant użyj adresu i danych logowania brokera MQTT.

Instrukcja opisuje również zmianę portów i obsługę istniejących instalacji uruchomionych przez `docker run`.

[Zmiana serwera loggera krok po kroku](../../src/solarman_hub/guides/pl.md), również przez ukrytą stronę ustawień, jest opisana w rozdziale o spoofingu.

## Obsługa i dokumentacja

[Pełna instrukcja](../../src/solarman_hub/guides/pl.md) · [Instalacja na Proxmoxie](../proxmox/pl.md) · [Rozwój projektu](../DEVELOPMENT.md) · [Architektura](../ARCHITECTURE.md) · [Audyt i ograniczenia](../AUDIT.md)

Instrukcja jest też dostępna w panelu. Opisuje przekazywanie danych do chmury, lokalne potwierdzenia odbioru, MQTT, historię, profile i konfigurację ESP32.

**Raporty potwierdzone lokalnie podczas awarii nie są później dosyłane do historii w chmurze.** Limity zapisu mogą też powodować luki w lokalnej historii. Zatrzymanie Huba przerywa przekazywanie danych. Udostępniaj port panelu i port loggerów tylko w zaufanej sieci lokalnej lub przez VPN.

## Opcjonalny ESP32 Companion

[Kod źródłowy](../../firmware/esp32-companion) · [Oprogramowanie i sumy kontrolne](../../firmware/esp32-companion/dist)

Companion odbiera i przekazuje raporty V5, przechwytuje ruch Wi-Fi oraz eksportuje profile dekodowania. Działa na klasycznym ESP32 z 4 MB pamięci flash i ma angielski interfejs. ESP32 jest opcjonalne — Hub działa również bez niego.

W Hubie otwórz **ESP32 / Instalacja**, aby pobrać oprogramowanie i instrukcje USB/OTA. Instalacja obrazu fabrycznego może usunąć ustawienia płytki. Na Proxmoxie najpierw udostępnij USB płytki maszynie wirtualnej.

Profile utworzone z nieznanych raportów wymagają ręcznej weryfikacji. Companion sam nie ustali, jakie pomiary kryją się w nieznanym raporcie, ani nie odszyfruje ruchu Wi-Fi.

[♡ Postaw mi kawę](https://buymeacoffee.com/adamstrad)
