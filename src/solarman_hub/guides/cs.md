# Uživatelský návod k Solarman Hubu

**Solarman Hub je nezávislý hobby projekt. Není spojen se společností SOFAR (SofarSolar).**

Návod vám pomůže nastavit Hub, připojit logger a případně používat ESP32 Companion. Volba jazyka v Hubu mění jazyk rozhraní i návodu. Companion má vlastní anglické rozhraní.

## [hub] Používání Hubu

Přihlaste se heslem webového panelu nebo tokenem správce. Přehled zobrazuje měření a stav loggeru, připojení ke cloudu, MQTT a místního úložiště. Sledujte připojení loggeru i čas posledního měření: připojený logger ještě nemusel odeslat žádnou zprávu.

Jazyk změníte vedle ukazatele obnovování. Prohlížeč si vaši volbu zapamatuje.

V části **Přehled** vyberte logger a zvolte **Nejnovější měření** nebo **Historie**. Starší měření si zachovávají původní názvy položek, jednotky a revizi profilu. Kliknutím na název veličiny otevřete časový graf. Vyberte období, pohybujte ukazatelem nad grafem nebo ovládejte posuvník datových bodů klávesnicí. Výpadky příjmu se projeví přerušením křivky. Delší období zobrazuje méně bodů, ale zachovává nejnižší a nejvyšší hodnoty.

V části **Konfigurace** změny nejprve uložte a potom aktivujte tlačítkem **Použít a znovu připojit**. Tím se ukončí stávající relace loggerů, aby se mohly znovu připojit s novým nastavením. Změna naslouchací adresy nebo portu vyžaduje také restart Hubu a odpovídající mapování portů Dockeru.

Část **Zařízení** zobrazuje údaje přijaté od loggeru odděleně od výrobce a modelu uvedeného v profilu. Dosud nepřijaté informace jsou označené jako nepřijaté.

## [install] Instalace a první připojení

**Automatická instalace VM**

Tento příkaz spusťte jako **root v Shellu uzlu Proxmox**, nikoli uvnitř VM. Průvodce vás provede jednotlivými kroky. Před potvrzením zkontrolujte souhrn.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Zadejte adresu IPv4 s maskou (například `192.168.1.50/24` nebo `192.168.1.50/255.255.255.0`), nebo ponechte pole prázdné pro DHCP. Na bránu a DNS se průvodce zeptá pouze u statické adresy.

Průvodce se zeptá na volné ID VM, název, úložiště disku, adresářové úložiště pro Cloud-Init snippets, síťový most/VLAN, DHCP nebo statické IPv4 (adresu/prefix, bránu a DNS), prostředky, volitelný soubor veřejného SSH klíče a heslo do webového panelu o nejméně 8 znacích. Výchozí nastavení: Debian 13, 2 vCPU, 2 GB RAM a disk 20 GB. Ověří SHA-512 oficiálního obrazu a do nové VM nainstaluje Docker a stávající projekt Compose. V případě potřeby přidá do adresářového úložiště typ obsahu snippets; ostatní typy zachová. Existující VM nemění.

Doporučeným způsobem instalace je Docker Compose. Na Proxmoxu spouštějte Docker ve VM s Debianem. Hub můžete také spustit přímo s Pythonem 3.12 nebo novějším.

V adresáři repozitáře:

```sh
docker compose up -d --build
docker compose exec hub solarman-hub token --data-dir /data
```

Otevřete `http://SERVER_IP:8080` a přihlaste se tokenem. Token je uložen v `/data/admin-token.txt` a při restartech ani aktualizacích se nemění. Nový se vytvoří pouze tehdy, když soubor chybí, například při spuštění s prázdným datovým svazkem. Výchozí zveřejněný port loggeru je `10000/TCP`. Stávající kontejner spuštěný přes `docker run` Compose nespravuje. Použijte jeho skutečný název, například:

```sh
docker exec solarman-hub solarman-hub token --data-dir /data
```

