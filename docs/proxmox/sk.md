# Nasadenie Proxmox: VM Debian 13 + Docker

**Solarman Hub je nezávislý hobby projekt. Nie je spojený so spoločnosťou SOFAR (SofarSolar).**

[English](en.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

[README](../readme/sk.md) · [Úplná používateľská príručka](../../src/solarman_hub/guides/sk.md)

## Automatická inštalácia VM

Tento príkaz spustite ako **root v Shelli uzla Proxmox**, nie vo VM. Sprievodca vás prevedie jednotlivými krokmi. Pred potvrdením skontrolujte súhrn.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Zadajte adresu IPv4 s maskou (napríklad `192.168.1.50/24` alebo `192.168.1.50/255.255.255.0`), alebo nechajte pole prázdne pre DHCP. Na bránu a DNS sa sprievodca opýta iba pri statickej adrese.

Sprievodca sa opýta na voľné ID VM, názov, úložisko disku, adresárové úložisko pre Cloud-Init snippets, sieťový most/VLAN, DHCP alebo statické IPv4 (adresu/prefix, bránu a DNS), prostriedky, voliteľný súbor verejného SSH kľúča a heslo webového panela s aspoň 8 znakmi. Predvolené nastavenia: Debian 13, 2 vCPU, 2 GB RAM a disk 20 GB. Overí SHA-512 oficiálneho obrazu a do novej VM nainštaluje Docker a existujúci projekt Compose. Podľa potreby pridá typ obsahu snippets do adresárového úložiska; ostatné typy zachová. Existujúce VM nemení.

Inštalácia môže trvať niekoľko minút. Potom otvorte vypísanú adresu `http://VM_IP:8080` a zadajte svoje heslo. Logger, profil, cloud a MQTT nastavíte v paneli; skript logger nemení. Pri DHCP rezervujte adresu VM, pri statickej konfigurácii vyberte voľnú adresu mimo rozsahu DHCP. Údaje konzoly a príkaz pre obnovovací token sú na hostiteľovi v `/root/solarman-hub-VMID-access.txt`, čitateľnom iba pre root. SSH prijíma kľúče, nie heslá. Po 15 minútach čakanie skončí, ale VM beží ďalej a inštalácia sa opakuje každú minútu. Diagnostika: `qm terminal VMID`, potom v Debiane `journalctl -u solarman-hub-install`.

Spolu so zálohou VM uchovajte Cloud-Init snippet. Jeho cestu nájdete v súbore s prístupmi; obsahuje odtlačky hesiel a prípadný verejný kľúč. Pred migráciou alebo obnovou musí byť dostupný na cieľovom uzle. Skript podporuje Proxmox VE 8/9 na amd64, linuxové mosty a adresárové úložisko pre snippets. Konfigurácia má automatické testy, skutočné vytvorenie VM na Proxmoxe však zatiaľ nebolo overené. Pred spustením si môžete prečítať [zdrojový kód](../../scripts/proxmox-vm.sh).

## Ručná inštalácia

Táto príručka vás prevedie inštaláciou Solarman Hubu vo virtuálnom počítači **Debian 13 (Trixie), amd64** na Proxmoxe. VM vytvorte vo webovom rozhraní Proxmoxu a všetky nasledujúce príkazy spúšťajte **v Debiane**.

## 1. Vytvorte VM

1. Stiahnite [oficiálne ISO Debian netinst amd64](https://www.debian.org/distrib/netinst). V Proxmoxe vyberte uzol → úložisko podporujúce ISO → **ISO Images → Upload**.
2. Kliknite na **Create VM**, pomenujte ju `solarman-hub` a v **OS** vyberte nahrané ISO. Začnite s **2 vCPU, 2048 MB RAM a diskom 20 GB**; ide o odporúčané prostriedky, nie zmerané minimá. Vyberte virtuálny disk v zálohovanom úložisku. Dlhšia história vyžaduje viac miesta.
3. V **Network** vyberte **VirtIO** a existujúci most LAN, zvyčajne `vmbr0`. Použite rovnakú dostupnú LAN/VLAN ako logger; názov mosta a VLAN nie sú na všetkých hostiteľoch rovnaké.
4. Dokončite vytvorenie, spustite VM a otvorte **Console**. Nainštalujte Debian bez grafického prostredia. Vyberte štandardné systémové nástroje; SSH server je voliteľný. Pri inštalácii nastavte heslo root na použitie nižšie uvedenej konzoly root.
5. Po inštalácii odpojte ISO a spustite systém z virtuálneho disku. V VM → **Options** zapnite **Start at boot** a **QEMU Guest Agent**. Po zapnutí agenta VM vypnite a spustite, aby bol dostupný jeho virtuálny kanál; balík agenta sa nainštaluje v ďalšom kroku.
6. Rezervujte adresu VM v DHCP smerovača. Aktuálnu adresu zistíte v Debiane pomocou `hostname -I`. Použite ju všade, kde príručka uvádza `VM_IP`. Líši sa od adresy správy Proxmoxu aj adresy loggera.

Projekt odporúča bežnú VM pre predvídateľnú prevádzku Dockeru a zálohu a obnovu celej VM. Docker v LXC vyžaduje ďalšiu konfiguráciu hostiteľa a kontajnera; nejde o tu opísanú cestu pre začiatočníkov. Pozrite [oficiálnu dokumentáciu kontajnerov Proxmox](https://github.com/proxmox/pve-docs/blob/master/pct.adoc).

## 2. Nainštalujte Docker v Debiane

Prihláste sa ako **root** v konzole VM Debian. V novej inštalácii Debian 13 spustite:

```sh
apt update
apt install -y docker.io docker-cli docker-compose docker-buildx git ca-certificates qemu-guest-agent curl
systemctl enable --now docker
systemctl start qemu-guest-agent
docker compose version
docker buildx version
```

Posledné príkazy majú zobraziť verzie Compose **v2** a Buildx. Ide o [balíky Dockeru pre Debian 13](https://packages.debian.org/trixie/docker.io), vrátane [Compose v2](https://packages.debian.org/trixie/docker-compose) a [Buildx](https://packages.debian.org/trixie/docker-buildx); ďalší inštalačný skript nie je potrebný. Nekombinujte ich s balíkmi Docker CE. Ak je Docker CE už nainštalovaný, ponechajte ho a postupujte podľa [oficiálneho návodu pre Debian](https://docs.docker.com/engine/install/debian/) namiesto inštalácie vyššie uvedených balíkov. Debian 12 má iné verzie balíkov; tento postup je pre Debian 13.

## 3. Stiahnite a spustite Hub

```sh
git clone https://github.com/ordigital/solarman-hub.git /opt/solarman-hub
cd /opt/solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
docker compose exec hub solarman-hub token --data-dir /data
```

Prvé zostavenie sťahuje závislosti a môže trvať niekoľko minút. Počkajte, kým `hub` pobeží; jeho stav by mal byť `healthy`. Posledný príkaz vypíše token správcu. Uchovajte ho v tajnosti. Ďalšie príkazy musia používať rovnaký adresár, aby Compose našiel rovnaký projekt a dátový zväzok. Token zostáva rovnaký po reštartoch a aktualizáciách, kým zachováte dátový zväzok.

## 4. Prvé pripojenie a sieť

Otvorte **`http://VM_IP:8080`** na počítači v LAN a prihláste sa tokenom. Pridajte číselné **sériové číslo loggera**, vyberte kompatibilný profil, uložte a použite. Potom nastavte vzdialený TCP cieľ loggera na **`VM_IP:10000`**. Najprv si uložte pôvodné nastavenia serverov. Správanie A/B závisí od firmvéru a po zmene môže byť potrebný reštart; ak správy neprichádzajú, pozrite príručku.

| Spojenie | Cieľ |
|---|---|
| Logger → Hub | IP VM, TCP `10000` |
| Prehliadač → panel | IP VM, TCP `8080` |
| Hub → cloud | Nastavený cloudový hostiteľ a port, predvolený `access3.solarmanpv.com:10000` |
| Hub → MQTT | Hostiteľ/port existujúceho brokera; zvyčajne `1883` alebo jeho TLS port |

VM tiež potrebuje funkčné DNS, správne hodiny a internet na inštaláciu a odovzdávanie do cloudu. MQTT vyžaduje samostatný broker, napríklad používaný Home Assistantom; tento súbor Compose broker nevytvára. Zapnite integráciu MQTT v HA a nastavte rovnaký broker v Hube.

Ak je zapnutý firewall Proxmoxu, hosťa alebo smerovača, povoľte príslušnú prevádzku z loggera a správcovskej LAN. Porty zverejnené Dockerom môžu obísť pravidlá UFW hosťa; obmedzenia použite na hranici Proxmoxu/smerovača alebo pomocou dokumentovaného firewallového mechanizmu Dockeru. Nepresmerujte porty Hubu z internetu. Pri vyššie uvedenom moste LAN nie je nutné presmerovanie portov hostiteľa Proxmoxu. Použite IP VM, nie súkromnú Docker IP kontajnera.

Ak chcete zachovať alternatívne zverejnené porty pri aktualizáciách, vytvorte pred spustením Hubu `/opt/solarman-hub/.env`:

```dotenv
HUB_WEB_PORT=18080
HUB_LOGGER_PORT=18899
```

Potom znovu spustite `docker compose up -d --wait --wait-timeout 120` a používajte `http://VM_IP:18080` a cieľ loggera `VM_IP:18899`. Predvolené nastavenia načúvania v paneli nemeňte: tieto premenné menia porty sprístupnené Dockerom. Súbor `.env` uchovajte súkromne.

## 5. Overenie a riešenie problémov

Z `/opt/solarman-hub` vnútri VM:

```sh
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail 100 hub
```

Ak ste zmenili zverejnený webový port, nahraďte `8080`. Funkčný HTTP endpoint dokazuje beh služby, nie pripojenie loggera. V paneli samostatne kontrolujte pripojenie loggera, posledné meranie, cloud a MQTT. Merania sa objavia, až povolený logger odošle kompatibilnú správu. Surové logy a exporty uchovávajte súkromne; môžu obsahovať identifikátory zariadení.

Ak `docker compose` chýba, overte Debian 13 a úspešnú inštaláciu `docker-cli` a `docker-compose`. Ak sa `hub` ukončil, pred získaním tokenu skontrolujte jeho logy. Ak sa prehliadač nemôže pripojiť, skontrolujte aktuálnu IP VM, most/VLAN, firewall a zverejnený port. Adresu rezervujte pred nasmerovaním loggera.

## 6. Záloha, aktualizácia a obnova

Pomenovaný zväzok Compose `hub-data`, pripojený v `/data`, ukladá tokeny, nastavenia, profily a históriu v dátovom adresári Dockeru v tejto VM. Opätovné zostavenie kontajnera ho zachová. **Nikdy nespúšťajte `docker compose down -v` ani nemažte tento zväzok, ak chcete zachovať údaje.** Neumiestňujte ho na dočasný súborový systém ani nevylučujte jeho virtuálny disk zo zálohy.

Pre jednoduchú konzistentnú zálohu vyberte VM → **Backup → Backup now**, samostatné záložné úložisko a režim **Stop**. Tým sa VM a zber krátko zastavia; overte, že potom beží. Naplánujte pravidelné zálohy VM v Proxmoxe a vyskúšajte obnovu. Samotná snímka nie je záloha. Zálohy obsahujú prihlasovacie údaje, preto obmedzte prístup. Pozrite [dokumentáciu zálohy a obnovy Proxmox](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

Pred aktualizáciou vytvorte zálohu. Potom vnútri VM:

```sh
cd /opt/solarman-hub
git pull --ff-only
docker compose build --pull hub
docker compose up -d --wait --wait-timeout 120
docker compose ps
```

Tým aktualizujete zdrojový kód a znovu zostavíte miestne inštalovaný obraz; tento postup nepredpokladá zverejnený obraz Hubu. Nahradenie kontajnera krátko preruší odovzdávanie. Pri aktualizácii nemeňte názov ani adresár projektu Compose a nemažte zväzok. Bezpečnostné aktualizácie Debianu a Dockeru sa spravujú zvlášť pomocou APT.

Na obnovu vypnite poškodenú VM a obnovte vybranú úplnú zálohu VM v Proxmoxe. Pri spustení obnovenej kópie ponechajte pôvodnú VM vypnutú, aby nekolidovali IP adresy, relácie loggera a ID klientov MQTT. Overte LAN adresu, stav služby a poslednú prijatú vzorku. Údaje po okamihu zálohy sa stratia; správy miestne potvrdené počas výpadku sa do cloudu automaticky nedoplnia.

## 7. Voliteľné odovzdanie USB pre ESP32

Bežná prevádzka Hubu nepotrebuje ESP32 ani USB. Pre voliteľný nástroj nahrávania pripojte dosku k hostiteľovi Proxmoxu a vyberte VM → **Hardware → Add → USB Device**. Vyberte dosku a odovzdajte ju; podľa potreby reštartujte VM. V Debiane overte skutočnú cestu zariadenia:

```sh
ls -l /dev/serial/by-id/
```

Potom postupujte podľa **ESP32 / Nahranie firmvéru** v paneli Hubu alebo [používateľskej príručky](../../src/solarman_hub/guides/sk.md). USB pripojené iba k počítaču zobrazujúcemu panel nie je VM dostupné. Samotný webový kontajner Hubu nedostáva oprávnenia na USB; nahrávanie vykonáva samostatný jednorazový nástroj Compose. Továrenské nahranie môže resetovať nastavenia dosky.
