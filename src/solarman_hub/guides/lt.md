# „Solarman Hub“ naudotojo vadovas

**„Solarman Hub“ yra nepriklausomas mėgėjiškas projektas. Jis nesusijęs su SOFAR (SofarSolar).**

Šis vadovas padės nustatyti „Hub“, prijungti registratorių ir, jei pageidaujate, naudoti „ESP32 Companion“. „Hub“ pasirinkta kalba taikoma skydeliui ir vadovui. „Companion“ turi atskirą anglišką sąsają.

## [hub] Kaip naudoti „Hub“

Prisijunkite žiniatinklio slaptažodžiu arba administratoriaus prieigos raktu. Skydelyje rodomi matavimai ir registratoriaus, debesijos, MQTT bei vietinės saugyklos būsenos. Patikrinkite ir registratoriaus ryšį, ir paskutinio matavimo laiką: prisijungęs registratorius dar gali būti neišsiuntęs pranešimo.

Kalbą pakeiskite šalia atnaujinimo indikatoriaus. Naršyklė įsimins jūsų pasirinkimą.

Dalyje **Apžvalga** pasirinkite registratorių ir **Naujausias matavimas** arba **Istorija**. Istoriniai mėginiai išsaugo pradines laukų etiketes, vienetus ir profilio versiją. Spustelėkite matavimo pavadinimą, kad atidarytumėte laiko diagramą. Pasirinkite laiko intervalą, judinkite žymeklį virš diagramos arba klaviatūra valdykite duomenų taškų slankiklį. Priėmimo spragos nutraukia liniją; mažinant taškų skaičių išsaugomos mažiausios ir didžiausios reikšmės.

Dalyje **Konfigūracija** pirmiausia išsaugokite pakeitimus, tada pasirinkite **Pritaikyti ir prijungti iš naujo**. Dabartiniai seansai uždaromi, kad registratoriai prisijungtų su naujais nustatymais. Pakeitus klausymosi adresą ar prievadą taip pat reikia paleisti „Hub“ iš naujo ir atitinkamai susieti „Docker“ prievadus.

**Įrenginiai** atskiria kadruose nustatytas reikšmes nuo pasirinktame profilyje nurodyto gamintojo ir modelio. Trūkstama informacija rodoma kaip nenustatyta. Nustatytas modelis neįrodo automatinio aparatinės įrangos atpažinimo.

## [install] Diegimas ir pirmasis prisijungimas

**Automatinis VM diegimas**

Šią komandą paleiskite kaip **root Proxmox mazgo Shell aplinkoje**, o ne VM viduje. Vedlys užduos klausimus paeiliui. Prieš patvirtindami patikrinkite suvestinę.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Įveskite IPv4 adresą su kauke (pavyzdžiui, `192.168.1.50/24` arba `192.168.1.50/255.255.255.0`), arba palikite lauką tuščią DHCP. Šliuzo ir DNS klausiama tik pasirinkus statinį adresą.

Vedlys paprašys laisvo VM ID, pavadinimo, disko saugyklos, katalogo tipo saugyklos Cloud-Init snippets failams, tinklo tilto/VLAN, DHCP arba statinio IPv4 (adreso/prefikso, šliuzo ir DNS), išteklių, pasirenkamo viešojo SSH rakto failo ir bent 8 ženklų žiniatinklio slaptažodžio. Numatyta: Debian 13, 2 vCPU, 2 GB RAM ir 20 GB diskas. Jis patikrina oficialaus atvaizdo SHA-512 ir naujoje VM įdiegia Docker bei esamą Compose projektą. Prireikus pasirinktoje katalogo saugykloje įjungia snippets turinio tipą, palikdamas kitus tipus. Esamų VM nekeičia.

Naudokite „Docker Compose“. „Proxmox“ aplinkoje paprastas sprendimas yra nedidelė „Debian“ virtualioji mašina su „Docker“; nediekite programos tiesiai hipervizoriuje. Programa taip pat veikia su „Python 3.12“ arba naujesne versija.

Saugyklos kataloge:

```sh
docker compose up -d --build
docker compose exec hub solarman-hub token --data-dir /data
```

