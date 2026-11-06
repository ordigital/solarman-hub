# Solarman Hub

![Solarman Hub](../images/solarman-hub.png)

**Solarman Hub je nezávislý hobby projekt. Není spojen se společností SOFAR (SofarSolar).**

[English](../../README.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

Solarman Hub propojí váš logger Solarman V5 s cloudem výrobce a zároveň zpřístupní měření v místní síti. Ve webovém rozhraní můžete sledovat aktuální hodnoty a grafy, uchovávat historii, spravovat dekódovací profily a připojit Home Assistant přes MQTT. Rozhraní i návod jsou k dispozici v devíti jazycích.

Přiložený profil Sofar HYD G3 / LSW3 dekóduje 48 měřených položek. Jiné formáty zpráv potřebují odpovídající, nezávisle ověřený profil. Předávání pokračuje i tehdy, když zprávu nelze dekódovat.

## Vyberte způsob instalace

| Prostředí | Kde začít |
|---|---|
| Linux s Docker Engine a Compose v2 | Rychlý start níže |
| Proxmox VE | [Nastavení VM s Debianem 13 krok za krokem](../proxmox/cs.md) |
| Python 3.12+ bez Dockeru | [Uživatelský návod](../../src/solarman_hub/guides/cs.md) |

Na Proxmoxu začněte s virtuálním strojem s Debianem 13, 2 vCPU, 2 GB RAM a 20GB diskem. Rezervujte mu adresu v místní síti a zapněte automatické spouštění. Pro delší historii počítejte s větším diskem.

**[Automatická instalace VM](../proxmox/cs.md)**

Tento příkaz spusťte jako **root v Shellu uzlu Proxmox**, nikoli uvnitř VM. Průvodce vás provede jednotlivými kroky. Před potvrzením zkontrolujte souhrn.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

## Rychlý start s Dockerem

Pokud už máte nainstalovaný Docker Engine a Compose v2:

```sh
git clone https://github.com/ordigital/solarman-hub.git
cd solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose exec hub solarman-hub token --data-dir /data
```

Vyžaduje-li to vaše instalace, přidejte před příkazy Dockeru `sudo`.

Otevřete `http://SERVER_IP:8080` s adresou hostitele Dockeru nebo VM. Přihlaste se zobrazeným tokenem. Dokud zachováte datový svazek, token se při restartech ani aktualizacích nemění. Přidejte číselné **sériové číslo loggeru**, vyberte odpovídající profil, nastavení uložte a použijte. V loggeru nastavte vzdálený TCP server na stejnou adresu a port `10000`. Připojit se mohou jen nastavené loggery. Na Proxmoxu použijte adresu VM, nikoli adresu správy Proxmoxu.

Nastavení, tokeny a historie se ukládají do svazku Dockeru připojeného na `/data`. Nepotřebujete účet Solarman, cookies ani heslo k Wi-Fi. Pro Home Assistant použijte adresu a přihlašovací údaje svého MQTT brokeru.

V návodu najdete také vlastní porty a postup pro existující instalace spuštěné přes `docker run`.

[Změna serveru loggeru: postup krok za krokem včetně skryté stránky nastavení.](../../src/solarman_hub/guides/cs.md)

## Provoz a dokumentace

[Úplný návod](../../src/solarman_hub/guides/cs.md) · [Instalace na Proxmoxu](../proxmox/cs.md) · [Vývoj](../DEVELOPMENT.md) · [Architektura](../ARCHITECTURE.md) · [Audit a omezení](../AUDIT.md)

Návod je dostupný také přímo v rozhraní. Popisuje předávání do cloudu, místní potvrzování zpráv, MQTT, historii, profily a nastavení ESP32.

**Zprávy potvrzené místně během výpadku se později do cloudové historie neodešlou.** Omezené úložiště může způsobit mezery i v místní historii. Zastavením Hubu přerušíte předávání zpráv. Porty pro správu a loggery zpřístupněte jen v důvěryhodné místní síti nebo VPN.

## Volitelný ESP32 Companion

[Zdrojové kódy](../../firmware/esp32-companion) · [Firmware a kontrolní součty](../../firmware/esp32-companion/dist)

Companion umí přijímat a předávat zprávy V5, zachytávat provoz Wi-Fi a exportovat dekódovací profily. Běží na klasickém ESP32 se 4 MB flash a má anglické rozhraní. ESP32 je volitelný; Hub funguje i bez něj.

V Hubu otevřete **ESP32 / Nahrání firmwaru**, kde najdete soubory ke stažení a postupy pro USB i OTA. Nahrání továrního obrazu může resetovat nastavení desky. Na Proxmoxu nejprve předejte její USB zařízení do VM.

Profily vytvořené z neznámých zpráv je třeba ručně ověřit. Companion nedokáže z libovolných bajtů určit elektrické veličiny ani automaticky dešifrovat provoz Wi-Fi.

[♡ Buy me a coffee](https://buymeacoffee.com/adamstrad)
