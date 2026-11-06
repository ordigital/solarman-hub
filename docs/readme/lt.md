# Solarman Hub

![Solarman Hub](../images/solarman-hub.png)

**„Solarman Hub“ yra nepriklausomas mėgėjiškas projektas. Jis nesusijęs su SOFAR (SofarSolar).**

[English](../../README.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

„Solarman Hub“ prijungia jūsų „Solarman V5“ registratorių prie gamintojo debesijos ir pateikia matavimus vietoje. Žiniatinklio skydelyje galite stebėti dabartinius rodmenis ir diagramas, kaupti istoriją, tvarkyti dekodavimo profilius ir per MQTT prisijungti prie „Home Assistant“. Skydelis ir vadovas prieinami devyniomis kalbomis.

Įtrauktas „Sofar HYD G3 / LSW3“ profilis dekoduoja 48 matavimų laukus. Kitiems formatams reikia suderinamo, nepriklausomai patikrinto profilio. Net ir negalint dekoduoti pranešimo persiuntimas tęsiamas.

## Pasirinkite diegimą

| Aplinka | Pradėkite čia |
|---|---|
| „Linux“ su „Docker Engine“ ir „Compose v2“ | Toliau pateikta greitoji pradžia |
| „Proxmox VE“ | [Nuoseklus „Debian 13“ VM ir „Docker“ vadovas](../proxmox/lt.md) |
| „Python 3.12+“ be „Docker“ | [Naudotojo vadovas](../../src/solarman_hub/guides/lt.md) |

„Proxmox“ aplinkoje pradėkite nuo „Debian 13“ VM su 2 vCPU, 2 GB RAM ir 20 GB disku. Rezervuokite jos LAN adresą ir įjunkite automatinį paleidimą. Ilgesnei istorijai skirkite daugiau vietos diske.

[Registratoriaus serverio keitimas: nuoseklūs veiksmai, įskaitant paslėptą nustatymų puslapį.](../../src/solarman_hub/guides/lt.md)

**[Automatinis VM diegimas](../proxmox/lt.md)**

Šią komandą paleiskite kaip **root Proxmox mazgo Shell aplinkoje**, o ne VM viduje. Vedlys užduos klausimus paeiliui. Prieš patvirtindami patikrinkite suvestinę.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

## Greitoji pradžia su „Docker“

Kai „Docker Engine“ ir „Compose v2“ jau įdiegti:

```sh
git clone https://github.com/ordigital/solarman-hub.git
cd solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose exec hub solarman-hub token --data-dir /data
```

„Docker“ komandas vykdykite turėdami pakankamas teises; jei dieginiui reikia, pridėkite `sudo`.

Atidarykite `http://SERVER_IP:8080`, naudodami „Docker“ kompiuterio arba VM IP. Prisijunkite rodomu prieigos raktu, pridėkite skaitinį **registratoriaus serijos numerį**, pasirinkite profilį, išsaugokite ir pritaikykite. Tada registratoriaus nuotolinį TCP adresą nukreipkite į tą patį kompiuterio IP ir prievadą `10000`. Nauji dieginiai nepriima nežinomų registratorių. VM adresas skiriasi nuo „Proxmox“ valdymo adreso. Prieigos raktas nesikeičia paleidus iš naujo ar atnaujinus, kol išsaugomas duomenų tomas.

Konfigūracija, prieigos raktai ir istorija išlieka „Docker“ tome, prijungtame prie `/data`. „Solarman“ paskyros, slapukų ar „Wi-Fi“ slaptažodžio nereikia. MQTT naudoja jūsų brokerio adresą ir prisijungimo duomenis, ne „Home Assistant“ API raktą.

Apie pasirinktinius prievadus ir esamus `docker run` dieginius skaitykite vadove.

## Naudojimas ir dokumentacija

[Visas naudotojo vadovas](../../src/solarman_hub/guides/lt.md) · [Diegimas „Proxmox“](../proxmox/lt.md) · [Kūrimas](../DEVELOPMENT.md) · [Architektūra](../ARCHITECTURE.md) · [Auditas ir apribojimai](../AUDIT.md)

Vadovas taip pat pasiekiamas skydelyje. Jame aprašomi persiuntimas į debesiją, vietiniai patvirtinimai, MQTT, istorija, profiliai ir ESP32 sąranka.

**Per sutrikimą vietoje patvirtinti pranešimai vėliau į debesijos istoriją neįkeliami.** Saugyklos ribos taip pat gali sukelti vietinės istorijos spragų. Sustabdžius „Hub“ persiuntimas nutrūksta. Valdymo ir registratoriaus prievadus laikykite patikimame LAN arba VPN.

## Pasirenkamas „ESP32 Companion“

[Pirminis kodas](../../firmware/esp32-companion) · [USB/OTA programinė įranga ir kontrolinės sumos](../../firmware/esp32-companion/dist)

„Companion“ gali priimti ir persiųsti V5 pranešimus, fiksuoti „Wi-Fi“ srautą ir eksportuoti dekodavimo profilius. Jis veikia klasikiniame ESP32 su 4 MB „flash“ ir turi anglišką sąsają. ESP32 yra pasirenkamas; „Hub“ veikia ir be jo.

„Hub“ atidarykite **ESP32 / Programinės įrangos įrašymas** — čia rasite programinę įrangą ir USB/OTA instrukcijas. Gamyklinis įrašymas gali atstatyti plokštės nustatymus. „Proxmox“ aplinkoje pirmiausia perduokite plokštės USB įrenginį VM.

Iš nežinomų pranešimų sukurtus profilius reikia patikrinti rankiniu būdu. „Companion“ negali nustatyti elektrinių matavimų iš savavališkų baitų ar automatiškai iššifruoti „Wi-Fi“ srauto.

[♡ Buy me a coffee](https://buymeacoffee.com/adamstrad)