Atidarykite `http://SERVER_IP:8080`. Prieigos raktas saugomas `/data/admin-token.txt` ir nesikeičia paleidus iš naujo ar atnaujinus. Naujas sukuriamas tik trūkstant failo, pavyzdžiui, naudojant tuščią duomenų tomą. Numatytasis paskelbtas registratoriaus prievadas yra `10000/TCP`. Jei naudojate esamą konteinerį, paleistą su `docker run`, „Compose“ jo nevaldo: naudokite tikrąjį pavadinimą, pavyzdžiui:

```sh
docker exec solarman-hub solarman-hub token --data-dir /data
```

Alternatyvus pagrindinio kompiuterio prievadų susiejimas padeda išvengti konfliktų:

```sh
HUB_LOGGER_PORT=18899 HUB_WEB_PORT=18080 docker compose up -d --build
```

Pridėkite skaitinį **registratoriaus serijos numerį**, o ne inverterio numerį. Pasirinktinai apribokite šaltinio IP ir rezervuokite jį DHCP. Pasirinkite suderinamą dekodavimo profilį, išsaugokite ir pritaikykite. Naujas dieginys nepriima nežinomų registratorių serijos numerių. Registratoriaus nuotolinį TCP adresą nustatykite į „Hub“ kompiuterio IP ir paskelbtą registratoriaus prievadą. Išsamūs veiksmai pateikti toliau skyriuje „Savo registratoriaus nukreipimas: vietinis V5 serveris“.

