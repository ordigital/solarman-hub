# Guide d’utilisation de Solarman Hub

**Solarman Hub est un projet personnel indépendant, sans affiliation avec SOFAR (SofarSolar).**

Ce guide vous accompagne pour installer le Hub, connecter votre logger et utiliser, si vous le souhaitez, l’ESP32 Companion. La langue choisie dans le Hub s’applique à l’interface et au guide. Le Companion possède sa propre interface en anglais.

## [hub] Utiliser le Hub

Connectez-vous avec votre mot de passe Web ou votre jeton administrateur. Le tableau de bord présente les mesures ainsi que l’état du logger, de la connexion au cloud, de MQTT et du stockage local. Vérifiez la connexion du logger et l’heure de la dernière mesure : un logger connecté n’a pas forcément déjà envoyé un rapport.

Changez la langue à côté de l’indicateur d’actualisation. Le navigateur mémorise votre choix.

Dans **Vue d’ensemble**, sélectionnez un logger, puis **Dernière mesure** ou **Historique**. Les anciennes mesures conservent leurs libellés, unités et révisions de profil d’origine. Cliquez sur le nom d’une mesure pour ouvrir son graphique. Choisissez une période, survolez le graphique ou utilisez le curseur de sélection des points au clavier. Les interruptions de réception apparaissent comme des coupures dans la courbe. Les périodes étendues affichent moins de points tout en préservant les valeurs minimales et maximales.

Dans **Configuration**, enregistrez d’abord vos changements, puis choisissez **Appliquer et reconnecter** pour les activer. Cette action ferme les sessions en cours afin que les loggers se reconnectent avec les nouveaux paramètres. Modifier une adresse ou un port d’écoute nécessite aussi de redémarrer le Hub et d’adapter les correspondances de ports Docker.

La page **Appareils** distingue les informations reçues du logger du fabricant et du modèle indiqués dans son profil. Les informations qui ne sont pas encore arrivées portent la mention « Non reçu ».

## [install] Installation et première connexion

**Installation automatique de la VM**

Exécutez cette commande en tant que **root dans le Shell du nœud Proxmox**, et non dans une VM. L’assistant vous guide étape par étape. Vérifiez le récapitulatif avant de confirmer.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Saisissez une adresse IPv4 avec masque (par exemple `192.168.1.50/24` ou `192.168.1.50/255.255.255.0`), ou laissez le champ vide pour DHCP. La passerelle et les DNS ne sont demandés que pour une adresse statique.

L’assistant demande un identifiant de VM libre, son nom, le stockage du disque, un stockage de type répertoire pour les snippets Cloud-Init, le pont réseau/VLAN, DHCP ou IPv4 statique (adresse/préfixe, passerelle et DNS), les ressources, un éventuel fichier de clé publique SSH et un mot de passe Web d’au moins 8 caractères. Par défaut : Debian 13, 2 vCPU, 2 Go de RAM et 20 Go de disque. Il vérifie la somme SHA-512 de l’image officielle et installe Docker et le projet Compose existant dans la nouvelle VM. Au besoin, il ajoute le type de contenu snippets au stockage choisi sans retirer les autres types. Les VM existantes ne sont pas modifiées.

Docker Compose est la méthode recommandée. Sur Proxmox, exécutez Docker dans une VM Debian. Vous pouvez aussi lancer le Hub directement avec Python 3.12 ou une version ultérieure.

Depuis le répertoire du dépôt :

```sh
docker compose up -d --build
docker compose exec hub solarman-hub token --data-dir /data
```

Ouvrez `http://SERVER_IP:8080` et connectez-vous avec le jeton. Celui-ci est enregistré dans `/data/admin-token.txt` et reste identique après les redémarrages et les mises à jour. Un nouveau jeton n’est créé que si ce fichier manque, par exemple lors d’un démarrage avec un volume de données vide. Le port publié par défaut pour les loggers est `10000/TCP`. Compose ne gère pas un conteneur existant lancé avec `docker run`. Utilisez son nom réel, par exemple :

```sh
docker exec solarman-hub solarman-hub token --data-dir /data
```

