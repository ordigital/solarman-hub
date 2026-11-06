# Používateľská príručka Solarman Hub

**Solarman Hub je nezávislý hobby projekt. Nie je spojený so spoločnosťou SOFAR (SofarSolar).**

Táto príručka vám pomôže nastaviť Hub, pripojiť logger a prípadne používať ESP32 Companion. Výber jazyka v Hube zmení panel aj príručku. Companion má vlastné anglické rozhranie.

## [hub] Používanie Hubu

Prihláste sa heslom webového panela alebo tokenom správcu. Panel zobrazuje merania a stav loggera, cloudu, MQTT a miestneho úložiska. Skontrolujte spojenie loggera aj čas posledného merania: pripojený logger ešte nemusel odoslať správu.

Jazyk zmeníte vedľa ukazovateľa obnovovania. Prehliadač si váš výber zapamätá.

V **Prehľade** vyberte logger a **Najnovšie meranie** alebo **História**. Historické vzorky zachovávajú pôvodné názvy polí, jednotky a verziu profilu. Kliknutím na názov merania otvoríte časový graf. Vyberte časový rozsah, pohybujte ukazovateľom nad grafom alebo použite posuvník bodov klávesnicou. Výpadky príjmu prerušujú čiaru; zníženie počtu bodov zachováva minimá a maximá.

V **Konfigurácii** najprv uložte zmeny a potom vyberte **Použiť a znova pripojiť**. Aktuálne spojenia sa zatvoria a loggery sa pripoja s novými nastaveniami. Zmena adresy alebo portu načúvania vyžaduje aj reštart Hubu a zodpovedajúce mapovanie portov Dockeru.

**Zariadenia** rozlišujú hodnoty pozorované v rámcoch od výrobcu a modelu uvedených vo vybranom profile. Chýbajúce informácie sú označené ako nezistené. Nastavený model nie je dôkazom automatickej identifikácie hardvéru.

## [install] Inštalácia a prvé pripojenie

**Automatická inštalácia VM**

Tento príkaz spustite ako **root v Shelli uzla Proxmox**, nie vo VM. Sprievodca vás prevedie jednotlivými krokmi. Pred potvrdením skontrolujte súhrn.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Zadajte adresu IPv4 s maskou (napríklad `192.168.1.50/24` alebo `192.168.1.50/255.255.255.0`), alebo nechajte pole prázdne pre DHCP. Na bránu a DNS sa sprievodca opýta iba pri statickej adrese.

Sprievodca sa opýta na voľné ID VM, názov, úložisko disku, adresárové úložisko pre Cloud-Init snippets, sieťový most/VLAN, DHCP alebo statické IPv4 (adresu/prefix, bránu a DNS), prostriedky, voliteľný súbor verejného SSH kľúča a heslo webového panela s aspoň 8 znakmi. Predvolené nastavenia: Debian 13, 2 vCPU, 2 GB RAM a disk 20 GB. Overí SHA-512 oficiálneho obrazu a do novej VM nainštaluje Docker a existujúci projekt Compose. Podľa potreby pridá typ obsahu snippets do adresárového úložiska; ostatné typy zachová. Existujúce VM nemení.

Použite Docker Compose. Na Proxmoxe je jednoduchým riešením malý virtuálny počítač Debian s Dockerom; neinštalujte aplikáciu priamo na hypervízor. Aplikácia funguje aj v Pythone 3.12 alebo novšom.

V adresári repozitára:

```sh
docker compose up -d --build
docker compose exec hub solarman-hub token --data-dir /data
```

Otvorte `http://SERVER_IP:8080`. Token je uložený v `/data/admin-token.txt` a zostáva rovnaký po reštartoch a aktualizáciách. Nový sa vytvorí iba vtedy, ak súbor chýba, napríklad pri prázdnom dátovom zväzku. Predvolený zverejnený port loggera je `10000/TCP`. Existujúci kontajner spustený pomocou `docker run` Compose nespravuje: použite jeho skutočný názov, napríklad:

