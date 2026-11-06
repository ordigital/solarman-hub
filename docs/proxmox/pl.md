# Solarman Hub na Proxmoxie: Debian 13 i Docker

**Solarman Hub to niezależny projekt hobbystyczny. Nie jest powiązany z SOFAR (SofarSolar).**

[English](en.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

[README](../readme/pl.md) · [Pełna instrukcja](../../src/solarman_hub/guides/pl.md)

## Automatyczna instalacja VM

Uruchom poniższą komendę jako **root w konsoli Shell węzła Proxmox**, a nie wewnątrz maszyny wirtualnej. Otworzy się instalator, który przeprowadzi Cię przez kolejne kroki. Przed zatwierdzeniem sprawdź podsumowanie.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Wpisz adres IPv4 z maską (np. `192.168.1.50/24` lub `192.168.1.50/255.255.255.0`) albo pozostaw pole puste, aby użyć DHCP. Pytania o bramę i DNS pojawią się tylko przy stałym adresie.

Kreator zapyta o wolny numer VM, nazwę, storage dysku, storage katalogowy na pliki Cloud-Init, most sieciowy i VLAN, DHCP lub stałe IPv4 (adres z prefiksem, bramę i DNS), zasoby, opcjonalny plik publicznego klucza SSH oraz hasło do panelu WWW — co najmniej 8 znaków. Domyślnie utworzy Debiana 13 z 2 vCPU, 2 GB RAM i dyskiem 20 GB. Sprawdzi sumę SHA-512 oficjalnego obrazu i zainstaluje Dockera oraz istniejący projekt Compose Huba wewnątrz nowej VM. Jeśli trzeba, włączy obsługę plików snippets w wybranym storage katalogowym, zachowując pozostałe typy zawartości. Nie zmienia istniejących maszyn.

Instalacja może potrwać kilka minut. Po zakończeniu otwórz wyświetlony adres `http://VM_IP:8080` i wpisz wybrane hasło. Logger, profil dekodowania, chmurę i MQTT skonfigurujesz już w panelu. Skrypt nie zmienia ustawień loggera. Przy DHCP zarezerwuj adres VM; przy stałym IP wybierz wolny adres spoza puli DHCP. Dane konsoli i komenda odczytu tokena odzyskiwania dostępu są zapisane na hoście Proxmox w `/root/solarman-hub-VMID-access.txt`, dostępnym tylko dla roota. SSH przyjmuje klucze, nie hasła. Jeśli oczekiwanie przekroczy 15 minut, VM nadal działa, a instalacja ponawia próbę co minutę. Do diagnostyki użyj `qm terminal VMID`, a wewnątrz Debiana — `journalctl -u solarman-hub-install`.

Zachowaj plik Cloud-Init wraz z kopią VM. Jego lokalizację znajdziesz w pliku dostępu; zawiera skróty haseł i opcjonalny klucz publiczny. Przed migracją lub przywróceniem musi być dostępny na docelowym węźle. Skrypt obsługuje Proxmox VE 8/9 na amd64, mosty Linux i storage katalogowy na snippets. Konfigurację sprawdzają testy automatyczne, ale instalator nie został jeszcze zweryfikowany przez utworzenie VM na rzeczywistym hoście Proxmox. Przed uruchomieniem możesz przeczytać [kod instalatora](../../scripts/proxmox-vm.sh).

## Instalacja ręczna

Ta instrukcja pokazuje, jak zainstalować Solarman Hub na maszynie wirtualnej z **Debianem 13 (Trixie), amd64**. Maszynę utworzysz w panelu Proxmoxa. Wszystkie polecenia z tej instrukcji wykonuj potem **wewnątrz Debiana**.

## 1. Utwórz maszynę wirtualną

1. Pobierz [oficjalny obraz Debian netinst amd64](https://www.debian.org/distrib/netinst). W Proxmoxie wybierz swój węzeł, magazyn obsługujący obrazy ISO, a następnie **ISO Images → Upload**.
2. Kliknij **Create VM**, nadaj nazwę `solarman-hub`, a w zakładce **OS** wybierz przesłany obraz ISO. Na początek przydziel **2 vCPU, 2048 MB RAM i dysk 20 GB**. Umieść dysk w magazynie objętym kopiami zapasowymi. Dłuższa historia wymaga więcej miejsca.
3. W **Network** wybierz **VirtIO** i most sieci lokalnej, zwykle `vmbr0`. Most i VLAN muszą umożliwiać połączenie loggera z maszyną wirtualną.
4. Zakończ kreator, uruchom maszynę i otwórz **Console**. Zainstaluj Debiana bez środowiska graficznego. Wybierz standardowe narzędzia systemowe; serwer SSH jest opcjonalny. Podczas instalacji ustaw hasło użytkownika root — przyda się do dalszych poleceń w konsoli.
5. Po instalacji odłącz obraz ISO i uruchom system z dysku. W ustawieniach maszyny, w **Options**, włącz **Start at boot** i **QEMU Guest Agent**. Po włączeniu agenta wyłącz i ponownie uruchom maszynę, aby mógł się z nią komunikować. Pakiet agenta zainstalujesz w następnym kroku.
6. Zarezerwuj adres maszyny w ustawieniach DHCP routera. Bieżący adres sprawdzisz w Debianie poleceniem `hostname -I`. Wstawiaj go wszędzie tam, gdzie instrukcja podaje `VM_IP`. To inny adres niż adres panelu Proxmoxa i adres loggera.

Maszyna wirtualna ułatwia instalację Dockera i wykonywanie kopii całego systemu. Docker w LXC wymaga dodatkowej konfiguracji; jeśli wybierzesz ten wariant, zajrzyj do [dokumentacji kontenerów Proxmox](https://github.com/proxmox/pve-docs/blob/master/pct.adoc).

## 2. Zainstaluj Dockera w Debianie

Zaloguj się jako **root** w konsoli Debiana. Na świeżej instalacji Debiana 13 wykonaj:

```sh
apt update
apt install -y docker.io docker-cli docker-compose docker-buildx git ca-certificates qemu-guest-agent curl
systemctl enable --now docker
systemctl start qemu-guest-agent
docker compose version
docker buildx version
```

Dwa ostatnie polecenia powinny wyświetlić wersje Compose **v2** i Buildx. Ta instrukcja korzysta z pakietów [Docker](https://packages.debian.org/trixie/docker.io), [Compose](https://packages.debian.org/trixie/docker-compose) i [Buildx](https://packages.debian.org/trixie/docker-buildx) dostarczanych przez Debiana 13. Jeśli masz już Docker CE, pomiń te polecenia i skorzystaj z jego [instrukcji dla Debiana](https://docs.docker.com/engine/install/debian/). Nie mieszaj obu zestawów pakietów.

## 3. Pobierz i uruchom Hub

```sh
git clone https://github.com/ordigital/solarman-hub.git /opt/solarman-hub
cd /opt/solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
docker compose exec hub solarman-hub token --data-dir /data
```

Przy pierwszym uruchomieniu Docker pobiera potrzebne pakiety i buduje aplikację. Może to potrwać kilka minut. Poczekaj, aż usługa `hub` będzie uruchomiona, a jej stan zmieni się na `healthy`. Ostatnie polecenie wyświetla token administratora. Zachowaj go dla siebie. Nie zmienia się on po restartach ani aktualizacjach, dopóki zachowujesz wolumen danych. Kolejne polecenia wykonuj z tego samego katalogu, aby Compose korzystał z tego samego projektu i wolumenu.

## 4. Połącz logger i sprawdź sieć

Na komputerze w sieci lokalnej otwórz **`http://VM_IP:8080`** i zaloguj się tokenem. Dodaj **numer seryjny loggera** (same cyfry), wybierz zgodny profil, zapisz i zastosuj ustawienia. Następnie w ustawieniach zdalnego serwera TCP loggera wpisz **`VM_IP:10000`**. Wcześniej zapisz jego oryginalne ustawienia serwerów. Zachowanie serwerów A/B zależy od oprogramowania loggera; zmiana adresu może wymagać restartu. Jeśli raporty nie docierają, zajrzyj do pełnej instrukcji.

| Połączenie | Adres docelowy |
|---|---|
| Logger → Hub | Adres IP maszyny wirtualnej, TCP `10000` |
| Przeglądarka → panel | Adres IP maszyny wirtualnej, TCP `8080` |
| Hub → chmura | Skonfigurowany serwer i port chmury, domyślnie `access3.solarmanpv.com:10000` |
| Hub → MQTT | Adres i port Twojego brokera, zwykle `1883` lub port TLS brokera |

Sprawdź, czy na maszynie działa DNS i czy zegar pokazuje prawidłowy czas. Dostęp do Internetu jest potrzebny do instalacji i wysyłania danych do chmury. MQTT wymaga osobnego brokera, na przykład używanego już przez Home Assistant. Ten projekt Compose nie uruchamia brokera. Włącz integrację MQTT w HA i skonfiguruj ten sam broker w Hubie.

Jeśli w Proxmoxie, Debianie lub routerze działa zapora, zezwól na odpowiednie połączenia z loggera i komputerów, z których otwierasz panel. Porty udostępniane przez Dockera mogą omijać reguły UFW w Debianie. Ogranicz dostęp na Proxmoxie lub routerze albo skorzystaj z mechanizmu zapory opisanego w dokumentacji Dockera. Nie przekierowuj portów Huba z Internetu. Przy połączeniu przez most opisanym wyżej nie trzeba przekierowywać portów z hosta Proxmox. Używaj adresu maszyny wirtualnej, a nie prywatnego adresu kontenera Dockera.

Aby używać innych portów i zachować je po aktualizacjach, przed uruchomieniem Huba utwórz plik `/opt/solarman-hub/.env`:

```dotenv
HUB_WEB_PORT=18080
HUB_LOGGER_PORT=18899
```

Następnie ponownie wykonaj `docker compose up -d --wait --wait-timeout 120`. Panel będzie dostępny pod `http://VM_IP:18080`, a logger należy skierować na `VM_IP:18899`. Ustawienia nasłuchu w panelu pozostaw domyślne — te zmienne zmieniają porty udostępniane przez Dockera. Nie udostępniaj pliku `.env` innym osobom.

## 5. Sprawdź działanie

W maszynie wirtualnej, z katalogu `/opt/solarman-hub`, wykonaj:

```sh
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail 100 hub
```

Jeśli zmieniono port panelu, zastąp `8080` właściwym numerem. Jeśli sprawdzenie zakończy się powodzeniem, serwer WWW działa. W panelu sprawdź również połączenie loggera, ostatni pomiar oraz stan chmury i MQTT. Pomiary pojawią się, gdy dodany logger prześle zgodny raport. Logi i eksportowane pliki mogą zawierać identyfikatory urządzeń — przechowuj je prywatnie.

Jeśli brakuje polecenia `docker compose`, sprawdź, czy system to Debian 13 i czy pakiety `docker-cli` oraz `docker-compose` zostały poprawnie zainstalowane. Jeśli `hub` się zatrzymał, najpierw sprawdź logi, a dopiero potem odczytuj token. Gdy panel nie otwiera się w przeglądarce, sprawdź bieżący adres maszyny, most i VLAN, zaporę oraz udostępniony port. Zarezerwuj adres przed wpisaniem go w loggerze.

## 6. Kopie zapasowe, aktualizacje i odtwarzanie

Wolumen Compose `hub-data`, zamontowany pod `/data`, przechowuje tokeny, ustawienia, profile i historię w katalogu danych Dockera wewnątrz maszyny. Przebudowanie kontenera nie usuwa danych z wolumenu. **Jeśli chcesz zachować dane, nie wykonuj `docker compose down -v` ani nie usuwaj tego wolumenu.** Nie umieszczaj go w tymczasowym systemie plików i nie wykluczaj jego dysku z kopii zapasowych.

Aby wykonać spójną kopię całej maszyny, wybierz **Backup → Backup now**, osobny magazyn kopii i tryb **Stop**. Na czas wykonywania kopii maszyna zostanie zatrzymana i nie będzie zbierać danych. Po zakończeniu sprawdź, czy znów działa. Zaplanuj regularne kopie w Proxmoxie i sprawdź ich odtwarzanie. Sama migawka nie zastępuje kopii zapasowej. Kopie zawierają dane logowania, więc ogranicz do nich dostęp. Szczegóły znajdziesz w [dokumentacji kopii i odtwarzania Proxmox](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

Przed aktualizacją wykonaj kopię. Następnie w maszynie wirtualnej uruchom:

```sh
cd /opt/solarman-hub
git pull --ff-only
docker compose build --pull hub
docker compose up -d --wait --wait-timeout 120
docker compose ps
```

Polecenia pobierają najnowszy kod i przebudowują Hub. Wymiana kontenera na krótko przerywa przekazywanie danych. Zachowaj katalog projektu, nazwę projektu Compose i wolumen danych. Aktualizacje bezpieczeństwa Debiana i Dockera instaluj osobno przez APT.

Aby odtworzyć system, wyłącz uszkodzoną maszynę i przywróć wybraną pełną kopię w Proxmoxie. Nie włączaj jednocześnie starej maszyny i odtworzonej kopii. Korzystają z tych samych adresów IP i identyfikatorów MQTT oraz przyjmują połączenia tych samych loggerów. Sprawdź adres w sieci lokalnej, stan usługi i ostatni odebrany pomiar. Dane zapisane po wykonaniu kopii zostaną utracone. Raporty potwierdzone lokalnie podczas awarii nie są później dosyłane do chmury.

## 7. Opcjonalnie: przekaż USB płytki ESP32

Do zwykłej pracy Hub nie potrzebuje ESP32 ani USB. Aby użyć narzędzia do instalacji oprogramowania, podłącz płytkę do hosta Proxmox i w ustawieniach maszyny wybierz **Hardware → Add → USB Device**. Wskaż płytkę i udostępnij ją maszynie wirtualnej. W razie potrzeby uruchom maszynę ponownie. W Debianie sprawdź ścieżkę urządzenia:

```sh
ls -l /dev/serial/by-id/
```

Dalsze kroki znajdziesz w sekcji **ESP32 / Instalacja** w panelu Huba lub w [instrukcji](../../src/solarman_hub/guides/pl.md). Płytka podłączona tylko do komputera z przeglądarką nie jest dostępna w maszynie wirtualnej. Polecenie instalacji uruchamia osobny kontener z narzędziem. **Instalacja obrazu fabrycznego może usunąć ustawienia płytki.**