Konfliktům můžete předejít použitím jiných portů hostitele:

```sh
HUB_LOGGER_PORT=18899 HUB_WEB_PORT=18080 docker compose up -d --build
```

Zadejte číselné **sériové číslo loggeru**, nikoli měniče. Volitelně omezte zdrojovou IP adresu a rezervujte ji v DHCP. Vyberte odpovídající dekódovací profil, nastavení uložte a použijte. Nová instalace nepřijímá neznámá sériová čísla loggerů. Vzdálený TCP server loggeru nastavte na IP adresu hostitele Hubu a zveřejněný port loggeru. Podrobný postup najdete níže v části „Přesměrování vlastního loggeru na místní server V5“.

Pro provoz bez Dockeru:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/solarman-hub serve --data-dir ./data
# In a second terminal:
.venv/bin/solarman-hub token --data-dir ./data
```

Pro trvalý provoz instalace v Pythonu použijte správce procesů. Příkaz `solarman-hub check-config --data-dir ./data` ověří konfiguraci a odkazy na profily.

## [cloud] Předávání do cloudu, místní ACK a MQTT

Výchozí cloudový cíl je `access3.solarmanpv.com:10000`. Hub předává zprávy V5 a odpovědi cloudu beze změn. Nepotřebuje heslo k účtu Solarman, cookies ani heslo k Wi-Fi. Rámce stále obsahují identifikátory zařízení a metadata protokolu; jde o soukromá data vaší instalace.

ACK potvrzuje loggeru přijetí zprávy. U podporovaných typů zpráv Hub odešle buď ACK z cloudu, nebo při chybě či vypršení času cloudového spojení právě jedno místní ACK. Poté neúspěšnou cloudovou relaci ukončí a pozdní ACK ignoruje. Neznámé platné rámce lze předávat, ale nedostanou místní ACK. Provoz proudí oběma směry, včetně příkazů z cloudu výrobce.

Při výpadku internetu a funkční místní síti mohou místní měření i MQTT pokračovat. **Zprávy potvrzené místně během výpadku se později automaticky neodešlou do cloudu. Cloudová historie může mít mezery.** Zastavení Hubu přeruší nastavenou cestu předávání. Pokud se vracíte k přímému spojení s cloudem, obnovte původní cílové servery loggeru.

Pro Home Assistant připojte obě aplikace ke stejnému MQTT brokeru. V Hubu zadejte server, port, případně uživatelské jméno a heslo i nastavení TLS a zapněte MQTT Discovery. V HA nastavte oficiální integraci MQTT. Token API HA není potřeba. Test brokeru ověřuje spojení a přihlášení, nikoli oprávnění k publikování (ACL).

Discovery se objeví po prvním kompatibilním měření. Stálá ID senzorů vycházejí ze sériového čísla loggeru a ID položky. Dostupnost MQTT, stáří posledního měření a cloudové spojení se sledují odděleně. Vhodné elektroměry pro energetický přehled HA vyberte sami. Při změně brokeru nebo prefixu témat může být potřeba odstranit stará uchovaná témata Discovery na původním brokeru.

## [history] Historie, grafy a uchovávání dat

Historie měření se ukládá do `/data/history.sqlite3`. Potíže s úložištěm nezastaví předávání do cloudu. Pokud starší instalace obsahuje archivy měření JSONL, Hub je jednorázově importuje na pozadí a přitom dál přijímá nové zprávy. Průběh importu a chyby úložiště najdete v části **Konfigurace**.

Nastavte **Uchování historie** ve dnech a **Limit velikosti historie** v MB. Platí oba limity; první dosažený odstraní nejstarší data. Stáří se počítá podle času přijetí, aby chybné hodiny měniče neudržovaly data navždy. Nula dní vypíná pouze omezení podle stáří. Vypnutí historie zastaví ukládání nových měření, ale nesmaže již uložená data.

Limit velikosti zahrnuje databázi a její žurnálové soubory i rezervu pro údržbu databáze. Dočasné zápisy ho mohou krátce překročit, proto nechte na disku volné místo. Surové rámce, archivy JSONL a protokoly událostí mají samostatné limity. **Snížení limitu historie smaže starší data.** To, co chcete zachovat, nejprve zálohujte.

Grafy používají čas měření, pokud je k dispozici, jinak čas přijetí. Oddělené revize profilu brání směšování neslučitelných měřítek nebo jednotek. Dlouhá období vracejí nejvýše 1500 reprezentativních bodů. Pokud dotaz překročí limit prohledávání, zobrazí se výzva ke zkrácení období. Opožděné měření se může objevit v historii, aniž by nahradilo nejnovější živý stav. Duplicitní měření se odstraňují.

## [devices] Údaje o zařízeních a dekódovací profily

Hub získává sériové číslo loggeru a IP protistrany z relace V5/TCP. Ověřené formáty úvodní komunikace LSW3 mohou obsahovat verzi firmwaru; podporovaná zpráva Sofar HYD obsahuje sériové číslo měniče. Každý dekódovaný identifikační údaj uvádí zdroj a čas zjištění. Hub neodvozuje MAC adresu z TCP spojení ani neodhaduje libovolná textová pole.

Vestavěný profil Sofar HYD G3 dekóduje 48 položek ze zprávy o délce 2115 bajtů. Byl ověřen na instalaci HYD 15KTL-3PH/LSW3. Jiný hardware vyžaduje nezávislé ověření. Zpráva může mít očekávaný kód i délku, ale jiné rozložení měření.

Profily jsou deklarativní soubory JSON s kódem, délkou celého rámce, mapováním časového razítka a položkami. Posun nula označuje první bajt `A5` úplného rámce V5. U položek se zadává posun, šířka, pořadí bajtů, znaménko, měřítko, jednotka a volitelné třídy HA. Odkazy na registry slouží jako poznámky; Hub je nepoužívá k dotazování měniče.

Pro úpravy vytvořte kopii vestavěného profilu. Před přiřazením mapování použijte náhled HEX a porovnejte několik zpráv s nezávislými měřeními. Jiné rozložení V5 může vyžadovat pouze nový profil; jiný přenosový protokol vyžaduje změnu kódu. **Pouze předávání** přenáší zprávy bez dekódování.

Na stránce profilů importujte samostatný profil JSON nebo balíček ESP32. Zkontrolujte souhrn, stav ověření a konflikty. Import uloží profil a případně nový záznam loggeru. Nastavení nepoužije ani nepřenastaví logger. Koncepty se surovými slovy obsahují neověřené hodnoty bez přiřazených jednotek a energetických tříd.

## [spoofing] Přesměrování vlastního loggeru na místní server V5

Chcete-li přijímat zprávy místně, změňte vzdálený server loggeru na Hub nebo Companion. Pojem „spoofing“ v tomto návodu znamená pouze použití místního serveru místo cloudového cíle.

Pro běžný provoz:

```text
Logger → Hub → manufacturer cloud
             ↘ local history and MQTT
