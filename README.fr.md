<p align="center"><img src="logo.png" width="96" alt="Logo VMI+"></p>

[🇬🇧 English](README.md) · 🇫🇷 Français

# VMI+ → Home Assistant

Intégration Home Assistant non officielle qui pilote les centrales de ventilation **Ventilairsec
VMI+ / VMCI** en Bluetooth Low Energy, en local, sans le cloud du fabricant. Elle a été construite
par rétro-ingénierie de l'app Android officielle VMI+ et vérifiée sur une vraie centrale **Urban**.

Tout ce que l'app affiche ou pilote pour un particulier est disponible dans Home Assistant. Le
protocole, y compris les fonctions installateur et SAV volontairement laissées de côté, est décrit
dans [PROTOCOL.fr.md](PROTOCOL.fr.md).

## Installation

**HACS :** ajoute ce dépôt comme dépôt personnalisé (catégorie *Intégration*), installe
« VMI+ (Ventilairsec) », puis redémarre Home Assistant.

**Manuelle :** copie `custom_components/vmi_plus/` dans le dossier `custom_components/` de ta
configuration Home Assistant, puis redémarre.

La centrale est détectée par l'intégration Bluetooth (une notification apparaît dans Paramètres →
Appareils et services). Sinon, ajoute-la à la main : Ajouter une intégration → « VMI+
(Ventilairsec) » → adresse MAC. Il faut un adaptateur Bluetooth ou un proxy Bluetooth ESPHome à
portée de la centrale.

⚠️ La centrale n'accepte **qu'une connexion Bluetooth à la fois**. Pour utiliser l'app officielle,
coupe d'abord l'interrupteur « Connexion Bluetooth », puis rallume-le après.

## Entités

Toutes les entités appartiennent à un seul appareil. Les entity_id commencent par le nom de ton
appareil (ex. `select.urban_vitesse` pour un appareil nommé « Urban »).

| Fonction de l'app | Entité | Type |
|---|---|---|
| Vitesse (3 niveaux, aussi le curseur « Débit théorique ») | Vitesse | `select` |
| Boost 30 min | Boost | `switch` |
| Bouton préchauffage | Préchauffage | `switch` |
| Mode vacances | Holiday | `switch` |
| Mode nuit (surventilation nocturne) | Mode nuit | `switch` |
| Débit fixe (radon) | Débit fixe (radon) | `switch` |
| Plages horaires on/off, programme de la semaine en attributs | Plages horaires | `switch` |
| Édition des plages horaires | `vmi_plus.set_day_schedule` | service |
| Consigne de préchauffage | Température de préchauffage | `number` |
| Limite de soufflage été | Limite température été | `number` |
| Température / humidité de la télécommande | Température pièce / Humidité pièce | `sensor` |
| Température / humidité de la sonde interne | Température sonde interne / Humidité sonde interne | `sensor` |
| Autonomie restante du filtre (jours) | Autonomie filtre | `sensor` |
| Débit théorique (m³/h) | Débit théorique | `sensor` |
| Saison | Saison | `sensor` |
| Jours de fonctionnement | Jours de fonctionnement | `sensor` (diagnostic) |
| Version logicielle | Version logicielle | `sensor` (diagnostic) |
| Volume à ventiler, surface, type de préchauffage | Volume à ventiler / Surface / Type de préchauffage | `sensor` (diagnostic) |
| Turbo chauffage, gestion technique du bâtiment (GTC), action en cours | Turbo chauffage / GTC / Action en cours | `binary_sensor` (diagnostic) |
| Capteurs sans fil associés, détail en attributs | Capteurs associés | `sensor` (diagnostic) |
| Bypass de l'échangeur (+ position, température) | Bypass échangeur / Position bypass | `binary_sensor` / `sensor` |
| Autotest (écran Diagnostic) | Autotest | `binary_sensor` (problème) |
| Localiser la centrale | Localiser (LED) | `button` |
| Filtre remplacé (6 ou 12 mois) | Filtre changé (6 mois) / (12 mois) | `button`, **remet le compteur filtre à zéro** |
| Libérer la centrale pour l'app officielle | Connexion Bluetooth | `switch` |

Le modèle, le numéro de série et les versions logicielle et matérielle sont affichés sur la page de
l'appareil.

Volontairement non exposé : configuration installateur (volume, surface, durée de vie du filtre,
réglages bypass et GTC / Modbus, appairage des capteurs), mise à jour firmware, export de
l'historique, reset usine et commandes SAV.

### Fonctionnement

- Les mesures sont relevées toutes les 10 secondes. Chaque interrupteur et sélecteur reflète
  **l'état lu sur la centrale** : un changement fait avec l'app ou la télécommande apparaît au relevé
  suivant.
- Pendant une coupure Bluetooth, les entités gardent leur dernière valeur au lieu de passer en
  indisponible.

### Programme des plages horaires

Exemple : lundi en vitesse moyenne à partir de 7 h, faible à partir de 22 h.

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

Activer les plages horaires applique le programme tout de suite ; un programme vide correspond à la
vitesse la plus basse.

## Tableau de bord

[`dashboard.yaml`](dashboard.yaml) est un tableau de bord organisé comme l'app officielle, avec
uniquement des cartes intégrées. Les instructions d'installation sont en tête du fichier (adapte le
préfixe des entity_id au nom de ton appareil).

## Outil en ligne de commande

[`vmi_ble.py`](vmi_ble.py) dialogue avec la centrale sans Home Assistant, pratique pour tester le
protocole depuis n'importe quelle machine équipée du Bluetooth :

```bash
pip install bleak
python3 vmi_ble.py scan
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF speed 2
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF boost on
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF monitor
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF raw --reg 0x18 --val 0x01
```

## Tests

`tests/test_protocol.py` vérifie l'encodage et le décodage des trames sur de vraies trames, sans
aucune dépendance :

```bash
python3 -m unittest discover -s tests
```

## Désinstallation

Paramètres → Appareils et services → VMI+ → ⋮ → Supprimer, puis supprime
`custom_components/vmi_plus/` si l'installation était manuelle. Rien n'est stocké sur la centrale.

## Avertissement

Ce projet n'est pas affilié à Ventilairsec. Utilisation à tes risques : les registres SAV et usine
listés dans [PROTOCOL.fr.md](PROTOCOL.fr.md) ne doivent jamais être envoyés à une centrale.