Darbui be „Docker“:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/solarman-hub serve --data-dir ./data
# In a second terminal:
.venv/bin/solarman-hub token --data-dir ./data
```

Nuolatiniam „Python“ dieginiui naudokite procesų prižiūrėtoją. `solarman-hub check-config --data-dir ./data` patikrina konfigūraciją ir nuorodas į profilius.

## [cloud] Persiuntimas į debesiją, vietiniai ACK ir MQTT

Numatytasis debesijos adresas yra `access3.solarmanpv.com:10000`. „Hub“ persiunčia pradinius V5 baitus ir debesijos atsakymus. Jam nereikia „Solarman“ paskyros slaptažodžio, slapukų ar „Wi-Fi“ slaptažodžio. Kadruose vis tiek yra įrenginių identifikatorių ir protokolo metaduomenų; tai privatūs sistemos duomenys.

ACK praneša registratoriui, kad pranešimas gautas. Palaikomiems pranešimams „Hub“ siunčia debesijos ACK arba, ryšiui nutrūkus ar pasibaigus skirtajam laikui, vieną vietinį ACK. Tada uždaromas nepavykęs debesijos seansas, o pavėluoti ACK ignoruojami. Nežinomi galiojantys kadrai gali būti perduoti, bet vietinio ACK negauna. Duomenys keliauja abiem kryptimis, įskaitant gamintojo debesijos komandas.

Nesant interneto, bet veikiant LAN, vietiniai rodmenys ir MQTT gali veikti toliau. **Per sutrikimą vietoje patvirtinti pranešimai vėliau automatiškai į debesiją neįkeliami. Debesijos istorijoje gali būti spragų.** Sustabdžius „Hub“, nustatytas persiuntimo kelias nutrūksta. Grįždami prie tiesioginio debesijos ryšio atkurkite pradinius registratoriaus adresus.

„Home Assistant“ atveju prijunkite abi programas prie to paties MQTT brokerio. „Hub“ įveskite brokerio adresą, prievadą, pasirenkamą naudotojo vardą ir slaptažodį bei TLS nustatymus; įjunkite MQTT Discovery. HA aplinkoje nustatykite oficialią MQTT integraciją. HA API prieigos rakto nereikia. Brokerio testas tikrina ryšį ir tapatybės nustatymą, bet ne publikavimo ACL.

Discovery pasirodo po pirmojo suderinamo mėginio. Pastovioms jutiklių tapatybėms naudojamas registratoriaus serijos numeris ir lauko ID. MQTT prieinamumas, paskutinio registratoriaus matavimo amžius ir debesijos ryšys stebimi atskirai. Tinkamus energijos skaitiklius HA energijos skydelyje pasirinkite patys. Pakeitus brokerį ar temų prefiksą gali reikėti ištrinti senas išsaugotas Discovery temas ankstesniame brokeryje.

## [history] Istorija, diagramos ir saugojimas

Matavimų istorija saugoma `/data/history.sqlite3`. Saugyklos problemos nesustabdo persiuntimo į debesiją. Senesni JSONL matavimų archyvai vieną kartą importuojami fone, toliau priimant naujus pranešimus. Importo eigą ir saugyklos klaidas patikrinkite **Konfigūracijoje**.

Nustatykite **Istorijos saugojimą** dienomis ir **Istorijos dydžio ribą** MB. Galioja abi ribos; pirmoji pasiekta pašalina seniausius duomenis. Amžius skaičiuojamas pagal gavimo laiką, todėl neteisingas inverterio laikrodis neišsaugos duomenų amžinai. Nulis dienų išjungia tik amžiaus ribą. Išjungus istoriją nauji įrašai neberašomi, bet išsaugota istorija neištrinama.

Dydžio riba apima duomenų bazę, jos žurnalus ir techninei priežiūrai rezervuotą vietą. Laikini įrašai gali trumpam ją viršyti, todėl palikite laisvos disko vietos. Neapdoroti kadrai, JSONL archyvai ir įvykių žurnalai turi atskiras ribas. **Sumažinus istorijos ribą senesni duomenys ištrinami.** Norimus išsaugoti duomenis pirmiausia nukopijuokite.

Diagramose naudojamas mėginio laikas, jei jis yra, priešingu atveju — gavimo laikas. Atskiros profilių versijos neleidžia sujungti nesuderinamų mastelių ar vienetų. Dideliems intervalams grąžinama ne daugiau kaip 1500 atrinktų taškų; viršijus nuskaitymo ribą reikia susiaurinti intervalą. Ne eilės tvarka gauti mėginiai gali atsirasti istorijoje nepakeisdami naujausių dabartinių duomenų. Pasikartojantys mėginiai išsaugomi tik vieną kartą.

## [devices] Įrenginių informacija ir dekodavimo profiliai

„Hub“ V5/TCP seanse stebi registratoriaus serijos numerį ir kitos pusės IP. Patikrinti LSW3 ryšio užmezgimo formatai gali atskleisti programinės įrangos versiją; palaikomas „Sofar HYD“ pranešimas pateikia inverterio serijos numerį. Prie kiekvienos dekoduotos tapatybės reikšmės rodoma jos kilmė ir stebėjimo laikas. „Hub“ nenustato MAC adreso pagal TCP ryšį ir nespėja savavališkų teksto laukų.

Integruotas „Sofar HYD G3“ profilis dekoduoja 48 laukus iš 2115 baitų pranešimo, patikrinto „HYD 15KTL-3PH/LSW3“ sistemoje. Kitą įrangą reikia patikrinti nepriklausomai. Vien kodo ir ilgio atitikimas neįrodo semantinio suderinamumo.

Profiliai yra deklaratyvus JSON: kodas, viso kadro ilgis, laiko žymos susiejimas ir laukai. Nulinis poslinkis yra pirmasis viso V5 kadro `A5` baitas. Laukai nurodo poslinkį, plotį, baitų tvarką, ženklą, mastelį, vienetą ir pasirenkamas HA klases. Registro nuoroda yra pastaba, o ne apklausos komanda.

Norėdami redaguoti, nukopijuokite integruotus profilius. Prieš priskirdami žemėlapį naudokite HEX peržiūrą ir palyginkite kelis mėginius su nepriklausomais rodmenimis. Kitam V5 formatui gali pakakti profilio; kitam perdavimo protokolui reikia kodo. **Tik persiųsti** perduoda duomenis nedekoduodamas.

Profilių puslapyje importuokite atskirą JSON profilį arba ESP32 paketą. Patikrinkite santrauką, patikrinimo būseną ir konfliktus. Importas išsaugo profilį ir, kai tinka, naują registratoriaus įrašą; jis nepritaiko pakeitimų ir nekeičia registratoriaus nustatymų. Neapdorotų žodžių juodraščiai aiškiai pažymėti kaip nepatikrinti, juose nėra išgalvotų vienetų ar energijos klasių.

## [spoofing] Savo registratoriaus nukreipimas: vietinis V5 serveris

Norėdami gauti pranešimus vietoje, pakeiskite registratoriaus nuotolinį serverį į „Hub“ arba „Companion“. Šiame vadove „spoofing“ reiškia vietinio serverio naudojimą vietoj debesijos.

Įprastas naudojimas:

```text
Logger → Hub → manufacturer cloud
             ↘ local history and MQTT