D’autres ports sur l’hôte permettent d’éviter les conflits :

```sh
HUB_LOGGER_PORT=18899 HUB_WEB_PORT=18080 docker compose up -d --build
```

Ajoutez le **numéro de série numérique du logger**, et non celui de l’onduleur. Vous pouvez limiter son adresse IP source et la réserver dans le DHCP. Choisissez un profil compatible, enregistrez et appliquez les paramètres. Une installation neuve n’accepte aucun numéro de série inconnu. Configurez la destination TCP distante du logger avec l’IP de l’hôte du Hub et le port publié pour les loggers. La procédure détaillée se trouve plus bas, dans « Rediriger son logger vers un serveur V5 local ».

Pour fonctionner sans Docker :

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/solarman-hub serve --data-dir ./data
# In a second terminal:
.venv/bin/solarman-hub token --data-dir ./data
```

Pour une installation Python permanente, utilisez un gestionnaire de processus. `solarman-hub check-config --data-dir ./data` vérifie la configuration et les références aux profils.

## [cloud] Transfert vers le cloud, ACK locaux et MQTT

La destination cloud par défaut est `access3.solarmanpv.com:10000`. Le Hub transmet les rapports V5 et les réponses du cloud sans les modifier. Il n’a besoin ni du mot de passe Solarman, ni de cookies, ni du mot de passe Wi-Fi. Les trames contiennent toujours des identifiants d’appareils et des métadonnées du protocole : ce sont des données privées de votre installation.

Un ACK indique au logger qu’un rapport a été reçu. Pour les types de rapports pris en charge, le Hub envoie soit l’ACK du cloud, soit un seul ACK local si la connexion au cloud échoue ou dépasse le délai prévu. Il ferme ensuite la session cloud défaillante et ignore les ACK tardifs. Les trames valides mais inconnues peuvent être transmises, sans recevoir d’ACK local. Le trafic circule dans les deux sens, y compris les commandes envoyées par le cloud du fabricant.

Si Internet est indisponible mais que le réseau local fonctionne, les mesures locales et MQTT peuvent continuer. **Les rapports confirmés localement pendant la panne ne sont pas envoyés automatiquement au cloud ensuite. L’historique du cloud peut donc présenter des lacunes.** Arrêter le Hub interrompt le chemin de transfert configuré. Pour revenir à une liaison directe avec le cloud, rétablissez les destinations d’origine du logger.

Pour Home Assistant, connectez les deux applications au même broker MQTT. Dans le Hub, renseignez l’hôte, le port, les éventuels identifiants et les paramètres TLS, puis activez MQTT Discovery. Dans HA, configurez l’intégration MQTT officielle. Aucun jeton API HA n’est nécessaire. Le test du broker vérifie la connexion et l’authentification, mais pas les droits de publication (ACL).

La découverte devient disponible après la première mesure compatible. Les identifiants stables des capteurs reposent sur le numéro de série du logger et l’identifiant du champ. La disponibilité MQTT, l’âge de la dernière mesure et la connexion au cloud sont suivis séparément. Choisissez vous-même les compteurs adaptés au tableau de bord Énergie de HA. Un changement de broker ou de préfixe de sujets peut nécessiter de supprimer les anciens sujets Discovery conservés sur le broker précédent.

## [history] Historique, graphiques et conservation

L’historique des mesures est enregistré dans `/data/history.sqlite3`. Les problèmes de stockage n’arrêtent pas le transfert vers le cloud. Si une ancienne installation possède des archives de mesures JSONL, le Hub les importe une seule fois en arrière-plan tout en continuant à recevoir les nouveaux rapports. Consultez la progression de l’import et les erreurs de stockage dans **Configuration**.

Réglez la **Conservation de l’historique** en jours et la **Taille maximale de l’historique** en Mo. Les deux limites s’appliquent : la première atteinte entraîne la suppression des données les plus anciennes. L’âge est calculé à partir de la réception, afin qu’une horloge d’onduleur incorrecte ne conserve pas des données indéfiniment. Zéro jour désactive uniquement la limite d’âge. Désactiver l’historique arrête les nouvelles écritures sans supprimer les données conservées.

La limite de taille inclut la base et ses fichiers journaux, avec une réserve pour la maintenance de la base. Des écritures temporaires peuvent la dépasser brièvement ; gardez de l’espace libre. Les trames brutes, les archives JSONL et les journaux d’événements ont leurs propres limites. **Réduire la limite de l’historique supprime les données les plus anciennes.** Sauvegardez d’abord celles que vous souhaitez conserver.

Les graphiques utilisent l’heure de mesure si elle est disponible, sinon l’heure de réception. Les révisions de profil restent séparées pour ne pas mélanger des échelles ou unités incompatibles. Les grandes périodes renvoient au plus 1500 points représentatifs. Si la requête dépasse la limite de lecture, il vous est demandé de réduire la période. Une mesure arrivée en retard peut apparaître dans l’historique sans remplacer la valeur en direct la plus récente. Les doublons sont éliminés.

## [devices] Informations sur les appareils et profils de décodage

Le Hub relève le numéro de série du logger et l’IP distante dans la session V5/TCP. Les formats de négociation LSW3 vérifiés peuvent fournir la version du micrologiciel ; le rapport Sofar HYD pris en charge fournit le numéro de série de l’onduleur. Chaque information d’identité décodée indique sa source et sa date d’observation. Le Hub ne déduit pas une adresse MAC d’une connexion TCP et ne tente pas de deviner des champs texte arbitraires.

Le profil Sofar HYD G3 intégré décode 48 champs dans un rapport de 2115 octets. Il a été validé sur une installation HYD 15KTL-3PH/LSW3. Les autres matériels nécessitent une validation indépendante. Un rapport peut avoir le code et la longueur attendus tout en organisant les mesures autrement.

Les profils sont des fichiers JSON déclaratifs : code, longueur de la trame complète, emplacement de l’horodatage et champs. Le décalage zéro correspond au premier octet `A5` de la trame V5 complète. Chaque champ précise son décalage, sa largeur, l’ordre des octets, le signe, l’échelle, l’unité et les classes HA éventuelles. Les références de registres servent de notes ; le Hub ne les utilise pas pour interroger l’onduleur.

Dupliquez un profil intégré pour le modifier. Utilisez l’aperçu HEX et comparez plusieurs rapports à des mesures indépendantes avant d’attribuer un profil. Un autre agencement V5 peut ne demander qu’un profil ; un autre protocole de communication nécessite du code. **Transfert seul** transmet les rapports sans les décoder.

Dans la page des profils, importez un fichier JSON de profil ou un paquet ESP32. Vérifiez le résumé, l’état de vérification et les conflits. L’import enregistre le profil et, si nécessaire, un nouveau logger. Il n’applique pas les paramètres et ne reconfigure pas le logger. Les brouillons de mots bruts contiennent des valeurs non vérifiées, sans unités ni classes d’énergie attribuées.

## [spoofing] Rediriger son logger vers un serveur V5 local

Pour recevoir les rapports localement, remplacez le serveur distant du logger par le Hub ou le Companion. Dans ce guide, « spoofing » désigne simplement l’utilisation de ce serveur local à la place du point d’accès cloud.

En utilisation normale :

```text
Logger → Hub → manufacturer cloud
             ↘ local history and MQTT
