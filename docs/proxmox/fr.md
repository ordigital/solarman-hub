# Installation sur Proxmox : VM Debian 13 et Docker

**Solarman Hub est un projet personnel indépendant, sans affiliation avec SOFAR (SofarSolar).**

[English](en.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

[README](../readme/fr.md) · [Guide complet](../../src/solarman_hub/guides/fr.md)

## Installation automatique de la VM

Exécutez cette commande en tant que **root dans le Shell du nœud Proxmox**, et non dans une VM. L’assistant vous guide étape par étape. Vérifiez le récapitulatif avant de confirmer.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

Saisissez une adresse IPv4 avec masque (par exemple `192.168.1.50/24` ou `192.168.1.50/255.255.255.0`), ou laissez le champ vide pour DHCP. La passerelle et les DNS ne sont demandés que pour une adresse statique.

L’assistant demande un identifiant de VM libre, son nom, le stockage du disque, un stockage de type répertoire pour les snippets Cloud-Init, le pont réseau/VLAN, DHCP ou IPv4 statique (adresse/préfixe, passerelle et DNS), les ressources, un éventuel fichier de clé publique SSH et un mot de passe Web d’au moins 8 caractères. Par défaut : Debian 13, 2 vCPU, 2 Go de RAM et 20 Go de disque. Il vérifie la somme SHA-512 de l’image officielle et installe Docker et le projet Compose existant dans la nouvelle VM. Au besoin, il ajoute le type de contenu snippets au stockage choisi sans retirer les autres types. Les VM existantes ne sont pas modifiées.

L’installation peut prendre plusieurs minutes. Ouvrez ensuite l’adresse affichée `http://VM_IP:8080` et saisissez votre mot de passe. Configurez le logger, le profil, le cloud et MQTT dans le panneau ; le script ne modifie pas le logger. Avec DHCP, réservez l’adresse ; en mode statique, choisissez une adresse libre hors de la plage DHCP. Les accès console et la commande du jeton de récupération sont enregistrés sur l’hôte dans `/root/solarman-hub-VMID-access.txt`, lisible uniquement par root. SSH accepte les clés, pas les mots de passe. Après 15 minutes, l’attente se termine mais la VM continue et l’installation réessaie chaque minute. Diagnostic : `qm terminal VMID`, puis dans Debian `journalctl -u solarman-hub-install`.

Conservez le snippet Cloud-Init avec la sauvegarde de la VM. Son emplacement figure dans le fichier d’accès ; il contient des empreintes de mots de passe et, éventuellement, la clé publique. Il doit être présent sur le nœud cible avant migration ou restauration. Le script prend en charge Proxmox VE 8/9 sur amd64, les ponts Linux et les stockages de type répertoire pour les snippets. La configuration dispose de tests automatisés, mais la création réelle d’une VM sur Proxmox n’a pas encore été vérifiée. Vous pouvez consulter [le code du script](../../scripts/proxmox-vm.sh) avant son exécution.

## Installation manuelle

Ce guide explique comment installer Solarman Hub dans une machine virtuelle **Debian 13 (Trixie), amd64** sous Proxmox. Créez la VM dans l’interface web de Proxmox, puis exécutez toutes les commandes ci-dessous **dans Debian**.

## 1. Créer la VM

1. Téléchargez l’[ISO officiel Debian netinst amd64](https://www.debian.org/distrib/netinst). Dans Proxmox, sélectionnez votre nœud → un stockage acceptant les ISO → **ISO Images → Upload**.
2. Cliquez sur **Create VM**, nommez la VM `solarman-hub` et sélectionnez l’ISO dans **OS**. Commencez avec **2 vCPU, 2048 Mo de RAM et un disque de 20 Go**. Placez le disque virtuel sur un stockage inclus dans vos sauvegardes. Un historique plus long demande davantage d’espace.
3. Dans **Network**, choisissez **VirtIO** et votre pont réseau local habituel, généralement `vmbr0`. Le pont et le VLAN doivent permettre au logger de joindre la VM.
4. Terminez l’assistant, démarrez la VM et ouvrez **Console**. Installez Debian sans environnement graphique. Sélectionnez les utilitaires usuels du système ; le serveur SSH est facultatif. Définissez un mot de passe root pendant l’installation pour pouvoir utiliser la console root ci-dessous.
5. Après l’installation, retirez l’ISO et démarrez sur le disque virtuel. Dans VM → **Options**, activez **Start at boot** et **QEMU Guest Agent**. Arrêtez puis démarrez la VM après avoir activé l’agent pour rendre son canal virtuel disponible. Son paquet sera installé à l’étape suivante.
6. Réservez l’adresse de la VM dans les paramètres DHCP du routeur. Dans Debian, `hostname -I` affiche son adresse actuelle. Utilisez-la partout où le guide indique `VM_IP`. Elle est différente de l’adresse d’administration de Proxmox et de celle du logger.

Une VM simplifie l’installation de Docker et la sauvegarde du système complet. Docker dans LXC demande une configuration supplémentaire ; consultez la [documentation Proxmox sur les conteneurs](https://github.com/proxmox/pve-docs/blob/master/pct.adoc) si vous préférez cette solution.

## 2. Installer Docker dans Debian

Connectez-vous en **root** dans la console de la VM Debian. Sur cette installation neuve de Debian 13, exécutez :

```sh
apt update
apt install -y docker.io docker-cli docker-compose docker-buildx git ca-certificates qemu-guest-agent curl
systemctl enable --now docker
systemctl start qemu-guest-agent
docker compose version
docker buildx version
```

Les deux dernières commandes doivent afficher les versions de Compose **v2** et de Buildx. Cette installation utilise les paquets Debian 13 de [Docker](https://packages.debian.org/trixie/docker.io), [Compose](https://packages.debian.org/trixie/docker-compose) et [Buildx](https://packages.debian.org/trixie/docker-buildx). Si Docker CE est déjà installé, ignorez ces commandes et suivez ses [instructions pour Debian](https://docs.docker.com/engine/install/debian/). Ne mélangez pas les deux familles de paquets.

## 3. Télécharger et démarrer le Hub

```sh
git clone https://github.com/ordigital/solarman-hub.git /opt/solarman-hub
cd /opt/solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose ps
docker compose exec hub solarman-hub token --data-dir /data
```

La première construction télécharge les dépendances et peut durer plusieurs minutes. Attendez que `hub` soit en cours d’exécution avec l’état `healthy`. La dernière commande affiche votre jeton administrateur. Gardez-le confidentiel. Il reste identique après les redémarrages et les mises à jour tant que le volume de données est conservé. Exécutez les commandes suivantes depuis ce même répertoire pour que Compose retrouve le même projet et le même volume.

## 4. Première connexion et réseau

Depuis un ordinateur du réseau local, ouvrez **`http://VM_IP:8080`** et connectez-vous avec le jeton. Ajoutez le **numéro de série numérique du logger**, choisissez un profil compatible, puis enregistrez et appliquez les paramètres. Configurez ensuite sa destination TCP distante sur **`VM_IP:10000`**. Notez d’abord ses paramètres de serveur d’origine. Le comportement des serveurs A/B dépend du micrologiciel et un redémarrage peut être nécessaire après le changement. Consultez le guide si aucun rapport n’arrive.

| Connexion | Destination |
|---|---|
| Logger → Hub | IP de la VM, TCP `10000` |
| Navigateur → interface | IP de la VM, TCP `8080` |
| Hub → cloud | Hôte et port configurés, par défaut `access3.solarmanpv.com:10000` |
| Hub → MQTT | Hôte et port de votre broker existant ; généralement `1883` ou son port TLS |

La VM a également besoin d’un DNS fonctionnel, d’une horloge correcte et d’un accès Internet pour l’installation et le transfert vers le cloud. MQTT nécessite un broker séparé, par exemple celui déjà utilisé par Home Assistant : ce fichier Compose n’en crée pas. Activez l’intégration MQTT dans HA et configurez le même broker dans le Hub.

Si un pare-feu est actif sur Proxmox, dans la VM ou sur le routeur, autorisez les connexions nécessaires depuis le logger et le réseau local d’administration. Les ports publiés par Docker peuvent contourner les règles UFW de la VM. Appliquez les restrictions sur Proxmox ou le routeur, ou avec le mécanisme de pare-feu documenté par Docker. N’exposez pas les ports du Hub sur Internet. Avec le pont réseau décrit plus haut, aucune redirection de port depuis l’hôte Proxmox n’est nécessaire. Utilisez l’IP de la VM, pas l’IP privée Docker du conteneur.

Pour conserver d’autres ports publiés lors des mises à jour, créez `/opt/solarman-hub/.env` avant de démarrer le Hub :

```dotenv
HUB_WEB_PORT=18080
HUB_LOGGER_PORT=18899
```

Relancez ensuite `docker compose up -d --wait --wait-timeout 120`, puis utilisez `http://VM_IP:18080` et la destination `VM_IP:18899` pour le logger. Laissez les paramètres d’écoute de l’interface à leurs valeurs par défaut : ces variables changent les ports publiés par Docker. Gardez `.env` confidentiel.

## 5. Vérifier le fonctionnement et résoudre les problèmes

Dans la VM, depuis `/opt/solarman-hub` :

```sh
docker compose ps
curl --fail http://127.0.0.1:8080/health
docker compose logs --tail 100 hub
```

Remplacez `8080` par le port web publié si vous l’avez changé. Un contrôle de santé réussi signifie que le serveur web répond. Vérifiez aussi dans l’interface la connexion du logger, la dernière mesure et les états du cloud et de MQTT. Les mesures apparaissent lorsqu’un logger configuré envoie un rapport compatible. Les journaux et les exports peuvent contenir des identifiants d’appareils : gardez-les confidentiels.

Si `docker compose` est introuvable, vérifiez que le système est bien Debian 13 et que `docker-cli` et `docker-compose` sont installés. Si `hub` s’est arrêté, examinez ses journaux avant de demander le jeton. Si le navigateur ne se connecte pas, vérifiez l’IP actuelle de la VM, le pont/VLAN, le pare-feu et le port publié. Réservez l’adresse avant d’y diriger le logger.

## 6. Sauvegarder, mettre à jour et restaurer

Le volume nommé Compose `hub-data`, monté sur `/data`, conserve les jetons, paramètres, profils et historique dans le répertoire de données Docker de la VM. Reconstruire le conteneur préserve ce volume. **N’exécutez jamais `docker compose down -v` et ne supprimez pas le volume si vous souhaitez garder vos données.** Ne le placez pas sur un système de fichiers temporaire et incluez son disque virtuel dans vos sauvegardes.

Pour une sauvegarde simple et cohérente, choisissez VM → **Backup → Backup now**, un stockage de sauvegarde séparé et le mode **Stop**. La VM et la collecte s’arrêtent brièvement ; vérifiez que la VM fonctionne à nouveau ensuite. Planifiez des sauvegardes régulières dans Proxmox et testez une restauration. Un instantané seul n’est pas une sauvegarde. Les sauvegardes contiennent des identifiants : limitez leur accès. Consultez la [documentation Proxmox sur la sauvegarde et la restauration](https://github.com/proxmox/pve-docs/blob/master/vzdump.adoc).

Avant une mise à jour, créez une sauvegarde. Puis, dans la VM :

```sh
cd /opt/solarman-hub
git pull --ff-only
docker compose build --pull hub
docker compose up -d --wait --wait-timeout 120
docker compose ps
```

Ces commandes récupèrent les dernières sources et reconstruisent le Hub. Le transfert s’interrompt brièvement pendant le remplacement du conteneur. Conservez le même répertoire, le même nom de projet Compose et le même volume de données. Installez séparément les mises à jour de sécurité de Debian et de Docker avec APT.

Pour restaurer, arrêtez la VM défaillante et restaurez la sauvegarde complète choisie dans Proxmox. Laissez la VM d’origine éteinte lorsque vous démarrez la copie restaurée pour éviter les conflits d’IP, de sessions de logger et d’identifiants clients MQTT. Vérifiez son adresse locale, l’état du service et la dernière mesure reçue. Les données postérieures à la sauvegarde sont perdues ; les rapports confirmés localement pendant une panne ne sont pas renvoyés automatiquement au cloud.

## 7. En option : transmettre l’USB de l’ESP32 à la VM

Le fonctionnement normal du Hub ne nécessite ni ESP32 ni USB. Pour utiliser l’outil de flashage facultatif, branchez la carte sur l’hôte Proxmox et sélectionnez VM → **Hardware → Add → USB Device**. Choisissez la carte et transmettez-la à la VM ; redémarrez celle-ci si nécessaire. Dans Debian, vérifiez le chemin réel du périphérique :

```sh
ls -l /dev/serial/by-id/
```

Suivez ensuite **ESP32 / Flashage** dans le Hub ou le [guide d’utilisation](../../src/solarman_hub/guides/fr.md). Un appareil USB branché seulement à l’ordinateur qui affiche l’interface n’est pas accessible à la VM. La commande de flashage lance un conteneur d’outillage séparé. **L’installation de l’image usine peut réinitialiser les paramètres de la carte.**