```

Pro dočasnou analýzu:

```text
Logger → ESP32 Companion → Hub → manufacturer cloud
```

### Změna vzdáleného serveru loggeru

Následující postup je určen pro logger LSW3 se skrytou stránkou nastavení serverů. Názvy nabídek a chování při restartu se mohou lišit podle firmwaru.

1. **Zjistěte obě adresy.** V seznamu DHCP klientů routeru najděte místní IP adresu loggeru i serveru Hubu. Logger může mít například `192.168.100.205` a Hub `192.168.100.50`; tyto příklady nahraďte vlastními adresami. Obě adresy rezervujte. Adresa loggeru slouží k otevření jeho nastavení, na adresu Hubu se budou posílat zprávy. Na Proxmoxu použijte pro Hub adresu VM s Debianem.
2. **Nejprve připravte Hub.** V části **Konfigurace** přidejte číselné sériové číslo loggeru, vyberte odpovídající profil, uložte nastavení a zvolte **Použít a znovu připojit**. Pokud chcete zachovat odesílání do cloudu, zapněte předávání do cloudu s původním cloudovým cílem loggeru. Ověřte port loggeru zveřejněný Dockerem; výchozí je `10000/TCP`.
3. **Otevřete vlastní nastavení loggeru.** V prohlížeči ve stejné místní síti otevřete `http://LOGGER_IP/config_hide.html`. `LOGGER_IP` nahraďte adresou loggeru. Přihlaste se údaji správce loggeru, nikoli účtem Solarman nebo tokenem Hubu. U testovaného loggeru byly tovární údaje uživatelské jméno `admin` a heslo `admin`. Pokud nefungují, podívejte se na štítek a do návodu loggeru nebo použijte údaje od instalačního technika. Pokud bylo heslo změněno, použijte aktuální heslo. Skrytý formulář nastavení se načítá uvnitř této stránky. Při přímém otevření `hide_set_edit.html` nemusí fungovat načtení ani uložení nastavení.
4. **Uschovejte obě konfigurace serverů.** Před úpravami si poznamenejte všechny hodnoty v **Server A Setting** a **Optional Server Setting(B)**, včetně IP adresy, doménového jména, portu a typu spojení. Hodí se i snímky obrazovky. Údaje si ponechte pro případný návrat k přímému odesílání do cloudu.
5. **Nastavte hlavní cíl.** V části **Server A Setting** zadejte do **IP address** místní IP adresu Hubu, vymažte **Domain name**, do **Port** zadejte zveřejněný port loggeru na Hubu a v **Connection** zvolte **TCP**. Tím za běžných okolností nasměrujete A na Hub. Použijte port loggeru, nikoli port webového rozhraní `8080`, port `8899` nebo soukromou IP adresu kontejneru Dockeru. B zpočátku neměňte, pokud váš firmware nepotřebuje níže popsané záložní nastavení.
6. **Uložte každý změněný formulář.** A i B mají vlastní tlačítko **Save**. Uložte A, a pokud jste upravili i B, uložte ho zvlášť. Nastavení znovu otevřete a ověřte uložené hodnoty.
7. **Restartujte logger.** Nejprve použijte jeho funkci restartu. Některý firmware ponechá staré TCP spojení i po požadavku na restart z rozhraní. Pokud logger stále posílá na původní cíl, fyzicky restartujte pouze logger, a to jen tehdy, pokud to jeho instalační pokyny dovolují bezpečně provést. Neměňte provozní nastavení měniče a kvůli restartu loggeru neodpojujte silové kabely měniče.
8. **Ověřte skutečný příjem zpráv.** V Hubu zkontrolujte, že se logger připojil a že nově přijatá měření mají aktuální čas a průběžně se obnovují. Samotné připojení nestačí. Pokud je zapnuté předávání do cloudu, ověřte, že Hub dostává cloudová potvrzení (ACK), a potom zkontrolujte i nové hodnoty na cloudové stránce výrobce. Počítejte s běžným intervalem odesílání loggeru.

