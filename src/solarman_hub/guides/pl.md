# Instrukcja użytkownika Solarman Hub

**Solarman Hub to niezależny projekt hobbystyczny. Nie jest powiązany z SOFAR (SofarSolar).**

Ta instrukcja pomoże Ci uruchomić Hub, podłączyć logger i opcjonalnie skorzystać z ESP32 Companion. Wybór języka w Hubie zmienia język panelu oraz instrukcji. Companion ma osobny interfejs w języku angielskim.

## [hub] Korzystanie z Huba

Zaloguj się hasłem do panelu lub tokenem administratora. Panel pokazuje pomiary oraz stan loggera, połączenia z chmurą, MQTT i zapisu danych. Sprawdzaj połączenie loggera i czas ostatniego pomiaru. Logger może być połączony, ale jeszcze nie wysłać pomiarów.

Język zmienisz obok wskaźnika odświeżania. Przeglądarka zapamięta Twój wybór.

W **Przeglądzie** wybierz logger, a następnie **Najnowszy pomiar** lub **Historię**. W historii zobaczysz nazwy pól, jednostki i wersję profilu używane w chwili zapisu. Kliknij nazwę pomiaru, aby otworzyć jego wykres. Wybierz zakres czasu i przesuń wskaźnik nad wykresem albo przesuwaj suwak klawiszami, aby wybrać punkt. Gdy brakuje danych, linia wykresu jest przerwana. Dłuższe zakresy pokazują mniej punktów, ale zachowują najniższe i najwyższe odczyty.

W **Konfiguracji** najpierw zapisz zmiany, a potem wybierz **Zastosuj i połącz ponownie**. Hub zamknie bieżące połączenia, aby loggery mogły połączyć się z nowymi ustawieniami. Zmiana adresu lub portu nasłuchu wymaga także restartu Huba i dopasowania mapowania portów Dockera.

W sekcji **Urządzenia** osobno pokazano dane odebrane z loggera oraz producenta i model z profilu. Przy informacjach, których nie odebrano, widnieje **Brak danych**.

## [install] Instalacja i pierwsze połączenie

**Automatyczna instalacja VM**

Uruchom poniższą komendę jako **root w konsoli Shell węzła Proxmox**, a nie wewnątrz maszyny wirtualnej. Otworzy się instalator, który przeprowadzi Cię przez kolejne kroki. Przed zatwierdzeniem sprawdź podsumowanie.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Wpisz adres IPv4 z maską (np. `192.168.1.50/24` lub `192.168.1.50/255.255.255.0`) albo pozostaw pole puste, aby użyć DHCP. Pytania o bramę i DNS pojawią się tylko przy stałym adresie.

Kreator zapyta o wolny numer VM, nazwę, storage dysku, storage katalogowy na pliki Cloud-Init, most sieciowy i VLAN, DHCP lub stałe IPv4 (adres z prefiksem, bramę i DNS), zasoby, opcjonalny plik publicznego klucza SSH oraz hasło do panelu WWW — co najmniej 8 znaków. Domyślnie utworzy Debiana 13 z 2 vCPU, 2 GB RAM i dyskiem 20 GB. Sprawdzi sumę SHA-512 oficjalnego obrazu i zainstaluje Dockera oraz istniejący projekt Compose Huba wewnątrz nowej VM. Jeśli trzeba, włączy obsługę plików snippets w wybranym storage katalogowym, zachowując pozostałe typy zawartości. Nie zmienia istniejących maszyn.

Zalecamy instalację przez Docker Compose. Na Proxmoxie uruchom Dockera w maszynie wirtualnej z Debianem. Hub może też działać bezpośrednio w Pythonie 3.12 lub nowszym.

Z katalogu repozytorium wykonaj:

```sh
docker compose up -d --build
docker compose exec hub solarman-hub token --data-dir /data
```