```

Laikina analizė:

```text
Logger → ESP32 Companion → Hub → manufacturer cloud
```

### Registratoriaus nuotolinio serverio keitimas

Šie veiksmai skirti LSW3 registratoriui su paslėptu serverio nustatymų puslapiu. Meniu pavadinimai ir paleidimo iš naujo veiksmai gali skirtis priklausomai nuo programinės įrangos.

1. **Raskite abu adresus.** Maršrutizatoriaus DHCP klientų sąraše raskite registratoriaus LAN IP ir „Hub“ serverio LAN IP. Pavyzdžiui, registratoriaus adresas gali būti `192.168.100.205`, o „Hub“ — `192.168.100.50`; pakeiskite juos savaisiais. Rezervuokite abu adresus. Registratoriaus adresu atidaromi jo nustatymai, o „Hub“ adresu siunčiami pranešimai. „Proxmox“ aplinkoje „Hub“ adresas yra „Debian“ VM adresas.
2. **Pirmiausia paruoškite „Hub“.** Dalyje **Konfigūracija** pridėkite skaitinį registratoriaus serijos numerį, pasirinkite suderinamą profilį, išsaugokite ir pasirinkite **Pritaikyti ir prijungti iš naujo**. Jei norite toliau siųsti duomenis į debesiją, įjunkite persiuntimą naudodami pradinį registratoriaus debesijos adresą. Patikrinkite „Docker“ paskelbtą registratoriaus prievadą; numatytasis yra `10000/TCP`.
3. **Atidarykite registratoriaus nustatymus.** Tame pačiame LAN naršyklėje atidarykite `http://LOGGER_IP/config_hide.html`, pakeitę `LOGGER_IP` registratoriaus adresu. Prisijunkite registratoriaus administratoriaus duomenimis, ne „Solarman“ paskyra ar „Hub“ raktu. Jei slaptažodis pakeistas, naudokite dabartinį. Išbandyto registratoriaus gamyklinis naudotojo vardas ir slaptažodis buvo `admin` / `admin`. Jei jie netinka, patikrinkite etiketę ar vadovą arba kreipkitės į montuotoją; jei slaptažodis pakeistas, naudokite dabartinį. Paslėpta nustatymų forma įkeliama šiame puslapyje; tiesiogiai atidarius `hide_set_edit.html` nustatymų gali nepavykti įkelti ar išsaugoti.
4. **Išsaugokite abiejų serverių nustatymus.** Prieš keisdami užsirašykite visas **Server A Setting** ir **Optional Server Setting(B)** reikšmes: IP adresą, domeno pavadinimą, prievadą ir ryšio tipą. Pravers ekrano nuotraukos. Išsaugokite šiuos duomenis, kad galėtumėte atkurti tiesioginį debesijos ryšį.
5. **Nustatykite pagrindinę paskirtį.** Dalyje **Server A Setting** į **IP address** įveskite „Hub“ LAN IP, išvalykite **Domain name**, į **Port** įveskite paskelbtą „Hub“ registratoriaus prievadą, o **Connection** pasirinkite **TCP**. Paprastai taip A nukreipiamas į „Hub“. Naudokite registratoriaus prievadą, ne skydelio `8080`, prievadą `8899` ar privatų „Docker“ konteinerio IP. Iš pradžių B nekeiskite, nebent jūsų programinei įrangai reikėtų toliau aprašyto atsarginio varianto.
6. **Išsaugokite kiekvieną pakeistą formą.** A ir B turi atskirus **Save** mygtukus. Išsaugokite A ir atskirai B, jei jį keitėte. Vėl atidarykite nustatymus ir patikrinkite reikšmes.
7. **Paleiskite registratorių iš naujo.** Pirmiausia naudokite registratoriaus paleidimo iš naujo funkciją. Kai kuri programinė įranga išlaiko seną TCP ryšį net ir po užklausos iš skydelio. Jei vis dar naudojamas senas adresas, fiziškai paleiskite iš naujo tik registratorių ir tik tada, kai jo diegimo instrukcijoje nurodyta, kad tai saugu. Nekeiskite inverterio veikimo nustatymų ir neatjunkite jo maitinimo kabelių.
8. **Patikrinkite tikrus pranešimus.** „Hub“ įsitikinkite, kad registratorius prisijungė, naujų matavimų laikas yra dabartinis ir reikšmės nuolat atnaujinamos. Vien prisijungimo nepakanka. Jei įjungtas persiuntimas į debesiją, patikrinkite, ar „Hub“ gauna debesijos patvirtinimus (ACK), o gamintojo debesijos puslapyje atsiranda naujų rodmenų. Palaukite įprasto registratoriaus siuntimo intervalo.