```sh
docker exec solarman-hub solarman-hub token --data-dir /data
```

Alternatívne mapovanie portov hostiteľa zabráni konfliktom:

```sh
HUB_LOGGER_PORT=18899 HUB_WEB_PORT=18080 docker compose up -d --build
```

Pridajte číselné **sériové číslo loggera**, nie meniča. Voliteľne obmedzte zdrojovú IP a rezervujte ju v DHCP. Vyberte kompatibilný dekódovací profil, uložte a použite zmeny. Nová inštalácia neprijíma neznáme sériové čísla loggerov. Vzdialený TCP cieľ loggera nastavte na IP hostiteľa Hubu a zverejnený port loggera. Podrobný postup nájdete nižšie v časti „Presmerovanie vlastného loggera: miestny server V5“.

Pre prevádzku bez Dockeru:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/solarman-hub serve --data-dir ./data
# In a second terminal:
.venv/bin/solarman-hub token --data-dir ./data
```

Pre trvalú inštaláciu Pythonu použite správcu procesov. `solarman-hub check-config --data-dir ./data` overí konfiguráciu a odkazy na profily.

## [cloud] Odovzdávanie do cloudu, miestne ACK a MQTT

Predvolený cloudový cieľ je `access3.solarmanpv.com:10000`. Hub odovzdáva pôvodné bajty V5 a odpovede cloudu. Nepotrebuje heslo účtu Solarman, cookies ani heslo Wi-Fi. Rámce stále obsahujú identifikátory zariadení a metadáta protokolu; ide o súkromné údaje inštalácie.

ACK potvrdzuje loggeru prijatie správy. Pri podporovaných správach Hub odošle buď cloudové ACK, alebo pri výpadku či uplynutí času jedno miestne ACK. Neúspešnú cloudovú reláciu uzavrie a oneskorené ACK ignoruje. Neznáme platné rámce môžu prejsť, ale nedostanú miestne ACK. Prenos funguje oboma smermi vrátane príkazov z cloudu výrobcu.

Ak nefunguje internet, ale LAN áno, miestne merania a MQTT môžu pokračovať. **Správy potvrdené miestne počas výpadku sa neskôr automaticky nenahrajú do cloudu. Cloudová história môže mať medzery.** Zastavenie Hubu preruší nastavenú cestu odovzdávania. Pri návrate k priamej cloudovej službe obnovte pôvodné ciele loggera.

Pre Home Assistant pripojte obe aplikácie k rovnakému brokeru MQTT. V Hube zadajte hostiteľa a port brokera, prípadné meno a heslo a nastavenia TLS; zapnite MQTT Discovery. V HA nastavte oficiálnu integráciu MQTT. Token API HA nie je potrebný. Test brokera kontroluje spojenie a overenie, nie publikačné ACL.

Discovery sa objaví po prvej kompatibilnej vzorke. Stabilné identity senzorov používajú sériové číslo loggera a ID poľa. Dostupnosť MQTT, vek posledného merania loggera a pripojenie ku cloudu sa sledujú samostatne. V energetickom paneli HA sami vyberte vhodné počítadlá energie. Zmena brokera alebo prefixu tém môže vyžadovať odstránenie starých zachovaných tém Discovery na pôvodnom brokeri.

## [history] História, grafy a uchovávanie

História meraní sa ukladá do `/data/history.sqlite3`. Problémy s úložiskom nezastavia odovzdávanie do cloudu. Staršie archívy meraní JSONL sa raz importujú na pozadí aj počas prijímania nových správ. Priebeh a chyby úložiska nájdete v **Konfigurácii**.

Nastavte **Uchovávanie histórie** v dňoch a **Limit veľkosti histórie** v MB. Platia oba; prvý dosiahnutý odstráni najstaršie údaje. Vek sa počíta podľa času príjmu, takže nesprávne hodiny meniča nezachovajú údaje navždy. Nula dní vypne iba limit veku. Vypnutie histórie zastaví nové zápisy, ale nevymaže uloženú históriu.

Limit veľkosti zahŕňa databázu aj jej žurnály a rezervu na údržbu. Dočasné zápisy ho môžu krátko prekročiť, preto nechajte na disku voľné miesto. Surové rámce, archívy JSONL a denníky udalostí majú vlastné limity. **Zníženie limitu histórie vymaže staršie údaje.** Údaje, ktoré chcete zachovať, najprv zálohujte.

Grafy používajú čas vzorky, ak je dostupný, inak čas príjmu. Oddelené verzie profilov bránia kombinácii nekompatibilných mierok alebo jednotiek. Veľké rozsahy vracajú najviac 1500 vybraných bodov; pri prekročení limitu prehľadávania treba rozsah zúžiť. Vzorky mimo poradia sa môžu objaviť v histórii bez nahradenia najnovších aktuálnych údajov. Opakované vzorky sa uložia len raz.

## [devices] Informácie o zariadeniach a dekódovacie profily

Hub z relácie V5/TCP zisťuje sériové číslo loggera a IP druhej strany. Overené formáty nadviazania spojenia LSW3 môžu odhaliť firmvér; podporovaná správa Sofar HYD poskytuje sériové číslo meniča. Každá dekódovaná identifikačná hodnota ukazuje zdroj a čas zistenia. Hub neodvodzuje MAC adresu z TCP spojenia ani neháda ľubovoľné textové polia.

Zabudovaný profil Sofar HYD G3 dekóduje 48 polí zo správy s 2115 bajtmi, overenej na inštalácii HYD 15KTL-3PH/LSW3. Iný hardvér vyžaduje nezávislé overenie. Samotná zhoda kódu a dĺžky nedokazuje významovú kompatibilitu.

Profily sú deklaratívny JSON: kód, dĺžka celého rámca, mapovanie časového údaja a polia. Posun nula je prvý bajt `A5` úplného rámca V5. Polia určujú posun, šírku, poradie bajtov, znamienko, mierku, jednotku a voliteľné triedy HA. Odkaz na register je poznámka, nie pokyn na dotazovanie.

Zabudované profily pred úpravou naklonujte. Pred priradením mapy použite náhľad HEX a porovnajte viac vzoriek s nezávislými meraniami. Iný formát V5 môže vyžadovať len profil; iný prenosový protokol vyžaduje kód. **Iba odovzdávať** odovzdáva bez dekódovania.

Na stránke profilov importujte samostatný profil JSON alebo balík ESP32. Skontrolujte súhrn, stav overenia a konflikty. Import uloží profil a prípadne nový záznam loggera; nepoužije zmeny ani neprekonfiguruje logger. Návrhy surových slov sú výslovne neoverené a nemajú vymyslené jednotky ani energetické triedy.

## [spoofing] Presmerovanie vlastného loggera: miestny server V5

Ak chcete prijímať správy miestne, zmeňte vzdialený server loggera na Hub alebo Companion. „Spoofing“ tu znamená použitie miestneho servera namiesto cloudového.

Bežná prevádzka:

```text
Logger → Hub → manufacturer cloud
             ↘ local history and MQTT