Otwórz `http://SERVER_IP:8080` i zaloguj się tokenem. Token jest przechowywany w `/data/admin-token.txt` i nie zmienia się po restartach ani aktualizacjach. Nowy token powstaje tylko wtedy, gdy tego pliku brakuje, na przykład po uruchomieniu z pustym wolumenem danych. Domyślny port udostępniany loggerom to `10000/TCP`. Jeśli masz kontener uruchomiony wcześniej przez `docker run`, Compose nim nie zarządza. Użyj jego rzeczywistej nazwy, na przykład:

```sh
docker exec solarman-hub solarman-hub token --data-dir /data
```

Jeśli domyślne porty są zajęte, możesz udostępnić inne:

```sh
HUB_LOGGER_PORT=18899 HUB_WEB_PORT=18080 docker compose up -d --build
```

Dodaj **numer seryjny loggera** (same cyfry), nie numer falownika. Możesz też ograniczyć dozwolony adres IP i zarezerwować go w DHCP. Wybierz zgodny profil dekodowania, zapisz i zastosuj ustawienia. Hub przyjmuje połączenia tylko od dodanych loggerów. W ustawieniach zdalnego serwera TCP loggera wpisz adres Huba i port udostępniony loggerom. Dokładne kroki znajdziesz poniżej w rozdziale „Lokalny serwer V5 zamiast chmury”.