### Jei jūsų LSW3 reikia atsarginio serverio B

Išbandytoje LSW3 programinėje įrangoje vien A nukreipimas į „Hub“ neužtikrino patikimo siuntimo. Veikė tokia sąranka:

| Nustatymas | Serveris A | Serveris B |
|---|---|---|
| IP address | „Hub“ LAN IP | „Hub“ LAN IP |
| Domain name | Tuščia | Tuščia |
| Port | `10001`, šiame prievade niekas neklauso | Paskelbtas „Hub“ registratoriaus prievadas, paprastai `10000` |
| Connection | TCP | TCP |

A sąmoningai nukreipiamas į uždarytą vietinį prievadą, kad registratorius pereitų prie B. **B yra atsarginė paskirtis, o ne antra vienu metu siunčiama kiekvieno pranešimo kopija.** Įsitikinkite, kad pasirinktame A prievade niekas neklauso. Išsaugokite abi formas atskirai, paleiskite registratorių iš naujo ir pakartokite matavimų bei debesijos patikrą. Tai pastebėta konkrečioje išbandytoje programinėje įrangoje; naudokite, jei įprastas A nustatymas neveikia.

### Grįžimas prie tiesioginio debesijos ryšio

Atkurkite visus pradinius A ir B nustatymus, įskaitant domenus, prievadus ir ryšio tipus. Išsaugokite kiekvieną formą ir paleiskite iš naujo tik registratorių. Prieš sustabdydami „Hub“ patikrinkite naujus matavimus gamintojo debesijoje. Per pertrūkį vietoje patvirtinti pranešimai vėliau į debesijos istoriją neįkeliami.

### „Companion“ tarp registratoriaus ir „Hub“

„Companion“ įjunkite tik vieną aukštesnįjį ryšį: su „Hub“ arba debesija. Nebandykite siųsti kiekvieno pranešimo į abu. Jei naudojate „Hub“, pirmiausia leiskite registratoriaus serijos numerį ir naudokite paskelbtą „Hub“ TCP prievadą. „Companion“ ryšio laiko limitas yra 3 sekundės. Keičiamas ACK laiko limitas pagal numatytuosius nustatymus yra 30 sekundžių (10–120 sekundžių); naudojant „Hub“ jis turi būti ilgesnis už visą „Hub“ prisijungimo, inicijavimo ir ACK laukimo operaciją. Be aukštesniojo ryšio žinomi kadrai patvirtinami vietoje ir į debesiją nepristatomi.

Vietiniams ACK reikia teisingo laiko. Paprastai jį pateikia NTP; atidarius „Companion“ sąsają taip pat perduodamas naršyklės laikas, jei jo dar nėra. Kol laikas nenustatytas, „Companion“ pranešimo nepatvirtina, kad registratorius galėtų bandyti dar kartą.