```

Pour une analyse temporaire :

```text
Logger → ESP32 Companion → Hub → manufacturer cloud
```

### Changer le serveur distant du logger

Les étapes suivantes concernent un logger LSW3 disposant d’une page cachée de configuration des serveurs. Les noms des menus et le comportement au redémarrage peuvent varier selon le micrologiciel.

1. **Repérez les deux adresses.** Dans la liste des clients DHCP de votre routeur, trouvez l’IP locale du logger et celle du serveur Hub. Par exemple, le logger peut être à l’adresse `192.168.100.205` et le Hub à `192.168.100.50`. Remplacez ces exemples par vos propres adresses et réservez-les toutes les deux. L’adresse du logger ouvre ses paramètres ; celle du Hub reçoit les rapports. Sur Proxmox, utilisez l’adresse de la VM Debian pour le Hub.
2. **Préparez d’abord le Hub.** Ajoutez le numéro de série numérique du logger dans **Configuration**, choisissez un profil compatible, enregistrez, puis sélectionnez **Appliquer et reconnecter**. Pour continuer à recevoir les données dans le cloud, activez le transfert vers le cloud en utilisant la destination cloud d’origine du logger. Vérifiez le port du logger publié par Docker ; la valeur par défaut est `10000/TCP`.
3. **Ouvrez les paramètres du logger lui-même.** Depuis un navigateur sur le même réseau local, ouvrez `http://LOGGER_IP/config_hide.html`. Remplacez `LOGGER_IP` par l’adresse du logger. Connectez-vous avec les identifiants administrateur du logger, et non avec votre compte Solarman ou le jeton du Hub. Sur le logger testé, les identifiants d’usine étaient le nom d’utilisateur `admin` et le mot de passe `admin`. S’ils ne fonctionnent pas, consultez l’étiquette et le manuel du logger, ou utilisez les identifiants fournis par l’installateur. Si le mot de passe a été changé, utilisez le mot de passe actuel. Le formulaire caché est chargé à l’intérieur de cette page. Ouvrir directement `hide_set_edit.html` peut empêcher le chargement ou l’enregistrement des paramètres.
4. **Conservez les deux configurations de serveur.** Avant toute modification, notez tous les paramètres de **Server A Setting** et **Optional Server Setting(B)**, y compris l’adresse IP, le nom de domaine, le port et le type de connexion. Des captures d’écran peuvent être utiles. Gardez ces informations pour pouvoir rétablir une connexion directe au cloud.
5. **Définissez la destination principale.** Dans **Server A Setting**, saisissez l’IP locale du Hub dans **IP address**, videz **Domain name**, indiquez le port du logger publié par le Hub dans **Port** et choisissez **TCP** dans **Connection**. Normalement, A pointe ainsi vers le Hub. Utilisez le port du logger, pas celui de l’interface web `8080`, le port `8899` ou une IP privée de conteneur Docker. Laissez B inchangé dans un premier temps, sauf si votre micrologiciel nécessite la configuration de secours ci-dessous.
6. **Enregistrez chaque formulaire modifié.** A et B possèdent chacun leur bouton **Save**. Enregistrez A, puis B séparément si vous l’avez modifié. Rouvrez les paramètres et vérifiez les valeurs enregistrées.
7. **Redémarrez le logger.** Essayez d’abord sa fonction de redémarrage. Certains micrologiciels conservent l’ancienne session TCP même après une demande de redémarrage depuis l’interface. Si le logger envoie toujours vers l’ancienne destination, redémarrez physiquement le logger seul, et uniquement si ses instructions d’installation indiquent que vous pouvez le faire sans danger. Ne modifiez pas les paramètres de fonctionnement de l’onduleur et ne débranchez pas ses câbles de puissance pour redémarrer le logger.
8. **Vérifiez la réception de vrais rapports.** Dans le Hub, vérifiez que le logger se connecte et que les nouvelles mesures portent des horodatages récents et continuent à s’actualiser. Une connexion seule ne suffit pas. Si le transfert vers le cloud est activé, vérifiez que le Hub reçoit les accusés de réception (ACK) du cloud, puis que de nouvelles mesures apparaissent aussi sur la page cloud du fabricant. Tenez compte de l’intervalle habituel d’envoi du logger.