Uruchomienie bez Dockera:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/solarman-hub serve --data-dir ./data
# In a second terminal:
.venv/bin/solarman-hub token --data-dir ./data
```

Jeśli Hub ma działać stale bez Dockera, skonfiguruj usługę systemową, która będzie go uruchamiać. Polecenie `solarman-hub check-config --data-dir ./data` sprawdza konfigurację i odwołania do profili.

## [cloud] Chmura, lokalne potwierdzenia odbioru i MQTT

Domyślny adres chmury to `access3.solarmanpv.com:10000`. Hub przekazuje raporty V5 i odpowiedzi chmury bez zmian. Nie potrzebuje hasła do konta Solarman, plików cookie ani hasła Wi-Fi. Ramki zawierają jednak identyfikatory urządzeń i metadane protokołu — traktuj je jako prywatne dane instalacji.

ACK informuje logger, że raport został odebrany. Dla obsługiwanych typów raportów Hub wysyła albo potwierdzenie z chmury, albo jedno potwierdzenie lokalne, jeśli połączenie z chmurą nie działa lub przekroczono czas oczekiwania. W tym drugim przypadku zamyka połączenie z chmurą i pomija spóźnione potwierdzenia. Hub przekazuje także poprawne ramki nieznanego typu, ale nie potwierdza ich lokalnie. Ruch działa w obie strony, także dla poleceń z chmury producenta.

Jeśli Internet nie działa, ale sieć lokalna pozostaje dostępna, lokalne pomiary i MQTT mogą działać dalej. **Raporty potwierdzone lokalnie podczas awarii nie są później automatycznie wysyłane do chmury. W historii chmury mogą zostać luki.** Gdy zatrzymasz Hub, przestanie przekazywać dane. Aby wrócić do bezpośredniego połączenia z chmurą, przywróć w loggerze oryginalne adresy serwerów.

Aby korzystać z Home Assistant, połącz obie aplikacje z tym samym brokerem MQTT. W Hubie podaj adres brokera, port, opcjonalnie nazwę użytkownika i hasło oraz ustawienia TLS. Włącz MQTT Discovery. W HA skonfiguruj oficjalną integrację MQTT. Token API Home Assistant nie jest potrzebny. Test brokera sprawdza połączenie i logowanie, ale nie uprawnienia do publikowania danych.

Po pierwszym zgodnym pomiarze MQTT Discovery doda encje w Home Assistant. Ich stałe identyfikatory są oparte na numerze loggera i identyfikatorze pola. Panel osobno pokazuje dostępność MQTT, wiek ostatniego pomiaru i stan połączenia z chmurą. W panelu Energia w HA wybierz liczniki, których chcesz używać. Po zmianie brokera lub prefiksu tematów może być konieczne usunięcie starych wpisów Discovery zapisanych na poprzednim brokerze.

## [history] Historia, wykresy i limity przechowywania

Historia pomiarów jest zapisywana w `/data/history.sqlite3`. Problemy z zapisem nie zatrzymują przekazywania danych do chmury. Jeśli starsza instalacja ma archiwa pomiarów JSONL, Hub jednorazowo zaimportuje je w tle, nadal odbierając nowe raporty. Postęp importu i błędy zapisu sprawdzisz w **Konfiguracji**.

Ustaw **Okres przechowywania historii** w dniach oraz **Limit rozmiaru historii** w MB. Gdy zostanie przekroczony którykolwiek z tych limitów, Hub usuwa najstarsze dane. Wiek danych liczy się od momentu odbioru, niezależnie od zegara falownika. Wpisanie zera wyłącza tylko limit liczby dni. Wyłączenie historii zatrzymuje zapis nowych pomiarów, ale nie usuwa wcześniej zapisanych.

Do limitu rozmiaru wlicza się bazę i jej pliki dziennika. Hub rezerwuje też miejsce potrzebne do pracy bazy. Tymczasowe zapisy mogą go na krótko przekroczyć, dlatego zostaw wolne miejsce na dysku. Surowe ramki, archiwa JSONL i dzienniki zdarzeń mają osobne limity. **Zmniejszenie limitu historii usuwa starsze dane.** Najpierw wykonaj kopię tych, które chcesz zachować.

Wykresy korzystają z czasu pomiaru, a jeśli go brakuje — z czasu odbioru. Dane z różnych wersji profilu są rozdzielane, aby nie mieszać niezgodnych skal i jednostek. Długie zakresy pokazują najwyżej 1500 reprezentatywnych punktów. Jeśli zakres wymaga przeszukania zbyt wielu danych, zawęź go zgodnie z komunikatem. Opóźnione pomiary mogą trafić do historii, ale nie zastępują nowszych odczytów w panelu. Powtórzone pomiary nie są zapisywane ponownie.

## [devices] Dane urządzeń i profile dekodowania

Po połączeniu loggera Hub odczytuje jego numer seryjny i adres IP. Rozpoznane komunikaty początkowe LSW3 mogą zawierać wersję oprogramowania, a obsługiwany raport Sofar HYD — numer seryjny falownika. Przy każdej odczytanej informacji widnieje jej źródło i czas odbioru. Z samego połączenia TCP nie można odczytać adresu MAC. Hub nie próbuje też rozpoznawać nieznanych pól tekstowych.

Wbudowany profil Sofar HYD G3 odczytuje 48 pól z raportu o długości 2115 bajtów. Został sprawdzony na instalacji HYD 15KTL-3PH/LSW3. Inny sprzęt wymaga osobnej weryfikacji. Nawet raport o oczekiwanym kodzie i długości może mieć inny układ pomiarów.

Profile to pliki JSON opisujące kod, długość całej ramki, położenie czasu i pola pomiarowe. Pozycje bajtów liczy się od zera, zaczynając od `A5` na początku pełnej ramki V5. Dla pola podaje się pozycję, długość, kolejność bajtów, obsługę znaku, skalę, jednostkę i opcjonalne klasy HA. Odwołania do rejestrów są notatkami — Hub nie używa ich do odpytywania falownika.

Aby edytować profil wbudowany, utwórz jego kopię. Skorzystaj z podglądu HEX i porównaj kilka raportów z niezależnymi odczytami, zanim przypiszesz profil do loggera. Inny układ raportu V5 może wymagać tylko nowego profilu; inny protokół wymaga zmian w kodzie. Opcja **Tylko przekazywanie** przesyła raporty bez odczytywania pomiarów.

Na stronie profili możesz zaimportować sam profil JSON lub pakiet z ESP32. Sprawdź podsumowanie, status weryfikacji i ewentualne konflikty. Import zapisuje profil, a jeśli pakiet zawiera nowy logger — dodaje go do konfiguracji. Nie stosuje ustawień ani nie zmienia konfiguracji samego loggera. Szkice zawierają surowe, niesprawdzone wartości bez jednostek ani klas energii.

## [spoofing] Lokalny serwer V5 zamiast chmury

Aby odbierać raporty lokalnie, w ustawieniach zdalnego serwera loggera podaj adres Huba lub Companiona. Określenie „spoofing” oznacza tu po prostu użycie własnego lokalnego serwera zamiast serwera chmury.

W codziennym użytkowaniu:

```text
Logger → Hub → manufacturer cloud
             ↘ local history and MQTT