```

Dočasná analýza:

```text
Logger → ESP32 Companion → Hub → manufacturer cloud
```

### Zmena vzdialeného servera loggera

Nasledujúci postup platí pre logger LSW3 so skrytou stránkou nastavení servera. Názvy ponúk a správanie po reštarte sa môžu líšiť podľa firmvéru.

1. **Zistite obe adresy.** V zozname klientov DHCP v smerovači nájdite LAN IP loggera a servera Hub. Napríklad logger môže mať `192.168.100.205` a Hub `192.168.100.50`; príklady nahraďte vlastnými adresami. Obe adresy rezervujte. Adresa loggera otvára jeho nastavenia; na adresu Hubu sa budú odosielať správy. V Proxmoxe použite adresu VM Debianu.
2. **Najprv pripravte Hub.** V **Konfigurácii** pridajte číselné sériové číslo loggera, vyberte kompatibilný profil, uložte a zvoľte **Použiť a znova pripojiť**. Ak chcete zachovať odosielanie do cloudu, zapnite ho s pôvodným cloudovým cieľom loggera. Skontrolujte port loggera zverejnený Dockerom; predvolený je `10000/TCP`.
3. **Otvorte nastavenia loggera.** V prehliadači v rovnakej LAN otvorte `http://LOGGER_IP/config_hide.html` a `LOGGER_IP` nahraďte adresou loggera. Prihláste sa údajmi správcu loggera, nie účtom Solarman ani tokenom Hubu. Ak bolo heslo zmenené, použite aktuálne. Na testovanom loggeri boli výrobné meno a heslo `admin` / `admin`. Ak nefungujú, skontrolujte štítok alebo návod, prípadne sa obráťte na inštalatéra; ak ste heslo zmenili, použite aktuálne. Skrytý formulár sa načítava v tejto stránke; priame otvorenie `hide_set_edit.html` môže zabrániť načítaniu alebo uloženiu nastavení.
4. **Uložte si obe pôvodné konfigurácie.** Pred úpravou zaznamenajte všetky hodnoty v **Server A Setting** a **Optional Server Setting(B)** vrátane IP adresy, názvu domény, portu a typu spojenia. Pomôžu snímky obrazovky. Údaje si odložte na návrat k priamemu cloudovému spojeniu.
5. **Nastavte hlavný cieľ.** V **Server A Setting** zadajte LAN IP Hubu do **IP address**, vymažte **Domain name**, do **Port** zadajte zverejnený port loggera Hubu a v **Connection** vyberte **TCP**. Takto je zvyčajne cieľom A Hub. Použite port loggera, nie port panelu `8080`, port `8899` ani súkromnú IP kontajnera Docker. B zatiaľ nemeňte, pokiaľ firmvér nevyžaduje náhradné nastavenie uvedené nižšie.
6. **Uložte každý zmenený formulár.** A a B majú samostatné tlačidlá **Save**. Uložte A a prípadne zvlášť aj B. Znovu otvorte nastavenia a overte uložené hodnoty.
7. **Reštartujte logger.** Najprv použite jeho možnosť reštartu. Niektorý firmvér ponechá staré TCP spojenie aj po požiadavke z panela. Ak logger stále používa starý cieľ, fyzicky reštartujte iba logger a len keď to jeho inštalačný návod označuje za bezpečné. Nemeňte prevádzkové nastavenia meniča ani neodpájajte jeho napájacie káble.
8. **Skontrolujte skutočné správy.** V Hube overte, že sa logger pripojil a nové merania majú aktuálny čas a priebežne sa obnovujú. Samotné pripojenie nestačí. Ak je zapnuté odovzdávanie do cloudu, overte prijímanie cloudových potvrdení (ACK) a potom aj nové hodnoty na stránke cloudu výrobcu. Počkajte na obvyklý interval odosielania loggera.