### Si votre LSW3 a besoin du serveur B en secours

Avec le micrologiciel LSW3 testé, diriger uniquement A vers le Hub n’envoyait pas les rapports de façon fiable. La configuration suivante fonctionnait :

| Paramètre | Serveur A | Serveur B |
|---|---|---|
| Adresse IP | IP locale du Hub | IP locale du Hub |
| Nom de domaine | Vide | Vide |
| Port | `10001`, sans service à l’écoute sur ce port | Port du logger publié par le Hub, généralement `10000` |
| Connexion | TCP | TCP |

A pointe volontairement vers un port local fermé pour que le logger se rabatte sur B. **B est une destination de secours, pas une seconde copie simultanée de chaque rapport.** Assurez-vous qu’aucun service n’écoute sur le port choisi pour A. Enregistrez les deux formulaires séparément, redémarrez le logger et répétez les vérifications des mesures et du cloud décrites plus haut. Ce comportement est propre au micrologiciel testé ; utilisez cette solution si la configuration normale de A ne fonctionne pas.

### Rétablir l’envoi direct vers le cloud

Restaurez tous les paramètres d’origine de A et B, y compris les noms de domaine, les ports et les types de connexion. Enregistrez chaque formulaire et redémarrez uniquement le logger. Vérifiez l’arrivée de nouvelles mesures dans le cloud du fabricant avant d’arrêter le Hub. Les rapports confirmés localement pendant l’interruption ne seront pas ajoutés ensuite à l’historique du cloud.