```

Do tymczasowej analizy:

```text
Logger → ESP32 Companion → Hub → manufacturer cloud
```

### Zmień serwer docelowy w ustawieniach loggera

Poniższe kroki dotyczą loggera LSW3 z ukrytą stroną ustawień serwera. Nazwy menu i sposób restartu mogą się różnić zależnie od wersji oprogramowania.

1. **Ustal oba adresy.** Na liście klientów DHCP w routerze znajdź adres IP loggera i adres IP serwera Huba. Przykładowo logger może mieć adres `192.168.100.205`, a Hub `192.168.100.50` — zastąp je adresami ze swojej sieci. Zarezerwuj oba. Adres loggera służy do otwierania jego ustawień, a adres Huba — do wysyłania raportów. Na Proxmoxie adresem Huba jest adres maszyny wirtualnej z Debianem.
2. **Najpierw przygotuj Hub.** W **Konfiguracji** dodaj numer seryjny loggera, wybierz zgodny profil, zapisz ustawienia i kliknij **Zastosuj i połącz ponownie**. Jeśli chcesz nadal wysyłać dane do chmury, włącz przekazywanie do chmury i wpisz jej oryginalny adres z ustawień loggera. Sprawdź port loggerów udostępniony przez Dockera — domyślnie to `10000/TCP`.
3. **Otwórz ustawienia samego loggera.** W przeglądarce na komputerze w tej samej sieci otwórz `http://LOGGER_IP/config_hide.html`. Zamiast `LOGGER_IP` wpisz adres loggera. Zaloguj się danymi administratora loggera, nie kontem Solarman ani tokenem Huba. Sprawdzony logger miał fabryczną nazwę użytkownika `admin` i hasło `admin`. Jeśli nie działają, sprawdź etykietę lub instrukcję loggera albo użyj danych ustawionych przez instalatora. Ta strona wczytuje ukryty formularz ustawień. Bezpośrednie otwarcie `hide_set_edit.html` może nie pozwolić na wczytanie lub zapisanie ustawień.
4. **Zapisz komplet ustawień obu serwerów.** Przed zmianami zanotuj wszystkie pola w **Server A Setting** i **Optional Server Setting(B)**: adres IP, nazwę domeny, port i typ połączenia. Możesz zrobić zrzuty ekranu. Te dane pozwolą Ci wrócić do bezpośredniego połączenia z chmurą.
5. **Ustaw główny serwer.** W **Server A Setting** wpisz lokalny adres IP Huba w **IP address**, wyczyść **Domain name**, w **Port** podaj port loggerów udostępniony przez Dockera, a w **Connection** wybierz **TCP**. Zwykle wystarczy skierować w ten sposób serwer A na Hub. Użyj portu loggerów, nie portu panelu `8080`, portu `8899` ani prywatnego adresu kontenera Dockera. Na początek pozostaw B bez zmian, chyba że Twoje oprogramowanie wymaga wariantu opisanego poniżej.
6. **Zapisz każdy zmieniony formularz.** Serwery A i B mają osobne przyciski **Save**. Zapisz A, a jeśli zmieniono też B — zapisz go oddzielnie. Ponownie otwórz ustawienia i sprawdź zapisane wartości.
7. **Uruchom ponownie logger.** Najpierw użyj opcji restartu w jego panelu. Niektóre wersje oprogramowania utrzymują stare połączenie TCP mimo żądania restartu. Jeśli logger nadal wysyła dane pod stary adres, uruchom ponownie fizycznie tylko logger, o ile instrukcja jego instalacji pozwala zrobić to bezpiecznie. Nie zmieniaj ustawień pracy falownika ani nie odłączaj jego przewodów zasilających, aby zrestartować logger.
8. **Sprawdź, czy docierają nowe pomiary.** W Hubie sprawdź połączenie loggera oraz to, czy czas ostatniego pomiaru jest aktualny i regularnie się zmienia. Samo połączenie nie wystarcza. Jeśli włączono przekazywanie do chmury, sprawdź, czy Hub otrzymuje z niej potwierdzenia ACK. Następnie otwórz stronę chmury producenta i sprawdź, czy pojawiają się tam nowe odczyty. Uwzględnij zwykły odstęp między raportami loggera.