### Ak váš LSW3 potrebuje záložný server B

V testovanom firmvéri LSW3 samotné nastavenie A na Hub neposielalo správy spoľahlivo. Fungovalo toto nastavenie:

| Nastavenie | Server A | Server B |
|---|---|---|
| IP address | LAN IP Hubu | LAN IP Hubu |
| Domain name | Prázdne | Prázdne |
| Port | `10001`, bez služby počúvajúcej na tomto porte | Zverejnený port loggera Hubu, zvyčajne `10000` |
| Connection | TCP | TCP |

A zámerne smeruje na uzavretý miestny port, aby logger prešiel na B. **B je záložný cieľ, nie druhá súčasná kópia každej správy.** Uistite sa, že na porte A nič nepočúva. Uložte oba formuláre samostatne, reštartujte logger a zopakujte kontrolu meraní a cloudu. Toto správanie platí pre testovaný firmvér; použite ho, ak bežné nastavenie A nefunguje.

### Návrat k priamemu cloudovému spojeniu

Obnovte úplné pôvodné nastavenia A a B vrátane názvov domén, portov a typov spojenia. Uložte každý formulár a reštartujte iba logger. Pred zastavením Hubu skontrolujte nové merania v cloude výrobcu. Správy miestne potvrdené počas prerušenia sa neskôr do cloudovej histórie nenahrajú.

