<p align="center"><img src="logo.png" width="96" alt="Logo VMI+"></p>

# VMI+ → Home Assistant

Intégration non-officielle pour piloter en Bluetooth Low Energy une centrale de ventilation
**VMI+ / VMCI (Ventilairsec)**, reverse-engineered à partir de l'app Android officielle et
d'une capture BLE réelle. Détails complets du protocole : [PROTOCOL.md](PROTOCOL.md).

**Vérifié contre du matériel réel** : vitesse (1/2/3), Boost, Bypass, et température/humidité
des deux sondes (interne + télécommande/pièce). **Pas encore fait** : % de filtre, numéros de
série, historique — voir "Ce qui reste à faire" dans [PROTOCOL.md](PROTOCOL.md).

## 0. Tests unitaires du protocole

`tests/test_protocol.py` vérifie `protocol.py` (checksum, construction/décodage de
trames) contre les trames réellement capturées documentées dans PROTOCOL.md —
aucune dépendance (ni `homeassistant`, ni `pytest`) : `python3 -m unittest discover
-s tests`.

## 1. Tester d'abord en ligne de commande

Avant d'installer l'intégration complète, valide le protocole directement avec le script
autonome `vmi_ble.py`, depuis n'importe quelle machine avec Bluetooth (ta box Home Assistant,
un Raspberry Pi, un PC Linux...) :

```bash
pip install bleak
python3 vmi_ble.py scan
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF speed 2
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF boost on
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF bypass on
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF monitor   # température/humidité en direct
```

⚠️ La centrale n'accepte qu'une connexion BLE à la fois — ferme l'app VMI+ sur ton téléphone
avant de tester, sinon la connexion échouera ou coupera l'app.

## 2. Installer l'intégration Home Assistant

Copie le dossier `custom_components/vmi_plus/` dans le dossier `custom_components/` de ta
config Home Assistant, puis redémarre HA. La centrale devrait être auto-détectée par
l'intégration Bluetooth (Paramètres → Appareils → une notification de découverte devrait
apparaître) ; sinon, ajoute-la manuellement via Paramètres → Appareils → Ajouter une
intégration → "VMI+ (Ventilairsec)" et saisis l'adresse MAC.

Toutes les entités sont regroupées sous un seul **appareil** (nommé d'après la centrale
détectée, ex. "Urban") — Paramètres → Appareils et services → Appareils → cet appareil →
crayon ✏️ pour lui assigner une pièce.

Entités créées (l'entity_id complet dépend du nom de ton appareil — ex. pour un appareil
nommé "Urban" : `select.urban_vitesse`, `switch.urban_boost`... vérifiable dans Outils de
développement → États) :
- **Vitesse** (`select`, suffixe `_vitesse`) — vitesse 1/2/3 (entité `select` et non `fan` :
  la centrale ventile en continu et ne peut pas être éteinte, alors que le domaine `fan` de HA
  impose toujours une position "Off")
- **Boost** (`switch`, suffixe `_boost`) — surventilation 30 min
- **Bypass** (`switch`, suffixe `_bypass`) — contournement de l'échangeur (préchauffage gratuit
  de l'air, utile en hiver)
- **Holiday** (`switch`, suffixe `_holiday`) — mode absence prolongée. ⚠️ L'app officielle
  demande aussi un nombre de jours, mais cette valeur n'est **jamais transmise à la centrale**
  en Bluetooth (vérifié par capture réelle : une seule trame d'écriture, juste l'interrupteur) —
  purement informatif côté app, cette entité `switch` couvre donc déjà 100% de ce que fait
  réellement le Bluetooth pour ce mode.
- **Connexion Bluetooth** (`switch`, suffixe `_connexion_bluetooth`) — active/désactive la
  connexion BLE (utile pour libérer la centrale au profit de l'app officielle, une seule
  connexion GATT possible à la fois)
- **Température/Humidité sonde interne** (`sensor`, suffixes `_temperature_sonde_interne` /
  `_humidite_sonde_interne`) — sonde interne (ex. sortie résistance de préchauffage)
- **Température/Humidité pièce** (`sensor`, suffixes `_temperature_piece` / `_humidite_piece`)
  — sonde télécommande de la pièce ventilée (ex. salle de bain)
- **Mode nuit** (`switch`, suffixe `_mode_nuit`) — "Night ventilation boost" (sur-ventilation
  nocturne gratuite été/préchauffage passif hiver). ⚠️ Registre à bascule (pas de valeur
  explicite ON/OFF comme les autres switches, voir PROTOCOL.md) : cette entité ne bascule que
  si l'état actuellement connu diffère de l'état demandé, pour éviter d'inverser par erreur —
  dans de rares cas un état légèrement périmé (poll 10s) pourrait faire basculer dans le
  mauvais sens si l'état a changé entretemps depuis l'app officielle ou la télécommande
  physique, mais se corrige de lui-même au poll suivant.

Les sensors sont alimentés par un polling automatique toutes les 10s (démarré dès qu'une
entité sensor est chargée) — pas besoin de configuration supplémentaire.

**Testé et fonctionnel en conditions réelles** (vitesse, boost, bypass, holiday, mode nuit,
lecture des sondes) sur une vraie instance HA.

Vitesse, Boost, Bypass, Holiday et Mode nuit reflètent tous une **vraie lecture de l'appareil**
(notification type `0x01`, rafraîchie au plus toutes les 10s par le polling périodique), pas
juste la dernière commande envoyée par HA — si tu changes un réglage via l'app officielle ou la
télécommande physique, ces entités se corrigent au poll suivant.

Toutes les entités restent **toujours "disponibles"**, même pendant une coupure Bluetooth
(ex. l'app officielle reprend temporairement la main) : plutôt que de passer en
`unavailable`/`unknown` et perdre leur dernière valeur connue, elles la gardent figée jusqu'à
la prochaine lecture réussie.

## 3. Tableau de bord (optionnel)

[`dashboard.yaml`](dashboard.yaml) reprend la mise en page de l'app officielle (vitesse,
boost, bypass, sondes) avec les entités ci-dessus — uniquement des cartes intégrées à Home
Assistant, rien à installer en plus. Voir l'en-tête du fichier pour l'installation (et pour
le rappel d'adapter le préfixe des entity_id au nom de ton propre appareil).

## 4. Désinstaller

Paramètres → Appareils et services → cette intégration → ⋮ → Supprimer (ou depuis HACS :
Intégrations → VMI+ → ⋮ → Supprimer). Supprime aussi le dossier
`custom_components/vmi_plus/` si l'intégration a été installée manuellement plutôt que via
HACS. Aucune donnée n'est stockée côté centrale — la retirer côté Home Assistant n'affecte
pas l'app officielle ni la centrale elle-même.

## 5. Prochaines étapes possibles

Voir la section "Ce qui reste à faire" dans [PROTOCOL.md](PROTOCOL.md) — principalement le
décodage de la télémétrie pour avoir des sensors (humidité, filtre, RPM) plutôt que juste du
contrôle.