## [esp32] „ESP32 Companion“ įrašymas ir nustatymas

Pateikta versija skirta **klasikiniam ESP32 su 4 MB „flash“**, išbandytam su ESP32-D0WD-V3 šeima. Tai nėra ESP32-C3, S2 ar S3 atvaizdas. Maitinkite kūrimo plokštę per USB; ji bendrauja per „Wi-Fi“.

Parengti atvaizdai ir kontrolinės sumos yra `firmware/esp32-companion/dist/`:

- `factory.bin`: pirmasis įrašymas per USB su paleidyklės ir skaidinių lentele;
- `firmware.bin`: tik programos atvaizdas OTA atnaujinimui;
- `SHA256SUMS`: vientisumo kontrolinės sumos.

Naudokite duomenis perduodantį USB kabelį. Įdiekite įrašymo įrankį virtualioje aplinkoje ir nustatykite tinkamą prievadą:

```sh
python3 -m venv .esp-tools
.esp-tools/bin/pip install esptool==5.6.0
.esp-tools/bin/python -m esptool --port /dev/ttyUSB0 flash-id
sha256sum -c firmware/esp32-companion/dist/SHA256SUMS
.esp-tools/bin/python -m esptool --chip esp32 --port /dev/ttyUSB0 write-flash 0x0 firmware/esp32-companion/dist/factory.bin
```

Prieigai prie nuosekliojo prievado gali reikėti priklausyti atitinkamai operacinės sistemos grupei. Prieš įrašydami uždarykite nuosekliojo ryšio monitorius. Jei automatinis perėjimas į paleidyklę nepavyksta, paleisdami įrankį laikykite BOOT ir prisijungus atleiskite. Gamyklinis įrašymas gali atstatyti išsaugotus nustatymus; OTA juos išsaugo.

Taip pat **Linux kompiuteryje su Docker Engine** galite įrašyti tiesiai iš vienkartinio konteinerio. Nukopijuokite arba atsisiųskite šią saugyklą ir vykdykite komandas jos pagrindiniame kataloge. Uždarykite nuosekliojo ryšio monitorius, prijunkite ESP32 prie šio „Docker“ kompiuterio ir nustatykite jo nuoseklųjį įrenginį; `/dev/ttyUSB0` yra pavyzdys:

```sh
ls -l /dev/serial/by-id/
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm --build esp-flash flash-id
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm esp-flash
```

Pirmoji komanda sukuria įrankį ir patikrina prijungtą lustą nieko neįrašydama. Antroji patikrina pridėto atvaizdo kontrolinę sumą ir įrašo `factory.bin` adresu `0x0`. Pakeiskite `ESP_PORT` plokštės `/dev/ttyUSB…`, `/dev/ttyACM…` arba `/dev/serial/by-id/…` keliu. Įrankiui nereikia „Python“ pagrindiniame kompiuteryje ir jis veikia atskirai nuo „Hub“. Vėliau naudokite OTA, kad nustatymai išliktų.

USB turi būti prieinamas **kompiuteryje, kuriame veikia „Docker“ demonas**, o ne tik kompiuteryje, kuriame rodomas valdymo skydelis. „Proxmox“ virtualiajai mašinai pirmiausia perduokite USB įrenginį. Ši komanda skirta „Linux Docker Engine“; „Docker Desktop“ sistemoje „Windows“ ar „macOS“ pagal numatytuosius nustatymus taip nepateikia nuosekliųjų įrenginių. Šiose sistemose naudokite pirmiau pateiktas vietines esptool instrukcijas arba aiškiai nustatykite USB perdavimą.

Prisijungus „Hub“ puslapyje **ESP32 / Programinės įrangos įrašymas** taip pat galima atsisiųsti **Programinė įranga pirmajam įrašymui per USB**, **Programinė įranga OTA atnaujinimui** ir **SHA-256 kontrolinės sumos**. Žiniatinklio skydelis atsisiunčia failus; jis neįrašo jų per naršyklės kompiuterio USB prievadą.