### Companion medzi loggerom a Hubom

V Companionovi povoľte práve jedno nadradené spojenie: Hub alebo cloud. Nepokúšajte sa posielať kópiu správy do oboch. Pri použití Hubu najprv povoľte sériové číslo loggera a použite zverejnený TCP port Hubu. Limit pripojenia Companiona je 3 sekundy. Nastaviteľný limit ACK je predvolene 30 sekúnd (10–120 sekúnd); pri použití Hubu ho nastavte dlhší než celé pripojenie, inicializácia a čakanie na ACK v Hube. Bez nadradeného spojenia Companion potvrdzuje známe rámce miestne; do cloudu sa nedoručia.

Miestne ACK vyžadujú správny čas. Zvyčajne ho poskytuje NTP; otvorenie rozhrania Companiona poskytne aj čas prehliadača, ak ešte nie je nastavený. Kým čas nie je správny, Companion správu nepotvrdí a logger ju môže odoslať znovu.

## [esp32] Nahranie a konfigurácia ESP32 Companion

Dodané zostavenie je určené pre **klasický ESP32 so 4 MB flash**, testovaný na rodine ESP32-D0WD-V3. Nie je to obraz pre ESP32-C3, S2 ani S3. Vývojovú dosku napájajte cez USB; komunikuje cez Wi-Fi.

Hotové obrazy a kontrolné súčty sú v `firmware/esp32-companion/dist/`:

- `factory.bin`: prvá inštalácia cez USB vrátane bootloadera a tabuľky oddielov;
- `firmware.bin`: samotný obraz aplikácie pre OTA;
- `SHA256SUMS`: kontrolné hashe integrity.

Použite USB kábel podporujúci dáta. Nainštalujte nástroj na nahrávanie vo virtuálnom prostredí a zistite správny port:

```sh
python3 -m venv .esp-tools
.esp-tools/bin/pip install esptool==5.6.0
.esp-tools/bin/python -m esptool --port /dev/ttyUSB0 flash-id
sha256sum -c firmware/esp32-companion/dist/SHA256SUMS
.esp-tools/bin/python -m esptool --chip esp32 --port /dev/ttyUSB0 write-flash 0x0 firmware/esp32-companion/dist/factory.bin
```

Sériový port môže vyžadovať členstvo v systémovej skupine pre prístup k portu. Pred nahrávaním zatvorte sériové monitory. Ak automatický vstup do bootloadera zlyhá, pri spustení nástroja podržte BOOT a po pripojení ho uvoľnite. Továrenské nahranie môže resetovať uložené nastavenia; OTA ich zachováva.

Na **hostiteľovi Linux s Docker Engine** môžete alternatívne nahrať firmvér priamo z jednorazového kontajnera. Naklonujte alebo stiahnite tento repozitár a spustite príkazy v jeho koreňovom adresári. Zatvorte sériové monitory, pripojte ESP32 k tomuto hostiteľovi Dockeru a zistite jeho sériové zariadenie; `/dev/ttyUSB0` je príklad:

```sh
ls -l /dev/serial/by-id/
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm --build esp-flash flash-id
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm esp-flash
```

Prvý príkaz zostaví nástroj a skontroluje pripojený čip bez zápisu. Druhý overí kontrolný súčet priloženého obrazu a nahrá `factory.bin` na `0x0`. Nahraďte `ESP_PORT` cestou dosky `/dev/ttyUSB…`, `/dev/ttyACM…` alebo `/dev/serial/by-id/…`. Nástroj nepotrebuje Python na hostiteľovi a beží oddelene od Hubu. Pri ďalších aktualizáciách použite OTA, aby nastavenia zostali zachované.