### Jeśli LSW3 wymaga użycia serwera B

W sprawdzonej wersji oprogramowania LSW3 raporty nie zawsze docierały, gdy tylko A wskazywał Hub. Zadziałał następujący układ:

| Ustawienie | Serwer A | Serwer B |
|---|---|---|
| IP address | Lokalny adres IP Huba | Lokalny adres IP Huba |
| Domain name | Puste | Puste |
| Port | `10001`, na którym nic nie nasłuchuje | Port loggerów udostępniony przez Hub, zwykle `10000` |
| Connection | TCP | TCP |

A celowo wskazuje zamknięty port lokalny, aby logger przeszedł na B. **B jest serwerem zapasowym — logger nie wysyła równocześnie kopii każdego raportu do obu serwerów.** Upewnij się, że na wybranym porcie A nic nie nasłuchuje. Zapisz oba formularze osobno, uruchom logger ponownie i sprawdź pomiary w Hubie oraz chmurze. Ten sposób dotyczy sprawdzonej wersji oprogramowania; użyj go, jeśli zwykłe ustawienie A nie działa.

### Wróć do bezpośredniego połączenia z chmurą

Przywróć komplet oryginalnych ustawień A i B, łącznie z nazwami domen, portami i typem połączenia. Zapisz każdy formularz i uruchom ponownie tylko logger. Zanim zatrzymasz Hub, sprawdź, czy w chmurze producenta pojawiają się nowe pomiary. Raporty potwierdzone lokalnie podczas przerwy nie zostaną później dosłane do historii chmury.

### Włącz Companion między logger a Hub

W Companionie włącz tylko jeden serwer docelowy: Hub albo chmurę. Nie wysyłaj tego samego raportu równocześnie do obu. Jeśli wybierasz Hub, najpierw dodaj w nim numer loggera i podaj udostępniony port TCP Huba. Companion czeka na nawiązanie połączenia do 3 sekund. Czas oczekiwania na ACK wynosi domyślnie 30 sekund i można go ustawić w zakresie 10–120 sekund. Jeśli Companion łączy się przez Hub, daj mu więcej czasu, niż Hub potrzebuje na połączenie z chmurą, wymianę komunikatów początkowych i odbiór ACK. Bez serwera docelowego Companion potwierdza obsługiwane ramki lokalnie, a dane nie trafiają do chmury.

Lokalne ACK wymagają prawidłowego czasu. Zwykle dostarcza go NTP. Jeśli zegar nie jest ustawiony, Companion może pobrać czas z przeglądarki po otwarciu panelu. Do czasu ustawienia zegara Companion nie potwierdza raportów, aby logger mógł ponowić wysyłanie.

## [esp32] Instalacja i konfiguracja ESP32 Companion