USB nuosekliąją išvestį skaitykite **115200 baud** sparta. Paleidimo išvestyje pateikiami unikalūs sąrankos SSID ir slaptažodis bei administratoriaus vardas `admin` su unikaliu slaptažodžiu. Prisijunkite prie sąrankos AP ir atidarykite `http://192.168.4.1`. Naršyklės užklausoje įveskite administratoriaus prisijungimo duomenis. Nustatykite namų SSID ir slaptažodį bei išsaugokite. Plokštė pasileis iš naujo; jos LAN IP raskite USB išvestyje ar DHCP arba bandykite `http://solarman-companion.local`.

Imtuvo režimas klausosi `10000/TCP`. Nustatykite leidžiamą registratoriaus serijos numerį, pasirinktinai pasirinkite serverį ir nukreipkite registratorių į ESP32 IP. Imtuvas palaiko vieną aktyvų registratorių, keturis eilėje laukiančius pranešimus ir iki 4096 baitų kadrus. Kadrų buferis, pranešimas ir pasyvus fiksavimas yra RAM ir dingsta paleidus iš naujo.

Norėdami kurti iš pirminio kodo, naudokite „PlatformIO“ su `firmware/esp32-companion/platformio.ini`.

## [export] Profilių, nustatymų ir įrašų eksportavimas

„Companion“ dalyje **Profile builder and exports** gaukite pranešimą, tada įkelkite žinomą HYD žemėlapį, nepatikrintą neapdorotų žodžių juodraštį arba išsaugotą pasirinktinį profilį. Juodraštis pateikia iki 64 neapdorotų žodžių; jų reikšmę, baitų tvarką ir mastelį nustatykite lygindami kelis mėginius ir nepriklausomus matavimus. Programinė įranga negali automatiškai nustatyti šifruotų paketų ar savavališkų baitų elektrinės reikšmės.

Redaguokite JSON ir išsaugokite pasirinktinį profilį plokštėje arba atsisiųskite jį tiesiogiai. Pasirinktinė saugykla ribojama iki 12 KiB ir 128 laukų. Atsisiųskite „Hub“ importo paketą, kad įtrauktumėte siūlomą registratoriaus įrašą ir patikrinimo būseną. Neapdorotą mėginį įtraukti neprivaloma, nes jis atskleidžia įrenginių identifikatorius. Importuokite failą į „Hub“, patikrinkite, išsaugokite ir pasiruošę aiškiai pritaikykite nustatymus.

**Download ESP32 settings (without passwords)** eksportuoja tinklų pavadinimus, režimą ir fiksavimo bei ryšio su serveriu parametrus. „Wi-Fi“ ir administratoriaus slaptažodžiai neįtraukiami. Saugokite failą kaip konfigūracijos pavyzdį; atkurdami išvalytoje plokštėje slaptažodžius įveskite iš naujo. OTA išsaugo NVS nustatymus ir „flash“ įrašytą profilį.

Pasyviu režimu nustatykite registratoriaus MAC ir tikslinio AP BSSID. ESP32 susiejimas su registratoriaus AP padeda tinkliniuose „mesh“ tinkluose: vienintelis 2,4 GHz radijo modulis fiksuoja stoties ir AP kanalą. Klasikinis ESP32 negali fiksuoti 5 GHz radijo ryšio. Registratoriui perėjus kitur atnaujinkite tikslinį AP arba fiksuokite naują kanalą.