### Placer le Companion entre le logger et le Hub

Activez une seule destination de transfert sur le Companion : le Hub ou le cloud. N’essayez pas de dupliquer les rapports vers les deux. Pour transmettre au Hub, autorisez d’abord le numéro de série du logger dans celui-ci et utilisez son port TCP publié. Le délai de connexion du Companion à sa destination est de 3 secondes. Le délai d’ACK est réglable de 10 à 120 secondes, avec 30 secondes par défaut. Avec le Hub comme destination, il doit dépasser la durée totale de connexion, d’initialisation et d’attente d’ACK du Hub. Sans destination de transfert, le Companion confirme les trames connues localement ; rien n’est livré au cloud.

Une heure correcte est nécessaire pour les ACK locaux. NTP la fournit normalement. Si le Companion n’a pas encore d’heure valide, l’ouverture de son interface lui transmet aussi l’heure du navigateur. Tant que son horloge n’est pas réglée, il ne confirme pas le rapport pour laisser le logger réessayer.

## [esp32] Installer et configurer l’ESP32 Companion

La version fournie cible un **ESP32 classique avec 4 Mo de mémoire flash**, testé avec la famille ESP32-D0WD-V3. Elle ne convient pas aux ESP32-C3, S2 ou S3. Alimentez la carte de développement par USB ; elle communique en Wi-Fi.

Les images prêtes à installer et leurs sommes de contrôle se trouvent dans `firmware/esp32-companion/dist/` :

- `factory.bin` : première installation USB, avec chargeur de démarrage et table de partitions ;
- `firmware.bin` : image de l’application seule pour OTA ;
- `SHA256SUMS` : empreintes de contrôle d’intégrité.

Utilisez un câble USB capable de transmettre des données. Installez l’outil dans un environnement virtuel et repérez le bon port :

```sh
python3 -m venv .esp-tools
.esp-tools/bin/pip install esptool==5.6.0
.esp-tools/bin/python -m esptool --port /dev/ttyUSB0 flash-id
sha256sum -c firmware/esp32-companion/dist/SHA256SUMS
.esp-tools/bin/python -m esptool --chip esp32 --port /dev/ttyUSB0 write-flash 0x0 firmware/esp32-companion/dist/factory.bin
```

L’accès au port série peut nécessiter l’appartenance au groupe prévu par votre système. Fermez les moniteurs série avant le flashage. Si le passage automatique au chargeur de démarrage échoue, maintenez BOOT au lancement de l’outil, puis relâchez-le une fois la connexion établie. L’image usine peut réinitialiser les paramètres enregistrés ; OTA les préserve.

Vous pouvez aussi utiliser un conteneur ponctuel sur un **hôte Linux avec Docker Engine**. Clonez ou téléchargez ce dépôt et lancez les commandes depuis sa racine. Fermez les moniteurs série, branchez l’ESP32 sur cet hôte Docker et repérez son périphérique série ; `/dev/ttyUSB0` est un exemple :

```sh
ls -l /dev/serial/by-id/
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm --build esp-flash flash-id
ESP_PORT=/dev/ttyUSB0 docker compose --profile tools run --rm esp-flash
```