Gotowe oprogramowanie jest przeznaczone dla **klasycznego ESP32 z 4 MB pamięci flash** i zostało sprawdzone na rodzinie ESP32-D0WD-V3. Nie pasuje do ESP32-C3, S2 ani S3. Płytkę zasilaj przez USB; komunikacja odbywa się przez Wi-Fi.

Gotowe pliki i sumy kontrolne znajdują się w `firmware/esp32-companion/dist/`:

- `factory.bin` — pierwsza instalacja przez USB, zawiera także program rozruchowy i tablicę partycji;
- `firmware.bin` — sama aplikacja do aktualizacji OTA;
- `SHA256SUMS` — sumy kontrolne plików.

Użyj przewodu USB obsługującego transmisję danych. Zainstaluj narzędzie w środowisku wirtualnym i sprawdź właściwy port:

```sh
python3 -m venv .esp-tools
.esp-tools/bin/pip install esptool==5.6.0
.esp-tools/bin/python -m esptool --port /dev/ttyUSB0 flash-id
sha256sum -c firmware/esp32-companion/dist/SHA256SUMS
.esp-tools/bin/python -m esptool --chip esp32 --port /dev/ttyUSB0 write-flash 0x0 firmware/esp32-companion/dist/factory.bin
```

Dostęp do portu szeregowego może wymagać dodania użytkownika do odpowiedniej grupy systemowej. Przed instalacją zamknij monitory portu szeregowego. Jeśli płytka nie przejdzie automatycznie w tryb programowania, przytrzymaj BOOT podczas uruchamiania narzędzia. Puść przycisk, gdy narzędzie połączy się z płytką. Instalacja obrazu fabrycznego może usunąć ustawienia; OTA je zachowuje.

Na **serwerze z Linuxem i Docker Engine** możesz też użyć jednorazowego kontenera. Pobierz lub sklonuj repozytorium i wykonuj polecenia z jego głównego katalogu. Zamknij monitory portu szeregowego, podłącz ESP32 do serwera Dockera i sprawdź ścieżkę urządzenia. `/dev/ttyUSB0` jest tylko przykładem:

```sh
ls -l /dev/serial/by-id/
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm --build esp-flash flash-id
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm esp-flash
```

Pierwsze polecenie buduje narzędzie i sprawdza podłączony układ bez zapisywania go. Drugie sprawdza sumę kontrolną dołączonego pliku i wgrywa `factory.bin` pod adres `0x0`. W `ESP_PORT` podaj ścieżkę swojej płytki: `/dev/ttyUSB…`, `/dev/ttyACM…` lub `/dev/serial/by-id/…`. Narzędzie działa niezależnie od Huba i nie wymaga instalacji Pythona na serwerze. Przy kolejnych aktualizacjach używaj OTA, aby zachować ustawienia.

USB musi być dostępne **na maszynie, na której działa usługa Dockera**, a nie tylko na komputerze z przeglądarką. Na Proxmoxie najpierw udostępnij USB płytki maszynie wirtualnej. Powyższe polecenia są przeznaczone dla Docker Engine na Linuxie. Docker Desktop na Windowsie i macOS domyślnie nie udostępnia tak portów szeregowych. Na tych systemach skorzystaj z esptool bezpośrednio na komputerze, zgodnie z wcześniejszą instrukcją, lub skonfiguruj przekazywanie USB.

Po zalogowaniu w sekcji **ESP32 / Instalacja** możesz pobrać **Oprogramowanie do pierwszej instalacji przez USB**, **Oprogramowanie do aktualizacji OTA** i **Sumy kontrolne SHA-256**. Panel służy do pobierania plików — nie wgrywa oprogramowania przez USB komputera z przeglądarką.

Otwórz port szeregowy USB z prędkością **115200 bodów**. Komunikaty startowe zawierają unikalną nazwę i hasło sieci konfiguracyjnej oraz nazwę administratora `admin` z jego unikalnym hasłem. Połącz się z tą siecią i otwórz `http://192.168.4.1`. W oknie logowania przeglądarki podaj dane administratora. Wpisz nazwę i hasło swojej domowej sieci Wi-Fi, a następnie zapisz ustawienia. Płytka uruchomi się ponownie. Jej adres w sieci lokalnej znajdziesz w komunikatach USB lub w DHCP routera. Możesz też spróbować `http://solarman-companion.local`.