USB musí byť dostupné **na počítači, kde beží démon Dockeru**, nielen na počítači zobrazujúcom webový panel. Vo virtuálnom počítači Proxmox najprv odovzdajte USB zariadenie tomuto počítaču. Príkaz je určený pre Docker Engine v Linuxe; Docker Desktop vo Windows/macOS takto sériové zariadenia štandardne nesprístupňuje. V týchto systémoch použite vyššie uvedený natívny postup esptool alebo výslovne nastavte odovzdanie USB.

Stránka **ESP32 / Nahranie firmvéru** Hubu po prihlásení ponúka aj **Firmvér na prvú inštaláciu cez USB**, **Firmvér na aktualizáciu OTA** a **Kontrolné súčty SHA-256** na stiahnutie. Webový panel sťahuje súbory; nenahráva ich cez USB port počítača s prehliadačom.

Sériový výstup USB čítajte rýchlosťou **115200 baud**. Výstup pri štarte obsahuje jedinečné SSID a heslo na nastavenie a meno správcu `admin` s jeho jedinečným heslom. Pripojte sa k nastavovaciemu AP a otvorte `http://192.168.4.1`. Vo výzve prehliadača zadajte prihlasovacie údaje správcu. Nastavte domáce SSID a heslo a uložte. Doska sa reštartuje; jej IP v LAN zistite z USB výstupu či DHCP alebo skúste `http://solarman-companion.local`.

Režim prijímača počúva na `10000/TCP`. Nastavte povolené sériové číslo loggera, voliteľne zvoľte nadradené spojenie a nasmerujte logger na IP ESP32. Prijímač podporuje jeden aktívny logger, štyri čakajúce správy a rámce do 4096 bajtov. Vyrovnávacia pamäť rámcov, správa a pasívny záznam sú v RAM a reštartom sa stratia.

Na zostavenie zo zdrojov použite PlatformIO s `firmware/esp32-companion/platformio.ini`.

## [export] Export profilov, nastavení a záznamov

V časti **Profile builder and exports** Companiona prijmite správu a načítajte známu mapu HYD, neoverený návrh surových slov alebo uložený vlastný profil. Návrh sprístupňuje až 64 surových slov; význam, poradie bajtov a mierku určte porovnaním viacerých vzoriek a nezávislých meraní. Firmvér nedokáže automaticky odvodiť elektrický význam zo šifrovaných paketov ani ľubovoľných bajtov.

Upravte JSON a uložte vlastný profil na doske alebo ho priamo stiahnite. Úložisko vlastného profilu je obmedzené na 12 KiB a 128 polí. Stiahnite importný balík Hubu zahŕňajúci navrhnutý záznam loggera a stav overenia. Priloženie surovej vzorky je voliteľné, pretože odhaľuje identifikátory zariadení. Súbor importujte do Hubu, skontrolujte, uložte a keď budete pripravení, výslovne použite nastavenia.

**Download ESP32 settings (without passwords)** exportuje názvy sietí, režim a parametre zachytávania a nadradeného spojenia. Neobsahuje heslá Wi-Fi ani správcu. Uchovajte ho ako referenciu konfigurácie; pri obnove na vymazanej doske zadajte tajné údaje znovu. OTA zachováva nastavenia NVS a profil uložený vo flash.

V pasívnom režime nastavte MAC loggera a BSSID cieľového AP. Pripnutie ESP32 k AP loggera pomáha v sieťach mesh: jeho jediné rádio 2,4 GHz zachytáva kanál stanice a AP. Klasický ESP32 nedokáže zachytávať rádio 5 GHz. Ak logger prejde inde, aktualizujte cieľové AP alebo zachytávajte nový kanál.