La première commande Docker construit l’outil et vérifie la puce connectée sans écrire dessus. La seconde vérifie la somme de contrôle de l’image fournie et écrit `factory.bin` à l’adresse `0x0`. Remplacez `ESP_PORT` par le chemin `/dev/ttyUSB…`, `/dev/ttyACM…` ou `/dev/serial/by-id/…` de votre carte. Cet outil ne demande pas d’installation Python sur l’hôte et fonctionne séparément du Hub. Utilisez OTA pour les mises à jour suivantes afin de conserver les paramètres.

L’USB doit être accessible **sur la machine qui exécute le démon Docker**, pas seulement sur l’ordinateur affichant l’interface web. Dans une VM Proxmox, transmettez d’abord le périphérique USB à la VM. Ces commandes concernent Docker Engine sous Linux. Docker Desktop sous Windows/macOS ne rend pas les ports série accessibles de cette façon par défaut. Sur ces systèmes, utilisez esptool en natif comme indiqué plus haut ou configurez explicitement la transmission USB.

Après connexion, la page **ESP32 / Flashage** du Hub propose aussi **Micrologiciel pour la première installation USB**, **Micrologiciel pour une mise à jour OTA** et **Sommes de contrôle SHA-256**. L’interface télécharge des fichiers ; elle ne programme pas la carte branchée à l’ordinateur du navigateur.

Lisez la sortie série USB à **115200 bauds**. Au démarrage, elle affiche un SSID et un mot de passe de configuration uniques, ainsi que le compte administrateur `admin` avec son mot de passe unique. Connectez-vous au point d’accès de configuration et ouvrez `http://192.168.4.1`. Saisissez les identifiants administrateur dans la demande du navigateur. Renseignez le SSID et le mot de passe de votre réseau domestique, puis enregistrez. La carte redémarre ; retrouvez son IP locale dans la sortie USB ou le DHCP, ou essayez `http://solarman-companion.local`.

Le mode récepteur écoute sur `10000/TCP`. Définissez le numéro de série autorisé, choisissez éventuellement une destination de transfert et dirigez le logger vers l’IP de l’ESP32. Le récepteur accepte un logger actif, quatre envois en attente et des trames de 4096 octets maximum. Le tampon de trames, le rapport et la capture passive sont en RAM et disparaissent au redémarrage.

Pour compiler les sources, utilisez PlatformIO avec `firmware/esp32-companion/platformio.ini`.

## [export] Exporter des profils, des paramètres et des captures

Dans **Profile builder and exports** du Companion, recevez un rapport, puis chargez la correspondance HYD connue, un brouillon de mots bruts non vérifié ou un profil personnalisé enregistré. Le brouillon expose jusqu’à 64 mots bruts. Déterminez leur sens, l’ordre des octets et l’échelle en comparant plusieurs rapports à des mesures indépendantes. Les valeurs brutes doivent être interprétées manuellement avant de devenir des mesures utilisables.

Modifiez le JSON et enregistrez un profil personnalisé sur la carte, ou téléchargez-le directement. Le stockage des profils est limité à 12 Kio et 128 champs. Un paquet d’import Hub inclut aussi le logger proposé et l’état de vérification. L’ajout du rapport brut est facultatif, car il révèle des identifiants d’appareils. Importez le fichier dans le Hub, vérifiez-le, enregistrez-le, puis appliquez explicitement les paramètres lorsque vous êtes prêt.

**Download ESP32 settings (without passwords)** exporte les noms de réseau, le mode et les paramètres de capture et de transfert, sans les mots de passe Wi-Fi et administrateur. Conservez ce fichier comme référence de configuration. Lors d’une restauration sur une carte effacée, ressaisissez les secrets. OTA conserve les paramètres NVS et le profil enregistré en mémoire flash.

En mode passif, configurez la MAC du logger et le BSSID du point d’accès cible. Fixer l’ESP32 sur le point d’accès du logger facilite la capture dans un réseau maillé : sa seule radio 2,4 GHz suit le canal de la station et du point d’accès. L’ESP32 classique ne peut pas capturer une radio 5 GHz. Si le logger change de point d’accès, modifiez la cible ou capturez le nouveau canal.

