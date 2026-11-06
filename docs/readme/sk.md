# Solarman Hub

![Solarman Hub](../images/solarman-hub.png)

**Solarman Hub je nezávislý hobby projekt. Nie je spojený so spoločnosťou SOFAR (SofarSolar).**

[English](../../README.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

Solarman Hub spája váš logger Solarman V5 s cloudom výrobcu a zároveň sprístupňuje merania lokálne. Vo webovom paneli môžete sledovať aktuálne hodnoty a grafy, uchovávať históriu, spravovať dekódovacie profily a pripojiť Home Assistant cez MQTT. Panel aj príručka sú dostupné v deviatich jazykoch.

Zabudovaný profil Sofar HYD G3 / LSW3 dekóduje 48 meraní. Iné formáty potrebujú kompatibilný, nezávisle overený profil. Odovzdávanie pokračuje aj vtedy, keď správu nemožno dekódovať.

## Vyberte inštaláciu

| Prostredie | Začnite tu |
|---|---|
| Linux s Docker Engine a Compose v2 | Rýchly štart nižšie |
| Proxmox VE | [Podrobný návod: VM Debian 13 + Docker](../proxmox/sk.md) |
| Python 3.12+ bez Dockeru | [Používateľská príručka](../../src/solarman_hub/guides/sk.md) |

Pre Proxmox začnite s VM Debian 13, 2 vCPU, 2 GB RAM a diskom 20 GB. Rezervujte jej LAN adresu a zapnite automatický štart. Ak chcete uchovávať dlhšiu históriu, vyhraďte viac miesta.

[Zmena servera loggera: postup krok za krokom vrátane skrytej stránky nastavení.](../../src/solarman_hub/guides/sk.md)

**[Automatická inštalácia VM](../proxmox/sk.md)**

Tento príkaz spustite ako **root v Shelli uzla Proxmox**, nie vo VM. Sprievodca vás prevedie jednotlivými krokmi. Pred potvrdením skontrolujte súhrn.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

## Rýchly štart s Dockerom

Ak sú Docker Engine a Compose v2 už nainštalované:

```sh
git clone https://github.com/ordigital/solarman-hub.git
cd solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose exec hub solarman-hub token --data-dir /data
```

Príkazy Dockeru spúšťajte s dostatočnými právami, prípadne pridajte `sudo`, ak to inštalácia vyžaduje.

Otvorte `http://SERVER_IP:8080` s IP hostiteľa Dockeru alebo VM. Prihláste sa zobrazeným tokenom, pridajte číselné **sériové číslo loggera**, vyberte profil, uložte a použite zmeny. Potom nastavte vzdialený TCP cieľ loggera na rovnakú IP a port `10000`. Nové inštalácie neprijímajú neznáme loggery. Adresa VM sa líši od správcovskej adresy Proxmoxu. Token zostáva rovnaký po reštartoch a aktualizáciách, kým zachováte dátový zväzok.

Konfigurácia, tokeny a história zostávajú vo zväzku Dockeru pripojenom k `/data`. Účet Solarman, cookies ani heslo Wi-Fi nie sú potrebné. MQTT používa adresu a prihlasovacie údaje vášho brokera, nie token API Home Assistant.

Návod na vlastné porty a existujúce inštalácie vytvorené pomocou `docker run` nájdete v príručke.

## Prevádzka a dokumentácia

[Úplná používateľská príručka](../../src/solarman_hub/guides/sk.md) · [Nasadenie Proxmox](../proxmox/sk.md) · [Vývoj](../DEVELOPMENT.md) · [Architektúra](../ARCHITECTURE.md) · [Audit a obmedzenia](../AUDIT.md)

Príručka je dostupná aj v paneli. Opisuje cloudové odovzdávanie, miestne potvrdenia, MQTT, históriu, profily a nastavenie ESP32.

**Správy potvrdené miestne počas výpadku sa neskôr nenahrajú do cloudovej histórie.** Limity úložiska môžu spôsobiť medzery aj v miestnej histórii. Zastavenie Hubu preruší odovzdávanie. Správcovské porty a port loggera ponechajte v dôveryhodnej LAN alebo VPN.

## Voliteľný ESP32 Companion

[Zdroje](../../firmware/esp32-companion) · [Firmvér USB/OTA a kontrolné súčty](../../firmware/esp32-companion/dist)

Companion môže prijímať a odovzdávať správy V5, zachytávať prevádzku Wi-Fi a exportovať dekódovacie profily. Funguje na klasickom ESP32 so 4 MB flash a má anglické rozhranie. ESP32 je voliteľný; Hub funguje aj bez neho.

V Hube otvorte **ESP32 / Nahranie firmvéru**, kde nájdete súbory a pokyny pre USB/OTA. Továrenské nahranie môže resetovať nastavenia dosky. V Proxmoxe najprv odovzdajte USB zariadenie dosky do VM.

Profily vytvorené z neznámych správ treba ručne overiť. Companion nedokáže z ľubovoľných bajtov rozpoznať elektrické merania ani automaticky dešifrovať prevádzku Wi-Fi.

[♡ Buy me a coffee](https://buymeacoffee.com/adamstrad)