Stiahnutý PCAP obsahuje obmedzenú snímku približne 32 KiB; najstaršie pakety sa prepisujú a straty v rade počítajú. Pri analýze ukladajte často, najmä pri opätovnom pripojení loggera. Chránené rámce Wi-Fi zostávajú šifrované. Dešifrovanie WPA2 na počítači všeobecne vyžaduje správny kľúč Wi-Fi a vhodne zachytené nadviazanie spojenia; to nie je zárukou pre WPA3. Použite Wireshark a záznam uchovávajte súkromne. Pozrite si [návod na dešifrovanie Wireshark](https://wiki.wireshark.org/HowToDecrypt802.11).

## [ota] Aktualizácie OTA a obnova

Stiahnite správny `firmware.bin` Companiona, overte jeho hash a otvorte **Firmware update (OTA)**. Pri stabilnom napájaní nahrajte jeden obraz aplikácie. Cez OTA nenahrávajte `factory.bin`. Aktualizácia overí prihlásenie a údaje o čipe a produkte a nový obraz aktivuje až po dokončení nahrávania.

Počas nahrávania sa zachytávanie a odovzdávanie pozastaví, takže sa logger môže znovu pripojiť. Neúspešné alebo prerušené nahranie zachová súčasnú aplikáciu a obnoví prevádzku. Úspešné nahranie reštartuje ESP32. Ak sa nová aplikácia nespustí, firmvér sa automaticky nevráti k predchádzajúcej verzii. Dosku obnovte pomocou BOOT/USB a továrenského obrazu.

OTA používa HTTP s prihlásením správcu. Obrazy firmvéru nie sú kryptograficky podpísané, preto používajte dôveryhodné súbory a aktualizujte iba v dôveryhodnej LAN. Každý s heslom správcu môže nainštalovať firmvér. Heslo a exportované záznamy uchovávajte súkromne.

## [operations] Zálohovanie, riešenie problémov a obmedzenia

Na nastavenie alebo zmenu hesla webového panela spustite tieto príkazy v adresári projektu Compose. Použite aspoň 12 znakov. Hub ukladá solený odtlačok do `/data/admin-password.json`, nie samotné heslo. Reštart aktivuje zmenu a ukončí existujúce webové relácie. Token správcu zostáva platný na obnovenie prístupu a API.

```sh
docker compose exec hub solarman-hub password --data-dir /data
docker compose restart hub
```

Pri zastavenej službe zálohujte celý zväzok Hubu `/data`, vrátane SQLite, konfigurácie, profilov, tokenu a archívov. Pri pripojených adresároch zachovajte UID/GID `10001`. Ak chcete údaje uchovať, nepoužívajte `docker compose down -v`. Konfigurácia obsahuje heslo MQTT v otvorenom texte s obmedzenými oprávneniami súborov; odpovede API ho skrývajú.

Použite protokoly a počítadlá úložiska v paneli a tiež:

```sh
docker compose logs --tail 100 hub
docker compose restart hub
```

Stav služby potvrdzuje, že webový server odpovedá; stav cloudu a MQTT skontrolujte samostatne. Plný disk, pomalé úložisko alebo zaplnené rady môžu spôsobiť medzery v záznamoch, aj keď odovzdávanie pokračuje. Počet zahodených vzoriek nájdete v počítadlách úložiska.

Ak údaje neprichádzajú, skontrolujte cieľovú IP a port, mapovanie Dockeru, DHCP, zoznam povolených sériových čísel a skutočný reštart loggera. Samotné nadviazanie spojenia nie je správa s meraním. Ak sa polia nedekódujú, skontrolujte kód profilu, dĺžku, časové údaje a HEX. Staré vzorky nezabezpečia aktuálnosť loggera. Ak je graf prázdny, skontrolujte rozsah a verziu profilu. Ak ESP32 nie je dostupný, skontrolujte jeho nastavovacie AP, kanál, USB výstup a napájanie.

HTTP rozhrania Hubu a Companiona ponechajte v dôveryhodnej LAN alebo VPN. Pre vzdialený prístup k Hubu použite reverznú HTTPS proxy s `HUB_COOKIE_SECURE=1`. Nevystavujte neoverovaný prijímač V5 TCP verejnému internetu. Kontroly sériového čísla a IP sú opatrenia LAN, nie silné overenie zariadenia.