### Pokud váš LSW3 potřebuje server B jako záložní cíl

U testovaného firmwaru LSW3 nebylo odesílání spolehlivé, pokud na Hub směřoval pouze A. Fungovalo toto nastavení:

| Nastavení | Server A | Server B |
|---|---|---|
| IP adresa | Místní IP adresa Hubu | Místní IP adresa Hubu |
| Doménové jméno | Prázdné | Prázdné |
| Port | `10001`, na kterém nic nenaslouchá | Zveřejněný port loggeru na Hubu, obvykle `10000` |
| Spojení | TCP | TCP |

A záměrně směřuje na zavřený místní port, aby logger přešel na B. **B je záložní cíl, nikoli druhá souběžná kopie každé zprávy.** Ověřte, že na zvoleném portu A nic nenaslouchá. Uložte oba formuláře zvlášť, restartujte logger a zopakujte výše uvedené kontroly měření i cloudu. Toto chování platí pro testovaný firmware; použijte ho, pokud běžné nastavení A nefunguje.

### Návrat k přímému odesílání do cloudu

Obnovte úplné původní nastavení A i B, včetně doménových jmen, portů a typů spojení. Uložte každý formulář a restartujte pouze logger. Před zastavením Hubu ověřte, že do cloudu výrobce přicházejí nová měření. Zprávy potvrzené místně během přerušení se později do cloudové historie neodešlou.

