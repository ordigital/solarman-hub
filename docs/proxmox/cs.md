# Instalace na Proxmoxu: VM s Debianem 13 a Dockerem

**Solarman Hub je nezávislý hobby projekt. Není spojen se společností SOFAR (SofarSolar).**

[English](en.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

[README](../readme/cs.md) · [Úplný uživatelský návod](../../src/solarman_hub/guides/cs.md)

## Automatická instalace VM

Tento příkaz spusťte jako **root v Shellu uzlu Proxmox**, nikoli uvnitř VM. Průvodce vás provede jednotlivými kroky. Před potvrzením zkontrolujte souhrn.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Zadejte adresu IPv4 s maskou (například `192.168.1.50/24` nebo `192.168.1.50/255.255.255.0`), nebo ponechte pole prázdné pro DHCP. Na bránu a DNS se průvodce zeptá pouze u statické adresy.

Průvodce se zeptá na volné ID VM, název, úložiště disku, adresářové úložiště pro Cloud-Init snippets, síťový most/VLAN, DHCP nebo statické IPv4 (adresu/prefix, bránu a DNS), prostředky, volitelný soubor veřejného SSH klíče a heslo do webového panelu o nejméně 8 znacích. Výchozí nastavení: Debian 13, 2 vCPU, 2 GB RAM a disk 20 GB. Ověří SHA-512 oficiálního obrazu a do nové VM nainstaluje Docker a stávající projekt Compose. V případě potřeby přidá do adresářového úložiště typ obsahu snippets; ostatní typy zachová. Existující VM nemění.

Instalace může trvat několik minut. Potom otevřete vypsanou adresu `http://VM_IP:8080` a zadejte své heslo. Logger, profil, cloud a MQTT nastavíte v panelu; skript logger nemění. U DHCP rezervujte adresu VM, u statické konfigurace zvolte volnou adresu mimo rozsah DHCP. Údaje konzole a příkaz pro obnovovací token jsou na hostiteli v `/root/solarman-hub-VMID-access.txt`, čitelném pouze pro root. SSH přijímá klíče, nikoli hesla. Po 15 minutách čekání skončí, ale VM běží dál a instalace se opakuje každou minutu. Diagnostika: `qm terminal VMID`, pak v Debianu `journalctl -u solarman-hub-install`.

Spolu se zálohou VM uchovejte Cloud-Init snippet. Jeho cestu najdete v souboru s přístupy; obsahuje otisky hesel a případný veřejný klíč. Před migrací nebo obnovou musí být dostupný na cílovém uzlu. Skript podporuje Proxmox VE 8/9 na amd64, linuxové mosty a adresářové úložiště pro snippets. Konfigurace má automatické testy, skutečné vytvoření VM na Proxmoxu však zatím nebylo ověřeno. Před spuštěním si můžete přečíst [zdrojový kód](../../scripts/proxmox-vm.sh).

## Ruční instalace

Tento návod vás provede instalací Solarman Hubu do virtuálního stroje s **Debianem 13 (Trixie), amd64** na Proxmoxu. VM vytvořte ve webovém rozhraní Proxmoxu. Všechny následující příkazy pak spouštějte **uvnitř Debianu**.

## 1. Vytvoření VM

1. Stáhněte [oficiální ISO Debian netinst amd64](https://www.debian.org/distrib/netinst). V Proxmoxu vyberte uzel → úložiště podporující ISO → **ISO Images → Upload**.
2. Klikněte na **Create VM**, pojmenujte stroj `solarman-hub` a v části **OS** vyberte nahrané ISO. Pro začátek nastavte **2 vCPU, 2048 MB RAM a 20GB disk**. Virtuální disk umístěte na úložiště zahrnuté do záloh. Delší historie potřebuje více místa.
3. V části **Network** zvolte **VirtIO** a stávající síťový most do LAN, obvykle `vmbr0`. Most a VLAN musí loggeru umožnit spojení s VM.
4. Dokončete průvodce, spusťte VM a otevřete **Console**. Nainstalujte Debian bez grafického prostředí. Vyberte standardní systémové nástroje; SSH server je volitelný. Během instalace nastavte heslo uživatele root, abyste mohli použít konzoli podle následujícího postupu.
5. Po instalaci odpojte ISO a spusťte systém z virtuálního disku. V nabídce VM → **Options** zapněte **Start at boot** a **QEMU Guest Agent**. Po zapnutí agenta VM vypněte a znovu spusťte, aby byl dostupný jeho virtuální komunikační kanál. Balíček agenta nainstalujete v dalším kroku.
6. V DHCP nastavení routeru rezervujte adresu VM. Její současnou adresu zjistíte v Debianu příkazem `hostname -I`. Použijte ji všude, kde návod uvádí `VM_IP`. Liší se od adresy správy Proxmoxu i od adresy loggeru.

Virtuální stroj usnadňuje instalaci Dockeru a zálohování celého systému. Docker v LXC vyžaduje další nastavení; pokud zvolíte tuto cestu, podívejte se do [dokumentace kontejnerů Proxmox](https://github.com/proxmox/pve-docs/blob/master/pct.adoc).

## 2. Instalace Dockeru v Debianu

Přihlaste se v konzoli Debian VM jako **root**. Na čerstvé instalaci Debianu 13 spusťte:

```sh
apt update
apt install -y docker.io docker-cli docker-compose docker-buildx git ca-certificates qemu-guest-agent curl
systemctl enable --now docker
systemctl start qemu-guest-agent
docker compose version
docker buildx version
```

Poslední dva příkazy mají vypsat verze Compose **v2** a Buildx. Tento postup používá balíčky Debianu 13 pro [Docker](https://packages.debian.org/trixie/docker.io), [Compose](https://packages.debian.org/trixie/docker-compose) a [Buildx](https://packages.debian.org/trixie/docker-buildx). Pokud už VM používá Docker CE, tyto příkazy přeskočte a řiďte se jeho [návodem pro Debian](https://docs.docker.com/engine/install/debian/). Obě sady balíčků nekombinujte.

## 3. Stažení a spuštění Hubu

```sh
git clone https://github.com/ordigital/solarman-hub.git /opt/solarman-hub
cd /opt/solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
docker compose exec hub solarman-hub token --data-dir /data
```

První sestavení stahuje závislosti a může trvat několik minut. Počkejte, až `hub` poběží a jeho stav bude `healthy`. Poslední příkaz vypíše token správce. Uchovejte ho v soukromí. Dokud zůstane zachovaný datový svazek, token se při restartech ani aktualizacích nemění. Další příkazy spouštějte ze stejného adresáře, aby Compose použil stejný projekt a datový svazek.

## 4. První připojení a síť

Z počítače v místní síti otevřete **`http://VM_IP:8080`** a přihlaste se tokenem. Přidejte číselné **sériové číslo loggeru**, zvolte odpovídající profil, nastavení uložte a použijte. Potom nastavte vzdálený TCP server loggeru na **`VM_IP:10000`**. Původní nastavení serverů si nejdřív poznamenejte. Chování serverů A/B závisí na firmwaru a po změně může být nutný restart. Pokud zprávy nepřicházejí, podívejte se do uživatelského návodu.

| Spojení | Cíl |
|---|---|
| Logger → Hub | IP adresa VM, TCP `10000` |
| Prohlížeč → rozhraní | IP adresa VM, TCP `8080` |
| Hub → cloud | Nastavený cloudový server a port, výchozí `access3.solarmanpv.com:10000` |
| Hub → MQTT | Adresa a port stávajícího brokeru; obvykle `1883` nebo jeho port TLS |

VM potřebuje také funkční DNS, správný čas a přístup k internetu pro instalaci a předávání do cloudu. MQTT vyžaduje samostatný broker, například ten, který už používá Home Assistant. Tento soubor Compose broker nevytváří. Zapněte integraci MQTT v HA a v Hubu nastavte stejný broker.

Pokud je zapnutý firewall v Proxmoxu, ve VM nebo v routeru, povolte potřebný provoz od loggeru a ze sítě pro správu. Porty zveřejněné Dockerem mohou obejít pravidla UFW ve VM. Přístup omezte na Proxmoxu či routeru nebo pomocí postupu pro firewall popsaného v dokumentaci Dockeru. Nezpřístupňujte porty Hubu z internetu. Při výše uvedeném zapojení přes síťový most není potřeba přesměrování portů na hostiteli Proxmoxu. Používejte IP adresu VM, nikoli soukromou adresu kontejneru v Dockeru.

Chcete-li zachovat jiné zveřejněné porty i po aktualizaci, vytvořte před spuštěním Hubu soubor `/opt/solarman-hub/.env`:

```dotenv
HUB_WEB_PORT=18080
HUB_LOGGER_PORT=18899
```

Potom znovu spusťte `docker compose up -d --wait --wait-timeout 120` a používejte `http://VM_IP:18080` a pro logger cíl `VM_IP:18899`. V rozhraní ponechte výchozí nastavení naslouchání: tyto proměnné mění pouze porty zveřejněné Dockerem. Soubor `.env` uchovejte v soukromí.

## 5. Kontrola provozu a řešení potíží

Uvnitř VM v adresáři `/opt/solarman-hub` spusťte:

```sh
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail 100 hub
```

Pokud jste změnili zveřejněný webový port, nahraďte jím `8080`. Úspěšná kontrola znamená, že webový server odpovídá. V rozhraní ještě zkontrolujte připojení loggeru, poslední měření a stav cloudu a MQTT. Měření se zobrazí, jakmile nastavený logger odešle kompatibilní zprávu. Protokoly a exporty mohou obsahovat identifikátory zařízení, proto je uchovejte v soukromí.

Pokud chybí `docker compose`, ověřte, že používáte Debian 13 a že se úspěšně nainstalovaly balíčky `docker-cli` a `docker-compose`. Pokud se `hub` ukončil, před získáním tokenu nejprve přečtěte jeho protokoly. Pokud se prohlížeč nepřipojí, prověřte aktuální IP adresu VM, most/VLAN, firewall a zveřejněný port. Adresu rezervujte dříve, než na ni nasměrujete logger.

## 6. Zálohování, aktualizace a obnova

Pojmenovaný svazek Compose `hub-data`, připojený na `/data`, uchovává tokeny, nastavení, profily a historii v datovém adresáři Dockeru uvnitř VM. Nové sestavení kontejneru ho zachová. **Pokud chcete data ponechat, nikdy nespouštějte `docker compose down -v` ani tento svazek nemažte.** Neukládejte ho na dočasný souborový systém a zahrňte jeho virtuální disk do záloh.

Pro jednoduchou a konzistentní zálohu zvolte VM → **Backup → Backup now**, samostatné zálohovací úložiště a režim **Stop**. VM i sběr dat se krátce zastaví; potom ověřte, že VM opět běží. Naplánujte pravidelné zálohy v Proxmoxu a vyzkoušejte obnovu. Samotný snapshot není záloha. Zálohy obsahují přihlašovací údaje, proto k nim omezte přístup. Viz [dokumentace zálohování a obnovy Proxmoxu](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

Před aktualizací vytvořte zálohu. Poté uvnitř VM spusťte:

```sh
cd /opt/solarman-hub
git pull --ff-only
docker compose build --pull hub
docker compose up -d --wait --wait-timeout 120
docker compose ps
```

Příkazy stáhnou aktuální zdrojové kódy a znovu sestaví Hub. Při výměně kontejneru se předávání krátce přeruší. Zachovejte adresář projektu, název projektu Compose i datový svazek. Bezpečnostní aktualizace Debianu a Dockeru instalujte samostatně přes APT.

Při obnově vypněte nefunkční VM a přes Proxmox obnovte vybranou úplnou zálohu. Původní VM nechte při spuštění obnovené kopie vypnutou, aby nedošlo ke konfliktu IP adres, relací loggeru nebo MQTT klientských ID. Ověřte adresu v LAN, stav služby a poslední přijaté měření. Data vzniklá po záloze se ztratí; zprávy potvrzené místně během výpadku se automaticky do cloudu nedoplní.

## 7. Volitelné předání USB pro ESP32

Běžný provoz Hubu nevyžaduje ESP32 ani USB. Pro volitelný nástroj k nahrání firmwaru připojte desku k hostiteli Proxmoxu a zvolte VM → **Hardware → Add → USB Device**. Vyberte desku a předejte ji do VM; podle potřeby VM restartujte. V Debianu zjistěte skutečnou cestu k zařízení:

```sh
ls -l /dev/serial/by-id/
```

Dále postupujte podle **ESP32 / Nahrání firmwaru** v Hubu nebo podle [uživatelského návodu](../../src/solarman_hub/guides/cs.md). USB připojené pouze k počítači, na kterém zobrazujete rozhraní, není ve VM dostupné. Příkaz pro nahrání firmwaru spustí samostatný nástrojový kontejner. **Nahrání továrního obrazu může resetovat nastavení desky.**
