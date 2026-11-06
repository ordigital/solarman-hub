# Diegimas „Proxmox“: „Debian 13“ VM + „Docker“

**„Solarman Hub“ yra nepriklausomas mėgėjiškas projektas. Jis nesusijęs su SOFAR (SofarSolar).**

[English](en.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

[README](../readme/lt.md) · [Visas naudotojo vadovas](../../src/solarman_hub/guides/lt.md)

## Automatinis VM diegimas

Šią komandą paleiskite kaip **root Proxmox mazgo Shell aplinkoje**, o ne VM viduje. Vedlys užduos klausimus paeiliui. Prieš patvirtindami patikrinkite suvestinę.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Įveskite IPv4 adresą su kauke (pavyzdžiui, `192.168.1.50/24` arba `192.168.1.50/255.255.255.0`), arba palikite lauką tuščią DHCP. Šliuzo ir DNS klausiama tik pasirinkus statinį adresą.

Vedlys paprašys laisvo VM ID, pavadinimo, disko saugyklos, katalogo tipo saugyklos Cloud-Init snippets failams, tinklo tilto/VLAN, DHCP arba statinio IPv4 (adreso/prefikso, šliuzo ir DNS), išteklių, pasirenkamo viešojo SSH rakto failo ir bent 8 ženklų žiniatinklio slaptažodžio. Numatyta: Debian 13, 2 vCPU, 2 GB RAM ir 20 GB diskas. Jis patikrina oficialaus atvaizdo SHA-512 ir naujoje VM įdiegia Docker bei esamą Compose projektą. Prireikus pasirinktoje katalogo saugykloje įjungia snippets turinio tipą, palikdamas kitus tipus. Esamų VM nekeičia.

Diegimas gali užtrukti kelias minutes. Tada atverkite parodytą `http://VM_IP:8080` ir įveskite pasirinktą slaptažodį. Logger, profilį, debesiją ir MQTT nustatysite valdymo skydelyje; scenarijus logger nustatymų nekeičia. Naudodami DHCP rezervuokite VM adresą; statiniam adresui rinkitės laisvą IP už DHCP intervalo ribų. Konsolės duomenys ir prieigos atkūrimo rakto komanda įrašomi Proxmox serveryje į `/root/solarman-hub-VMID-access.txt`, skaitomą tik root. SSH priima raktus, ne slaptažodžius. Po 15 minučių laukimas baigiasi, bet VM veikia toliau, o diegimas kartojamas kas minutę. Diagnostikai naudokite `qm terminal VMID`, o Debian viduje — `journalctl -u solarman-hub-install`.

Kartu su VM atsargine kopija išsaugokite Cloud-Init snippet failą. Jo kelias nurodytas prieigos faile; jame yra slaptažodžių maišos ir galimas viešasis raktas. Prieš perkėlimą ar atkūrimą jis turi būti pasiekiamas paskirties mazge. Scenarijus palaiko Proxmox VE 8/9 su amd64, Linux tiltus ir katalogo tipo snippets saugyklą. Konfigūracija tikrinama automatiniais testais, tačiau tikras VM sukūrimas Proxmox serveryje dar nepatikrintas. Prieš paleisdami galite perskaityti [scenarijaus kodą](../../scripts/proxmox-vm.sh).

## Rankinis diegimas

Šis vadovas padės įdiegti „Solarman Hub“ **Debian 13 (Trixie), amd64** virtualiojoje mašinoje „Proxmox“ aplinkoje. Sukurkite VM „Proxmox“ žiniatinklio sąsajoje, o visas toliau pateiktas komandas vykdykite **„Debian“ viduje**.

## 1. Sukurkite VM

1. Atsisiųskite [oficialų „Debian netinst amd64“ ISO](https://www.debian.org/distrib/netinst). „Proxmox“ pasirinkite mazgą → ISO palaikančią saugyklą → **ISO Images → Upload**.
2. Spustelėkite **Create VM**, pavadinkite ją `solarman-hub` ir dalyje **OS** pasirinkite įkeltą ISO. Pradėkite nuo **2 vCPU, 2048 MB RAM ir 20 GB disko**; tai siūlomi ištekliai, ne išmatuoti minimumai. Pasirinkite virtualų diską saugykloje, kurios atsarginės kopijos daromos. Ilgesnei istorijai reikia daugiau vietos.
3. Dalyje **Network** pasirinkite **VirtIO** ir esamą LAN tiltą, paprastai `vmbr0`. Naudokite tą patį pasiekiamą LAN/VLAN kaip registratorius; tilto pavadinimas ir VLAN skirtinguose kompiuteriuose gali skirtis.
4. Užbaikite kūrimą, paleiskite VM ir atidarykite **Console**. Įdiekite „Debian“ be grafinės aplinkos. Pasirinkite standartines sistemos priemones; SSH serveris pasirenkamas. Diegdami nustatykite root slaptažodį, kad galėtumėte naudoti toliau aprašytą root konsolę.
5. Įdiegę atjunkite ISO ir paleiskite iš virtualaus disko. Dalyje VM → **Options** įjunkite **Start at boot** ir **QEMU Guest Agent**. Įjungę agentą išjunkite ir paleiskite VM, kad būtų pasiekiamas jo virtualus kanalas; agento paketas bus įdiegtas kitame žingsnyje.
6. Rezervuokite VM adresą maršrutizatoriaus DHCP nustatymuose. Dabartinį adresą „Debian“ aplinkoje sužinokite komanda `hostname -I`. Naudokite jį visur, kur vadove nurodyta `VM_IP`. Jis skiriasi nuo „Proxmox“ valdymo ir registratoriaus adresų.

Projektas rekomenduoja įprastą VM dėl nuspėjamo „Docker“ veikimo ir visos VM atsarginio kopijavimo bei atkūrimo. „Docker“ sistemoje LXC reikalauja papildomos kompiuterio ir konteinerio konfigūracijos; tai nėra čia aprašytas pradedančiųjų kelias. Žr. [oficialią „Proxmox“ konteinerių dokumentaciją](https://github.com/proxmox/pve-docs/blob/master/pct.adoc).

## 2. Įdiekite „Docker“ į „Debian“

„Debian“ VM konsolėje prisijunkite kaip **root**. Naujoje „Debian 13“ sistemoje vykdykite:

```sh
apt update
apt install -y docker.io docker-cli docker-compose docker-buildx git ca-certificates qemu-guest-agent curl
systemctl enable --now docker
systemctl start qemu-guest-agent
docker compose version
docker buildx version
```

Paskutinės komandos turi parodyti „Compose“ **v2** ir „Buildx“ versijas. Tai [„Debian 13“ Docker paketai](https://packages.debian.org/trixie/docker.io), įskaitant [Compose v2](https://packages.debian.org/trixie/docker-compose) ir [Buildx](https://packages.debian.org/trixie/docker-buildx); papildomo diegimo scenarijaus nereikia. Nemaišykite jų su „Docker CE“ paketais. Jei „Docker CE“ jau įdiegtas, palikite jį ir vietoj pirmiau nurodytų paketų vadovaukitės [oficialiomis „Debian“ instrukcijomis](https://docs.docker.com/engine/install/debian/). „Debian 12“ paketų versijos kitokios; šis receptas skirtas „Debian 13“.

## 3. Atsisiųskite ir paleiskite „Hub“

```sh
git clone https://github.com/ordigital/solarman-hub.git /opt/solarman-hub
cd /opt/solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
docker compose exec hub solarman-hub token --data-dir /data
```

Pirmasis kūrimas atsisiunčia priklausomybes ir gali užtrukti kelias minutes. Palaukite, kol `hub` veiks; jo būsenos patikra turėtų tapti `healthy`. Paskutinė komanda parodo administratoriaus prieigos raktą. Laikykite jį paslaptyje. Vėlesnes komandas vykdykite tame pačiame kataloge, kad „Compose“ rastų tą patį projektą ir duomenų tomą. Prieigos raktas nesikeičia paleidus iš naujo ar atnaujinus, kol išsaugomas duomenų tomas.

## 4. Pirmasis prisijungimas ir tinklas

LAN kompiuteryje atidarykite **`http://VM_IP:8080`** ir prisijunkite su prieigos raktu. Pridėkite skaitinį **registratoriaus serijos numerį**, pasirinkite suderinamą profilį, išsaugokite ir pritaikykite. Tada registratoriaus nuotolinį TCP adresą nustatykite į **`VM_IP:10000`**. Pirmiausia išsaugokite pradinius serverių nustatymus. Serverių A/B veikimas priklauso nuo programinės įrangos, o po pakeitimo gali reikėti paleisti iš naujo; jei pranešimai negaunami, žr. vadovą.

| Ryšys | Paskirtis |
|---|---|
| Registratorius → Hub | VM IP, TCP `10000` |
| Naršyklė → skydelis | VM IP, TCP `8080` |
| Hub → debesija | Nustatytas debesijos adresas ir prievadas, numatytasis `access3.solarmanpv.com:10000` |
| Hub → MQTT | Jūsų esamo brokerio adresas ir prievadas; paprastai `1883` arba brokerio TLS prievadas |

Diegimui ir persiuntimui į debesiją VM taip pat reikia veikiančio DNS, teisingo laikrodžio ir interneto. MQTT reikia atskiro brokerio, pavyzdžiui, jau naudojamo „Home Assistant“; šis „Compose“ failas brokerio nesukuria. Įjunkite HA MQTT integraciją ir tą patį brokerį nustatykite „Hub“.

Jei įjungta „Proxmox“, svečio ar maršrutizatoriaus užkarda, leiskite tinkamą srautą iš registratoriaus ir valdymo LAN. „Docker“ paskelbti prievadai gali apeiti svečio UFW taisykles; apribojimus taikykite „Proxmox“ ir maršrutizatoriaus riboje arba dokumentuotu „Docker“ užkardos mechanizmu. Nenukreipkite „Hub“ prievadų iš interneto. Naudojant pirmiau aprašytą LAN tiltą „Proxmox“ kompiuterio prievadų persiuntimo nereikia. Naudokite VM IP, o ne privatų konteinerio „Docker“ IP.

Norėdami išlaikyti alternatyvius paskelbtus prievadus po atnaujinimų, prieš paleisdami „Hub“ sukurkite `/opt/solarman-hub/.env`:

```dotenv
HUB_WEB_PORT=18080
HUB_LOGGER_PORT=18899
```

Tada vėl vykdykite `docker compose up -d --wait --wait-timeout 120` ir naudokite `http://VM_IP:18080` bei registratoriaus adresą `VM_IP:18899`. Palikite numatytuosius skydelio klausymosi nustatymus: šie kintamieji keičia „Docker“ atvertus prievadus. `.env` laikykite privačiai.

## 5. Patikra ir trikčių šalinimas

VM viduje iš `/opt/solarman-hub`:

```sh
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail 100 hub
```

Jei paskelbtas žiniatinklio prievadas pakeistas, pakeiskite `8080`. Veikiantis HTTP galinis taškas patvirtina paslaugos veikimą, ne registratoriaus ryšį. Skydelyje atskirai tikrinkite registratoriaus ryšį, paskutinį matavimą, debesiją ir MQTT. Matavimai atsiras tik leidžiamam registratoriui išsiuntus suderinamą pranešimą. Neapdorotus žurnalus ir eksportus laikykite privačiai; juose gali būti įrenginių identifikatorių.

Jei nėra `docker compose`, patikrinkite, ar sistema yra „Debian 13“ ir ar sėkmingai įdiegti `docker-cli` bei `docker-compose`. Jei `hub` sustojo, prieš prašydami prieigos rakto patikrinkite jo žurnalus. Jei naršyklė neprisijungia, patikrinkite dabartinį VM IP, tiltą/VLAN, užkardą ir paskelbtą prievadą. Prieš nukreipdami registratorių rezervuokite adresą.

## 6. Atsarginės kopijos, atnaujinimas ir atkūrimas

Pavadintas „Compose“ tomas `hub-data`, prijungtas prie `/data`, saugo prieigos raktus, nustatymus, profilius ir istoriją šios VM „Docker“ duomenų kataloge. Pakartotinai kuriant konteinerį jis išlieka. **Niekada nevykdykite `docker compose down -v` ir nešalinkite šio tomo, jei norite išsaugoti duomenis.** Nedėkite jo į laikiną failų sistemą ir neišskirkite jo virtualaus disko iš atsarginių kopijų.

Paprastai nuosekliai kopijai pasirinkite VM → **Backup → Backup now**, atskirą kopijų saugyklą ir **Stop** režimą. Tai trumpam sustabdo VM ir duomenų rinkimą; įsitikinkite, kad po to ji veikia. Suplanuokite reguliarias VM kopijas „Proxmox“ ir išbandykite atkūrimą. Vien momentinė kopija nėra atsarginė kopija. Kopijose yra prisijungimo duomenų, todėl apribokite prieigą. Žr. [„Proxmox“ kopijavimo ir atkūrimo dokumentaciją](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

Prieš atnaujindami sukurkite kopiją. Tada VM viduje:

```sh
cd /opt/solarman-hub
git pull --ff-only
docker compose build --pull hub
docker compose up -d --wait --wait-timeout 120
docker compose ps
```

Taip atnaujinamas pirminis kodas ir iš naujo sukuriamas vietoje įdiegtas atvaizdas; ši sąranka nereikalauja paskelbto „Hub“ atvaizdo. Keičiant konteinerį persiuntimas trumpam nutrūksta. Atnaujindami nekeiskite „Compose“ projekto pavadinimo ar katalogo ir nešalinkite tomo. „Debian“ ir „Docker“ saugos atnaujinimai atskirai valdomi per APT.

Norėdami atkurti, išjunkite sugedusią VM ir per „Proxmox“ atkurkite pasirinktą visą VM kopiją. Paleisdami atkurtą kopiją pradinę VM palikite išjungtą, kad nesikirstų IP adresai, registratoriaus seansai ir MQTT klientų ID. Patikrinkite LAN adresą, paslaugos būseną ir paskutinį gautą mėginį. Duomenys po kopijos sukūrimo prarandami; per sutrikimą vietoje patvirtinti pranešimai į debesiją automatiškai nepapildomi.

## 7. Pasirenkamas ESP32 USB perdavimas

Įprastam „Hub“ veikimui ESP32 ar USB nereikia. Norėdami naudoti pasirenkamą įrašymo įrankį, prijunkite plokštę prie „Proxmox“ kompiuterio ir pasirinkite VM → **Hardware → Add → USB Device**. Pasirinkite tą plokštę ir perduokite ją; prireikus paleiskite VM iš naujo. „Debian“ aplinkoje patikrinkite tikrąjį įrenginio kelią:

```sh
ls -l /dev/serial/by-id/
```

Tada vadovaukitės **ESP32 / Programinės įrangos įrašymas** „Hub“ skydelyje arba [naudotojo vadovu](../../src/solarman_hub/guides/lt.md). USB, prijungtas tik prie skydelį rodančio kompiuterio, VM nepasiekiamas. Pats „Hub“ žiniatinklio konteineris USB privilegijų negauna; įrašymą atlieka atskiras vienkartinis „Compose“ įrankis. Gamyklinis įrašymas gali atstatyti plokštės nustatymus.
