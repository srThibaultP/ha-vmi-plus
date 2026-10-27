<p align="center"><img src="logo.png" width="96" alt="Logo VMI+"></p>

# VMI+ → Home Assistant

Intégration non-officielle pour piloter en Bluetooth Low Energy une centrale de ventilation
**VMI+ / VMCI (Ventilairsec)**, reverse-engineered à partir de l'app Android officielle et
d'une capture BLE réelle. Détails complets du protocole : [PROTOCOL.md](PROTOCOL.md).

**Feature parity with the official app**: everything the app shows or controls for a private
customer is available in Home Assistant (table in section 2), checked against a real Urban unit.
The full protocol, including the installer and after-sales functions that are deliberately not
exposed, is in [PROTOCOL.md](PROTOCOL.md).

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

Entities (the full entity_id depends on the device name, e.g. `select.urban_vitesse` for a device
named "Urban"; check Developer tools → States). Every app feature maps to one of them:

| App screen | Entity | Type | Register / frame |
|---|---|---|---|
| Home: 3 speeds (also the "Theoretical air flow" slider) | Vitesse | `select` | `0x18`, status `[34]` |
| Home: Boost 30 min | Boost | `switch` | `0x19`, status `[44]` |
| Home: preheat button | Préchauffage (`_bypass`, named "Bypass" before v0.4.0) | `switch` | `0x2f`, status `[53]` |
| Home: FILTER gauge / Equipment life: filter life | Autonomie filtre (days) | `sensor` | status `[28:30]` |
| Home: bathroom remote control | Température / Humidité pièce | `sensor` | SensorsState `0x02` |
| Special modes: holiday | Holiday | `switch` | `0x1a`, status `[43]` |
| Special modes: night ventilation boost | Mode nuit | `switch` | `0x0b` (toggle), status `[33]` |
| Special modes: fixed air flow (radon) | Débit fixe (radon) | `switch` | `0x1b`, status `[45]` |
| Configuration: activating time slots | Plages horaires (+ weekly schedule as attributes) | `switch` | `0x1d`, status `[46]`, TimeSlotState `0x05` |
| Configuration: time slots editor | `vmi_plus.set_day_schedule` | service | ConfigTimeSlot `0x19` |
| Simplified configuration: theoretical air flow | Débit théorique (m³/h) | `sensor` | status `[47:49]` / 5 |
| Simplified configuration: preheat target | Température de préchauffage | `number` | `0x1c`, status `[35]` |
| Simplified configuration: summer limit | Limite température été | `number` | `0x17`, status `[38]` |
| Equipment life: operating days | Jours de fonctionnement | `sensor` | status `[26:28]` |
| Equipment life: season | Saison | `sensor` | status `[51]` |
| Equipment life: housing, serial, versions | device info (model, serial number, firmware, hardware) + Version logicielle | device / `sensor` | status `[5:9]`, `[19]`, `[20]`, `[21]`, `[49]`, `[50]` |
| Equipment life: volume to ventilate, surface, preheat type | Volume à ventiler (m³) / Surface (m²) / Type de préchauffage | `sensor` (diagnostic) | status `[22:24]`, `[17]` × 2, `[24]` |
| Equipment life: turbo heat, building management (GTC) | Turbo chauffage / GTC | `binary_sensor` (diagnostic) | status `[52]`, `[15]` |
| (not shown by the app) locate / action running | Action en cours | `binary_sensor` (diagnostic) | status `[9]` |
| Instantaneous measurements: internal probe | Température / Humidité sonde interne | `sensor` | ProbesState `0x03` |
| Diagnostic | Autotest (problem) | `binary_sensor` | status `[10]`–`[14]` |
| Sensor management | Capteurs associés (list as attributes) | `sensor` | SensorsState `0x02` |
| Maintenance: filter change (6 / 12 months) | Filtre changé (6 mois) / (12 mois) | `button` | `0x05` = months. **Restarts the filter counter.** |
| Find my unit | Localiser (LED) | `button` | `0x02` |
| (not shown by the app) heat-exchanger bypass | Bypass échangeur (+ position, temperature) / Position bypass | `binary_sensor` / `sensor` | status `[25]`, ByPassState `0x18` |
| — | Connexion Bluetooth | `switch` | frees the unit for the official app |

Not exposed on purpose (installer / after-sales functions, documented in
[PROTOCOL.md](PROTOCOL.md)): installer configuration frames (volume, surface, filter lifespan,
bypass and GTC/Modbus settings, sensor pairing), firmware update, history CSV export (the app
e-mails it through the vendor's cloud; Home Assistant keeps its own history), factory reset and
after-sales work codes.

Example of a time slot programme (Monday: Moyenne from 7 h, Faible from 22 h):

```yaml
action: vmi_plus.set_day_schedule
target:
  entity_id: switch.urban_plages_horaires
data:
  day: 1
  slots:
    - {start: 7, speed: Moyenne}
    - {start: 22, speed: Faible}
```

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

## 5. What is left

See "Ce qui reste à faire" in [PROTOCOL.md](PROTOCOL.md): mostly confirming a few installer-only
fields on other units (CO₂ sensors, hydraulic preheating) that we cannot test on ours.
