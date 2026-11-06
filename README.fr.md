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

**Marketplace** (Home Assistant 2026.11 et suivants) : Paramètres → Marketplace → *Ajouter depuis un
lien*, saisis `https://github.com/srThibaultP/ha-vmi-plus`, valide avec *Ajouter* (choisis
*Intégrations* si le type est demandé), installe « VMI+ (Ventilairsec) », puis redémarre Home
Assistant. Sur les versions plus anciennes, ajoute le même lien comme dépôt personnalisé dans HACS.

**Manuelle :** copie `custom_components/vmi_plus/` dans le dossier `custom_components/` de ta
configuration Home Assistant, puis redémarre.

La centrale est détectée par l'intégration Bluetooth (une notification apparaît dans Paramètres →
Appareils et services). Sinon, ajoute-la à la main : Ajouter une intégration → « VMI+
(Ventilairsec) » → adresse MAC. Il faut un adaptateur Bluetooth ou un proxy Bluetooth ESPHome à
portée de la centrale.

⚠️ La centrale n'accepte **qu'une connexion Bluetooth à la fois**. Pour utiliser l'app officielle,
désactive d'abord l'intégration (Paramètres → Appareils et services → VMI+ → ⋮ → Désactiver), puis réactive-la après.

## Entités

Toutes les entités appartiennent à un seul appareil. Les entity_id commencent par le nom de ton
appareil (ex. `select.urban_speed` pour un appareil nommé « Urban »). Les noms suivent la langue de
Home Assistant (anglais et français fournis).

| Fonction de l'app | Entité | Type |
|---|---|---|
| Vitesse (3 niveaux, aussi le curseur « Débit théorique ») | Vitesse | `select` |
| Boost 30 min | Boost | `switch` |
| Bouton préchauffage | Préchauffage | `switch` |
| Mode vacances | Holiday | `switch` |
| Mode nuit (surventilation nocturne) | Mode nuit | `switch` |
| Débit fixe (radon) | Débit fixe (radon) | `switch` (désactivé par défaut) |
| Plages horaires on/off | Plages horaires | `switch` (désactivé par défaut) |
| Édition des plages horaires | `vmi_plus.set_day_schedule` | service |
| Consigne de préchauffage | Température de préchauffage | `number` |
| Limite de soufflage été | Limite température été | `number` |
| Température / humidité de la télécommande | Température pièce / Humidité pièce | `sensor` |
| Température / humidité de la sonde interne | Température sonde interne / Humidité sonde interne | `sensor` |
| Autonomie restante du filtre (jours) | Autonomie filtre | `sensor` |
| Débit théorique (m³/h) | Débit théorique | `sensor` |
| Saison | Saison | `sensor` |
| Jours de fonctionnement | Jours de fonctionnement | `sensor` (diagnostic) |
| Version logicielle | Version logicielle | `sensor` (diagnostic, désactivé par défaut) |
| Volume à ventiler, surface, type de préchauffage | Volume à ventiler / Surface / Type de préchauffage | `sensor` (diagnostic, désactivé par défaut) |
| Turbo chauffage, gestion technique du bâtiment (GTC), action en cours | Turbo chauffage / GTC / Action en cours | `binary_sensor` (diagnostic, désactivé par défaut) |
| Nombre de capteurs sans fil associés | Capteurs associés | `sensor` (diagnostic, désactivé par défaut) |
| Bypass de l'échangeur (+ position, température) | Bypass échangeur / Position bypass / Température bypass | `binary_sensor` / `sensor` (position et température : diagnostic, désactivés par défaut) |
| Autotest (écran Diagnostic) | Autotest | `binary_sensor` (problème, diagnostic, désactivé par défaut) |
| Localiser la centrale | Localiser (LED) | `button` (désactivé par défaut) |
| Filtre remplacé (6 ou 12 mois) | Filtre changé (6 mois) / (12 mois) | `button`, **remet le compteur filtre à zéro** |

Les entités de diagnostic (hormis Jours de fonctionnement), ainsi que Débit fixe, Plages horaires
et Localiser, sont désactivées par défaut : active-les depuis la page de l'appareil si besoin.
L'action `vmi_plus.set_day_schedule` cible l'interrupteur Plages horaires : active-le d'abord.

Le modèle, le numéro de série et les versions logicielle et matérielle sont affichés sur la page de
l'appareil.

Volontairement non exposé : modification de la configuration installateur (volume, surface, durée
de vie du filtre, réglages bypass et GTC / Modbus, appairage des capteurs ; volume et surface sont
seulement affichés en lecture seule), mise à jour firmware, export de l'historique, reset usine et
commandes SAV.

### Fonctionnement

- Les mesures sont relevées toutes les 10 secondes. Chaque interrupteur et sélecteur reflète
  **l'état lu sur la centrale** : un changement fait avec l'app ou la télécommande apparaît au relevé
  suivant.
- Les entités passent en indisponible tant que la centrale est injoignable (app officielle connectée, hors de portée).
- Le programme de la semaine et le détail de chaque capteur associé sont dans les diagnostics : page
  de l'intégration → ⋮ → Télécharger les diagnostics (adresse MAC et numéros de série masqués).
  Joins ce fichier à un rapport de bug.

### Programme des plages horaires

Exemple : lundi en vitesse moyenne à partir de 7 h, faible à partir de 22 h.

```yaml
action: vmi_plus.set_day_schedule
target:
  entity_id: switch.urban_time_slots
data:
  day: 1
  slots:
    - {start: 7, speed: medium}
    - {start: 22, speed: low, temperature: 16}
```

Activer les plages horaires applique le programme tout de suite ; un programme vide correspond à la
vitesse la plus basse.

## Tableau de bord

[`dashboard.yaml`](dashboard.yaml) est un tableau de bord organisé comme l'app officielle, avec
uniquement des cartes intégrées. Les instructions d'installation sont en tête du fichier (adapte le
préfixe des entity_id au nom de ton appareil).

## Outil en ligne de commande et bibliothèque

Le protocole Bluetooth est dans la bibliothèque Python
[vmi-plus-ble](https://github.com/srThibaultP/vmi-plus-ble), qui fournit aussi un outil en ligne de
commande pour tester une centrale sans Home Assistant :

```bash
pip install "vmi-plus-ble @ git+https://github.com/srThibaultP/vmi-plus-ble"
vmi-plus-ble scan
vmi-plus-ble status AA:BB:CC:DD:EE:FF
vmi-plus-ble speed AA:BB:CC:DD:EE:FF high
```

## Tests

L'intégration est testée avec
[pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) :

```bash
pip install pytest-homeassistant-custom-component -e ../vmi-plus-ble
pytest --cov
```

## Désinstallation

Paramètres → Appareils et services → VMI+ → ⋮ → Supprimer, puis supprime
`custom_components/vmi_plus/` si l'installation était manuelle. Rien n'est stocké sur la centrale.

## Avertissement

Ce projet n'est pas affilié à Ventilairsec. Utilisation à tes risques : les registres SAV et usine
listés dans [PROTOCOL.fr.md](PROTOCOL.fr.md) ne doivent jamais être envoyés à une centrale.