Atsisiųstas PCAP yra ribota maždaug 32 KiB momentinė kopija; seniausi paketai perrašomi, o eilėje atmesti paketai skaičiuojami. Analizės metu dažnai išsaugokite duomenis, ypač registratoriui prisijungiant iš naujo. Apsaugoti „Wi-Fi“ kadrai lieka užšifruoti. WPA2 iššifravimui kompiuteryje paprastai reikia teisingo „Wi-Fi“ rakto ir tinkamai užfiksuoto ryšio užmezgimo; WPA3 atveju tai nežadama. Naudokite „Wireshark“ ir laikykite įrašą privačiai. Žr. [„Wireshark“ iššifravimo vadovą](https://wiki.wireshark.org/HowToDecrypt802.11).

## [ota] OTA atnaujinimai ir atkūrimas

Atsisiųskite tinkamą „Companion“ `firmware.bin`, patikrinkite jo kontrolinę sumą ir atidarykite **Firmware update (OTA)**. Esant stabiliam maitinimui įkelkite vieną programos atvaizdą. Neįkelkite `factory.bin` per OTA. Atnaujinimo įrankis patikrina prisijungimą, lusto ir produkto duomenis, o naują atvaizdą aktyvina tik baigus įkėlimą.

Įkeliant fiksavimas ir persiuntimas sustabdomi, todėl registratorius gali prisijungti iš naujo. Nepavykęs ar nutrūkęs įkėlimas išsaugo dabartinę programą ir atnaujina veikimą. Sėkmingas įkėlimas paleidžia ESP32 iš naujo. Jei nauja programa nepasileidžia, ankstesnė versija automatiškai neatkuriama. Plokštę atkurkite per BOOT/USB su gamykliniu atvaizdu.

OTA naudoja HTTP su administratoriaus prisijungimu. Programinės įrangos atvaizdai nėra kriptografiškai pasirašyti, todėl naudokite patikimus failus ir atnaujinkite tik patikimame LAN. Įrangą gali įdiegti kiekvienas, žinantis administratoriaus slaptažodį. Slaptažodį ir eksportuotus įrašus laikykite privačiai.

## [operations] Atsarginės kopijos, trikčių šalinimas ir ribos

Norėdami nustatyti arba pakeisti žiniatinklio slaptažodį, paleiskite šias komandas Compose projekto kataloge. Naudokite bent 8 ženklų. Hub faile `/data/admin-password.json` saugo maišą su atsitiktine druska, ne patį slaptažodį. Paleidus iš naujo įsigalioja pakeitimas ir baigiami esami žiniatinklio seansai. Administratoriaus prieigos raktas lieka tinkamas prieigai atkurti ir API.

```sh
docker compose exec hub solarman-hub password --data-dir /data
docker compose restart hub
```

Sustabdę paslaugą sukurkite viso „Hub“ tomo `/data` atsarginę kopiją, įskaitant „SQLite“, konfigūraciją, profilius, prieigos raktą ir archyvus. Susietiems katalogams išsaugokite UID/GID `10001`. Norėdami išlaikyti duomenis nenaudokite `docker compose down -v`. Konfigūracijoje MQTT slaptažodis saugomas atviru tekstu su apribotomis failų sistemos teisėmis; API atsakymai jį paslepia.

Naudokite skydelio žurnalus ir saugyklos skaitiklius bei:

```sh
docker compose logs --tail 100 hub
docker compose restart hub
```

Paslaugos būsena rodo, kad žiniatinklio serveris atsako; debesijos ir MQTT būseną patikrinkite atskirai. Pilnas diskas, lėta saugykla ar užpildytos eilės gali sukelti įrašų spragų, nors persiuntimas tęsiamas. Atmestų mėginių skaičių rasite saugyklos skaitikliuose.

Jei duomenys negaunami, patikrinkite paskirties IP ir prievadą, „Docker“ susiejimus, DHCP, leidžiamų serijos numerių sąrašą ir faktinį registratoriaus paleidimą iš naujo. Vien ryšio užmezgimas nėra matavimo pranešimas. Jei laukai nedekoduojami, patikrinkite profilio kodą, ilgį, laiko žymas ir HEX. Seni mėginiai nepadaro registratoriaus duomenų naujais. Jei diagrama tuščia, patikrinkite intervalą ir profilio versiją. Jei ESP32 nepasiekiamas, patikrinkite jo sąrankos AP, kanalą, USB išvestį ir maitinimą.

„Hub“ ir „Companion“ HTTP sąsajas laikykite patikimame LAN arba VPN. Nuotolinei prieigai prie „Hub“ naudokite atvirkštinį HTTPS tarpinį serverį su `HUB_COOKIE_SECURE=1`. Neatidarykite neautentifikuoto V5 TCP imtuvo viešajam internetui. Serijos numerio ir IP patikros yra LAN kontrolės priemonės, o ne stiprus įrenginio tapatybės nustatymas.