### Zapojení Companionu mezi logger a Hub

Na Companionu zapněte právě jeden cíl předávání. Zvolte Hub nebo cloud; nepokoušejte se posílat stejnou zprávu oběma. Při předávání do Hubu v něm nejprve povolte sériové číslo loggeru a použijte zveřejněný TCP port. Limit připojení Companionu k cíli je 3 sekundy. Nastavitelný limit ACK má výchozí hodnotu 30 sekund a rozsah 10–120 sekund. Při použití Hubu musí být delší než celý jeho postup připojení, inicializace a čekání na ACK. Bez cíle předávání Companion potvrzuje známé rámce místně; do cloudu se nic nedoručí.

Místní ACK vyžadují správný čas. Běžně ho poskytuje NTP. Pokud Companion dosud nemá platný čas, při otevření rozhraní ho získá také z prohlížeče. Dokud není čas nastaven, zprávu nepotvrdí, aby ji logger mohl poslat znovu.

## [esp32] Nahrání a nastavení ESP32 Companionu

Dodaná sestava je určena pro **klasický ESP32 se 4 MB flash** a byla testována na rodině ESP32-D0WD-V3. Není určena pro ESP32-C3, S2 ani S3. Vývojovou desku napájejte přes USB; komunikuje přes Wi-Fi.

Hotové obrazy a kontrolní součty najdete v `firmware/esp32-companion/dist/`:

- `factory.bin`: první instalace přes USB včetně zavaděče a tabulky oddílů;
- `firmware.bin`: samotná aplikace pro OTA;
- `SHA256SUMS`: kontrolní součty pro ověření integrity.

Použijte USB kabel podporující přenos dat. Nainstalujte nástroj do virtuálního prostředí a určete správný port:

```sh
python3 -m venv .esp-tools
.esp-tools/bin/pip install esptool==5.6.0
.esp-tools/bin/python -m esptool --port /dev/ttyUSB0 flash-id
sha256sum -c firmware/esp32-companion/dist/SHA256SUMS
.esp-tools/bin/python -m esptool --chip esp32 --port /dev/ttyUSB0 write-flash 0x0 firmware/esp32-companion/dist/factory.bin
```

Přístup k sériovému portu může vyžadovat členství v příslušné skupině operačního systému. Před nahráváním zavřete sériové monitory. Pokud automatický vstup do zavaděče selže, při spuštění nástroje držte BOOT a po navázání spojení tlačítko uvolněte. Tovární obraz může resetovat uložené nastavení; OTA ho zachovává.

Na **linuxovém hostiteli s Docker Engine** můžete firmware nahrát také jednorázovým kontejnerem. Naklonujte nebo stáhněte tento repozitář a příkazy spusťte z jeho kořene. Zavřete sériové monitory, připojte ESP32 k tomuto hostiteli Dockeru a zjistěte jeho sériové zařízení; `/dev/ttyUSB0` je příklad:

```sh
ls -l /dev/serial/by-id/
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm --build esp-flash flash-id
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm esp-flash
```

První příkaz Dockeru sestaví nástroj a ověří připojený čip bez zápisu. Druhý ověří kontrolní součet přiloženého obrazu a nahraje `factory.bin` na adresu `0x0`. Nahraďte `ESP_PORT` skutečnou cestou desky `/dev/ttyUSB…`, `/dev/ttyACM…` nebo `/dev/serial/by-id/…`. Nástroj nepotřebuje Python na hostiteli a běží odděleně od Hubu. Pro další aktualizace použijte OTA, abyste zachovali nastavení.

