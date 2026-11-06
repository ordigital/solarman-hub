# Solarman Hub

![Solarman Hub](../images/solarman-hub.png)

**Solarman Hub est un projet personnel indépendant, sans affiliation avec SOFAR (SofarSolar).**

[English](../../README.md) · [Polski](pl.md) · [Deutsch](de.md) · [Français](fr.md) · [Čeština](cs.md) · [Slovenčina](sk.md) · [Lietuvių](lt.md) · [Українська](uk.md) · [Русский](ru.md)

Solarman Hub relie votre logger Solarman V5 au cloud du fabricant tout en vous donnant accès aux mesures en local. Son interface web permet de consulter les valeurs et les graphiques, de conserver un historique, de gérer les profils de décodage et de connecter Home Assistant via MQTT. L’interface et le guide sont disponibles en neuf langues.

Le profil fourni pour Sofar HYD G3 / LSW3 décode 48 champs de mesure. Les autres formats de rapport nécessitent un profil compatible, vérifié séparément. Les rapports restent transmis même si leur décodage échoue.

## Choisir une installation

| Environnement | Pour commencer |
|---|---|
| Linux avec Docker Engine et Compose v2 | Démarrage rapide ci-dessous |
| Proxmox VE | [Créer une VM Debian 13, étape par étape](../proxmox/fr.md) |
| Python 3.12+ sans Docker | [Guide d’utilisation](../../src/solarman_hub/guides/fr.md) |

Sur Proxmox, commencez avec une VM Debian 13, 2 vCPU, 2 Go de RAM et un disque de 20 Go. Réservez son adresse sur le réseau local et activez son démarrage automatique. Prévoyez davantage d’espace pour conserver un historique plus long.

**[Installation automatique de la VM](../proxmox/fr.md)**

Exécutez cette commande en tant que **root dans le Shell du nœud Proxmox**, et non dans une VM. L’assistant vous guide étape par étape. Vérifiez le récapitulatif avant de confirmer.

```sh
bash -c "$(wget -qLO - https://raw.githubusercontent.com/ordigital/solarman-hub/main/scripts/proxmox-vm.sh)"
```

## Démarrage rapide avec Docker

Une fois Docker Engine et Compose v2 installés :

```sh
git clone https://github.com/ordigital/solarman-hub.git
cd solarman-hub
docker compose up -d --build --wait --wait-timeout 120
docker compose exec hub solarman-hub token --data-dir /data
```

Ajoutez `sudo` aux commandes Docker si votre installation l’exige.

Ouvrez `http://SERVER_IP:8080` en remplaçant l’adresse par celle de l’hôte Docker ou de la VM. Connectez-vous avec le jeton affiché. Il reste identique après les redémarrages et les mises à jour tant que vous conservez le volume de données. Ajoutez le **numéro de série numérique du logger**, choisissez un profil compatible, puis enregistrez et appliquez les paramètres. Configurez ensuite la destination TCP distante du logger avec cette même adresse et le port `10000`. Seuls les loggers configurés peuvent se connecter. Sur Proxmox, utilisez l’adresse de la VM, et non celle de l’interface d’administration de Proxmox.

Les paramètres, les jetons et l’historique sont conservés dans le volume Docker monté sur `/data`. Aucun compte Solarman, cookie ou mot de passe Wi-Fi n’est nécessaire. Pour Home Assistant, utilisez l’adresse et les identifiants de votre broker MQTT.

Consultez le guide pour choisir d’autres ports ou utiliser une installation existante lancée avec `docker run`.

[Changer le serveur du logger : procédure pas à pas, avec la page cachée des paramètres.](../../src/solarman_hub/guides/fr.md)

## Utilisation et documentation

[Guide complet](../../src/solarman_hub/guides/fr.md) · [Installation sur Proxmox](../proxmox/fr.md) · [Développement](../DEVELOPMENT.md) · [Architecture](../ARCHITECTURE.md) · [Audit et limites](../AUDIT.md)

Le guide est également accessible dans l’interface. Il couvre le transfert vers le cloud, les accusés de réception locaux, MQTT, l’historique, les profils et la configuration de l’ESP32.

**Les rapports confirmés localement pendant une panne ne sont pas ajoutés ensuite à l’historique du cloud.** Les limites de stockage peuvent aussi créer des lacunes dans l’historique local. L’arrêt du Hub interrompt le transfert. Réservez les ports d’administration et de réception des loggers à un réseau local ou un VPN de confiance.

## ESP32 Companion en option

[Sources](../../firmware/esp32-companion) · [Micrologiciel et sommes de contrôle](../../firmware/esp32-companion/dist)

Le Companion peut recevoir et transmettre les rapports V5, capturer le trafic Wi-Fi et exporter des profils de décodage. Il fonctionne sur un ESP32 classique doté de 4 Mo de mémoire flash et possède une interface en anglais. L’ESP32 est facultatif : le Hub fonctionne sans lui.

Ouvrez **ESP32 / Flashage** dans le Hub pour télécharger le micrologiciel et consulter les instructions USB/OTA. L’installation de l’image usine peut réinitialiser les paramètres de la carte. Sur Proxmox, transmettez d’abord son périphérique USB à la VM.

Les profils créés à partir de rapports inconnus doivent être vérifiés manuellement. Le Companion ne peut ni reconnaître des mesures électriques dans des octets arbitraires, ni déchiffrer automatiquement le trafic Wi-Fi.

[♡ Buy me a coffee](https://buymeacoffee.com/adamstrad)