Tryb odbiornika nasłuchuje na `10000/TCP`. Ustaw dozwolony numer loggera, opcjonalnie wybierz serwer docelowy i skieruj logger na adres ESP32. Jednocześnie może być połączony jeden logger. Kolejka mieści cztery raporty, a pojedyncza ramka może mieć do 4096 bajtów. Bufor ramek, ostatni raport i przechwycony ruch są przechowywane w RAM i znikają po restarcie.

Aby zbudować oprogramowanie ze źródeł, użyj PlatformIO z plikiem `firmware/esp32-companion/platformio.ini`.

## [export] Eksport profili, ustawień i przechwyconego ruchu

W sekcji **Profile builder and exports** Companiona najpierw odbierz raport. Następnie wczytaj znany profil HYD, niezweryfikowany szkic surowych wartości lub zapisany własny profil. Szkic pokazuje do 64 surowych słów danych. Ustal ich znaczenie, kolejność bajtów i skalę, porównując kilka raportów z niezależnymi pomiarami. Zanim użyjesz tych wartości jako pomiarów, musisz ustalić, co oznaczają.

Edytuj JSON i zapisz własny profil na płytce albo pobierz go bezpośrednio. Profil może mieć najwyżej 12 KiB i 128 pól. Pakiet importu dla Huba zawiera także proponowany wpis loggera i status weryfikacji. Surowy raport dołączaj tylko wtedy, gdy jest potrzebny — zawiera identyfikatory urządzeń. Zaimportuj plik w Hubie, sprawdź dane, zapisz je, a następnie zastosuj ustawienia.

Opcja **Download ESP32 settings (without passwords)** eksportuje nazwy sieci, tryb pracy oraz parametry przechwytywania i serwera docelowego. Plik nie zawiera haseł Wi-Fi ani administratora. Zachowaj ten plik jako zapis ustawień; po odtwarzaniu na wyczyszczonej płytce hasła trzeba wpisać ponownie. OTA zachowuje ustawienia NVS i profil zapisany w pamięci flash.

W trybie pasywnym ustaw adres MAC loggera i BSSID jego punktu dostępowego. W sieci mesh połącz ESP32 z tym samym punktem dostępowym co logger. ESP32 ma jedno radio 2,4 GHz i przechwytuje ruch na kanale, z którym jest połączone. Klasyczny ESP32 nie przechwytuje pasma 5 GHz. Jeśli logger przełączy się do innego punktu dostępowego, zmień punkt docelowy lub kanał przechwytywania.