USB musí být dostupné **na počítači, kde běží démon Dockeru**, nikoli jen na počítači s otevřeným webovým rozhraním. Ve VM na Proxmoxu nejprve předejte USB zařízení do této VM. Uvedené příkazy jsou určeny pro Linux Docker Engine. Docker Desktop na Windows/macOS takto sériová zařízení standardně nezpřístupňuje. Na těchto systémech použijte nativní esptool podle postupu výše nebo výslovně nastavte předání USB.

Stránka Hubu **ESP32 / Nahrání firmwaru** po přihlášení nabízí také soubory **Firmware pro první instalaci přes USB**, **Firmware pro aktualizaci OTA** a **Kontrolní součty SHA-256**. Webové rozhraní soubory stahuje; nenahrává firmware přes USB počítače s prohlížečem.

Sériový výstup USB čtěte rychlostí **115200 baudů**. Při startu vypíše jedinečné SSID a heslo pro nastavení a správce `admin` s jedinečným heslem. Připojte se k nastavovacímu přístupovému bodu a otevřete `http://192.168.4.1`. Do výzvy prohlížeče zadejte údaje správce. Nastavte SSID a heslo domácí sítě a uložte je. Deska se restartuje; její adresu v LAN zjistíte ze sériového výstupu nebo DHCP, případně zkuste `http://solarman-companion.local`.

Režim přijímače naslouchá na `10000/TCP`. Nastavte povolené sériové číslo loggeru, případně cíl předávání, a logger nasměrujte na IP adresu ESP32. Přijímač podporuje jeden aktivní logger, čtyři čekající zprávy a rámce do 4096 bajtů. Vyrovnávací paměť rámců, zpráva i pasivní záznam jsou v RAM a při restartu se ztratí.

Pro sestavení ze zdrojů použijte PlatformIO s `firmware/esp32-companion/platformio.ini`.

## [export] Export profilů, nastavení a záznamů

V části Companionu **Profile builder and exports** přijměte zprávu a načtěte známé mapování HYD, neověřený koncept surových slov nebo uložený vlastní profil. Koncept zpřístupní až 64 surových slov. Jejich význam, pořadí bajtů a měřítko určete porovnáním několika zpráv s nezávislými měřeními. Než lze surové hodnoty použít jako měření, je nutné je ručně interpretovat.

Upravte JSON a uložte vlastní profil na desku nebo si profil rovnou stáhněte. Úložiště vlastních profilů má limit 12 KiB a 128 položek. Importní balíček Hubu obsahuje také navržený záznam loggeru a stav ověření. Přiložení surové zprávy je volitelné, protože odhaluje identifikátory zařízení. Soubor importujte do Hubu, zkontrolujte, uložte a poté nastavení výslovně použijte.

**Download ESP32 settings (without passwords)** exportuje názvy sítí, režim a parametry zachytávání i předávání. Hesla k Wi-Fi a správě neobsahuje. Soubor si ponechte jako přehled nastavení; při obnově na vymazanou desku hesla zadejte znovu. OTA zachovává nastavení NVS i profil uložený ve flash.

V pasivním režimu nastavte MAC loggeru a BSSID cílového přístupového bodu. Připnutí ESP32 k přístupovému bodu loggeru pomáhá v mesh sítích: jeho jediné 2,4GHz rádio zachytává kanál stanice a přístupového bodu. Klasický ESP32 neumí zachytávat 5GHz síť. Pokud logger přejde na jiný přístupový bod, změňte cíl nebo zachytávejte nový kanál.