Les fichiers PCAP contiennent un instantané limité à environ 32 Kio. Les paquets les plus anciens sont écrasés et les pertes dues à la file d’attente sont comptées. Enregistrez souvent pendant l’analyse, en particulier lors d’une reconnexion du logger. Les trames Wi-Fi protégées restent chiffrées. Pour déchiffrer du WPA2 sur un ordinateur, il faut généralement la clé Wi-Fi et une négociation capturée. Le déchiffrement WPA3 n’est pas couvert ici. Utilisez Wireshark et gardez les captures confidentielles. Consultez le [guide de déchiffrement Wireshark](https://wiki.wireshark.org/HowToDecrypt802.11).

## [ota] Mises à jour OTA et récupération

Téléchargez le `firmware.bin` correspondant au Companion, vérifiez son empreinte et ouvrez **Firmware update (OTA)**. Envoyez une seule image d’application en maintenant une alimentation stable. N’envoyez pas `factory.bin` par OTA. L’outil vérifie votre connexion et les informations de puce et de produit de l’image. La nouvelle image n’est activée qu’après la fin de l’envoi.

La capture et le transfert sont suspendus pendant l’envoi ; le logger peut donc se reconnecter. Un envoi interrompu ou échoué conserve l’application actuelle et reprend le fonctionnement. Après un envoi réussi, l’ESP32 redémarre. Le micrologiciel ne revient pas automatiquement à la version précédente si la nouvelle application ne démarre pas. Récupérez une carte qui ne démarre plus avec BOOT/USB et l’image usine.

OTA utilise HTTP avec une connexion administrateur. Les images ne sont pas signées cryptographiquement : choisissez des images de confiance et mettez à jour uniquement sur un réseau local de confiance. Toute personne disposant du mot de passe administrateur peut installer un micrologiciel. Gardez ce mot de passe et les captures exportées confidentiels.

## [operations] Sauvegarde, dépannage et limites

Pour définir ou modifier le mot de passe Web, exécutez ces commandes dans le répertoire du projet Compose. Utilisez au moins 8 caractères. Le Hub conserve une empreinte salée dans `/data/admin-password.json`, pas le mot de passe. Le redémarrage active la modification et ferme les sessions Web existantes. Le jeton administrateur reste valable pour récupérer l’accès et utiliser l’API.

```sh
docker compose exec hub solarman-hub password --data-dir /data
docker compose restart hub
```

Sauvegardez tout le volume `/data` du Hub lorsque le service est arrêté : base SQLite, configuration, profils, jeton et archives. Conservez l’UID/GID `10001` pour les montages de répertoires de l’hôte. N’utilisez pas `docker compose down -v` si vous voulez garder les données. La configuration contient le mot de passe MQTT en clair, protégé par des permissions de fichiers restreintes ; les réponses API le masquent.

Consultez les journaux et les compteurs de stockage de l’interface, ainsi que :

```sh
docker compose logs --tail 100 hub
docker compose restart hub
```

Un service indiqué comme sain signifie que le serveur web répond. Vérifiez séparément le cloud et MQTT. Un disque plein, un stockage lent ou des files saturées peuvent créer des lacunes dans les données enregistrées alors que le transfert continue. Les compteurs de stockage indiquent les mesures perdues.

Si aucune donnée n’arrive, vérifiez l’IP et le port de destination, les correspondances Docker, le DHCP, les numéros de série autorisés et le redémarrage effectif du logger. Une négociation seule n’est pas un rapport de mesures. Si le décodage échoue, vérifiez le code du profil, la longueur, les horodatages et le contenu HEX. Des mesures anciennes ne rendent pas un logger à jour. Si un graphique est vide, vérifiez la période et la révision du profil. Si l’ESP32 est inaccessible, vérifiez son point d’accès de configuration, son canal, sa sortie USB et son alimentation.

Gardez les interfaces HTTP du Hub et du Companion sur un réseau local ou un VPN de confiance. Pour un accès distant au Hub, utilisez un proxy inverse HTTPS avec `HUB_COOKIE_SECURE=1`. N’exposez pas le récepteur TCP V5 sans authentification sur Internet. Les restrictions par numéro de série et IP ne constituent pas une authentification sûre de l’appareil.