Pobierany PCAP zawiera około 32 KiB ostatnio przechwyconego ruchu. Najstarsze pakiety są nadpisywane, a licznik pokazuje, ile pakietów pominięto z powodu pełnej kolejki. Podczas analizy często pobieraj plik, szczególnie gdy logger rozłącza się i łączy ponownie. Chronione ramki Wi-Fi pozostają zaszyfrowane. Do odszyfrowania WPA2 na komputerze zwykle potrzebne są hasło Wi-Fi i zapis komunikatów wymienianych przy nawiązywaniu połączenia (handshake). Ta instrukcja nie obejmuje odszyfrowywania WPA3. Do analizy użyj Wiresharka i przechowuj pliki prywatnie. Zobacz [instrukcję odszyfrowywania w Wiresharku](https://wiki.wireshark.org/HowToDecrypt802.11).

## [ota] Aktualizacje OTA i odzyskiwanie płytki

Pobierz zgodny plik `firmware.bin` Companiona, sprawdź sumę kontrolną i otwórz **Firmware update (OTA)**. Prześlij jeden plik aplikacji, zapewniając stabilne zasilanie. Nie przesyłaj `factory.bin` przez OTA. Aktualizator sprawdza logowanie oraz informacje o układzie i produkcie w pliku. Nowa aplikacja jest aktywowana dopiero po zakończeniu przesyłania.

Podczas aktualizacji przechwytywanie i przekazywanie raportów są wstrzymane, więc logger może połączyć się ponownie. Jeśli przesyłanie się nie powiedzie lub zostanie przerwane, pozostaje obecna aplikacja, a urządzenie wznawia pracę. Udana aktualizacja uruchamia ESP32 ponownie. Jeśli nowa aplikacja się nie uruchomi, oprogramowanie nie wróci automatycznie do poprzedniej wersji. Aby przywrócić działanie płytki, użyj BOOT i wgraj obraz fabryczny przez USB.

OTA korzysta z HTTP i logowania administratora. Pliki oprogramowania nie są podpisane kryptograficznie, dlatego używaj zaufanych plików i aktualizuj tylko w zaufanej sieci lokalnej. Każdy, kto zna hasło administratora, może zainstalować oprogramowanie. Chroń hasło i pliki z przechwyconym ruchem.

## [operations] Kopie zapasowe i rozwiązywanie problemów

Aby ustawić lub zmienić hasło do panelu WWW, uruchom poniższe komendy z katalogu projektu Compose. Użyj co najmniej 8 znaków. Hub zapisuje solony skrót w `/data/admin-password.json`, a nie samo hasło. Restart włącza nowe hasło i zamyka dotychczasowe sesje WWW. Token administratora nadal pozwala odzyskać dostęp i korzystać z API.

```sh
docker compose exec hub solarman-hub password --data-dir /data
docker compose restart hub
```

Kopię całego wolumenu `/data` wykonuj przy zatrzymanym Hubie. Powinna obejmować bazę SQLite, konfigurację, profile, token i archiwa. Jeśli montujesz katalog z hosta, ustaw jego właściciela i grupę na UID/GID `10001`. Jeśli chcesz zachować dane, nie używaj `docker compose down -v`. Plik konfiguracji zawiera jawne hasło MQTT, a dostęp do niego ograniczają uprawnienia systemu plików. Odpowiedzi API nie ujawniają hasła.

Sprawdź logi i liczniki zapisu w panelu. Przydatne są też polecenia:

```sh
docker compose logs --tail 100 hub
docker compose restart hub
```

Poprawny stan usługi oznacza, że serwer WWW odpowiada. Stan chmury i MQTT sprawdzaj osobno. Pełny dysk, powolny zapis lub pełne kolejki mogą powodować luki w danych mimo działającego przekazywania raportów. Liczniki zapisu pokazują liczbę pominiętych pomiarów.

Jeśli dane nie docierają, sprawdź adres i port docelowy, mapowanie portów Dockera, DHCP, listę dozwolonych numerów loggerów i to, czy logger rzeczywiście się zrestartował. Same komunikaty początkowe nie zawierają jeszcze pomiarów. Jeśli nie udaje się odczytać pomiarów, sprawdź kod i długość ramki w profilu, czas pomiaru oraz podgląd HEX. Odbiór starego raportu nie oznacza aktualnych pomiarów. Jeśli wykres jest pusty, sprawdź zakres czasu i wersję profilu. Jeśli ESP32 jest niedostępne, sprawdź jego sieć konfiguracyjną, kanał Wi-Fi, komunikaty USB i zasilanie.

Panele HTTP Huba i Companiona udostępniaj tylko w zaufanej sieci lokalnej lub przez VPN. Przy zdalnym dostępie do Huba użyj odwrotnego proxy HTTPS z `HUB_COOKIE_SECURE=1`. Nie wystawiaj odbiornika V5 TCP bezpośrednio do Internetu — nie ma on uwierzytelniania. Ograniczenia numeru loggera i adresu IP nie zapewniają bezpiecznego uwierzytelnienia urządzenia.