Stažený PCAP obsahuje omezený snímek přibližně 32 KiB. Nejstarší pakety se přepisují a ztráty ve frontě se počítají. Během analýzy ukládejte často, zejména při opětovném připojení loggeru. Chráněné rámce Wi-Fi zůstávají zašifrované. Pro dešifrování WPA2 na počítači obvykle potřebujete klíč Wi-Fi a zachycený handshake. Tento návod nepokrývá dešifrování WPA3. Použijte Wireshark a záznamy uchovejte v soukromí. Viz [návod k dešifrování ve Wiresharku](https://wiki.wireshark.org/HowToDecrypt802.11).

## [ota] Aktualizace OTA a obnova

Stáhněte odpovídající `firmware.bin` pro Companion, ověřte kontrolní součet a otevřete **Firmware update (OTA)**. Nahrajte jeden obraz aplikace a zajistěte stabilní napájení. Přes OTA nenahrávejte `factory.bin`. Aktualizační nástroj ověří přihlášení a údaje obrazu o čipu a produktu; nový obraz aktivuje až po dokončení přenosu.

Během přenosu se zachytávání a předávání pozastaví, takže logger se může znovu připojit. Při chybě nebo přerušení zůstává současná aplikace a provoz se obnoví. Úspěšný přenos restartuje ESP32. Pokud nová aplikace nenastartuje, firmware se automaticky nevrátí ke starší verzi. Nefunkční desku obnovte pomocí BOOT/USB a továrního obrazu.

OTA používá HTTP s přihlášením správce. Obrazy firmwaru nejsou kryptograficky podepsané, proto používejte důvěryhodné obrazy a aktualizujte pouze v důvěryhodné místní síti. Každý, kdo zná heslo správce, může instalovat firmware. Heslo i exportované záznamy uchovejte v soukromí.

## [operations] Zálohování, řešení potíží a omezení

Pro nastavení nebo změnu hesla webového panelu spusťte tyto příkazy v adresáři projektu Compose. Použijte nejméně 8 znaků. Hub ukládá solený otisk do `/data/admin-password.json`, nikoli samotné heslo. Restart aktivuje změnu a ukončí stávající webové relace. Token správce zůstává platný pro obnovení přístupu a API.

```sh
docker compose exec hub solarman-hub password --data-dir /data
docker compose restart hub
```

Při zastavené službě zálohujte celý svazek Hubu `/data`, včetně SQLite, konfigurace, profilů, tokenu a archivů. U připojených adresářů hostitele zachovejte UID/GID `10001`. Pokud chcete data ponechat, nepoužívejte `docker compose down -v`. Konfigurace obsahuje heslo MQTT v čitelné podobě a chrání ji omezená oprávnění souborového systému; odpovědi API heslo skrývají.

Používejte protokoly a počítadla úložiště v rozhraní i příkazy:

```sh
docker compose logs --tail 100 hub
docker compose restart hub
```

Zdravý stav služby znamená, že webový server odpovídá. Cloud a MQTT kontrolujte samostatně. Plný disk, pomalé úložiště nebo zaplněné fronty mohou způsobit mezery v uložených datech, zatímco předávání pokračuje. Počet zahozených měření najdete v počítadlech úložiště.

Pokud data nepřicházejí, zkontrolujte cílovou IP a port, mapování Dockeru, DHCP, povolená sériová čísla a skutečný restart loggeru. Samotný handshake není zpráva s měřením. Pokud nejdou položky dekódovat, ověřte kód profilu, délku, časová razítka a HEX. Staré měření neznamená, že je logger aktuální. U prázdného grafu zkontrolujte období a revizi profilu. Pokud je ESP32 nedostupný, ověřte jeho nastavovací přístupový bod, kanál, výstup USB a napájení.

HTTP rozhraní Hubu i Companionu ponechte v důvěryhodné místní síti nebo VPN. Pro vzdálený přístup k Hubu použijte reverzní proxy HTTPS s `HUB_COOKIE_SECURE=1`. Nezpřístupňujte neautentizovaný přijímač V5 TCP do veřejného internetu. Omezení podle sériového čísla a IP není bezpečným ověřením zařízení.
