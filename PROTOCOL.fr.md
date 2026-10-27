[🇬🇧 English](PROTOCOL.md) · 🇫🇷 Français

# Protocole BLE VMI+ (Ventilairsec)

Description, obtenue par rétro-ingénierie, du protocole Bluetooth Low Energy des centrales de
ventilation Ventilairsec VMI+ / VMCI (testé sur une centrale **Urban**) et de l'app Android
officielle **VMI+** (`com.ventilairsec.ventilairsecinstallateur`, Flutter).

Sources :

- Captures Bluetooth HCI de l'app officielle pilotant une vraie centrale, en changeant un seul
  réglage à la fois et en comparant les trames.
- Lectures et écritures directes depuis une machine Linux avec [bleak](https://github.com/hbldh/bleak).
- Le décodeur de trames de l'app elle-même, retrouvé en décompilant une version plus ancienne de
  l'app (voir [Refaire la décompilation](#refaire-la-décompilation)).

Les valeurs marquées ✓ ont été vérifiées sur une vraie centrale et sur les écrans de l'app. Le reste
vient uniquement du code de l'app.

## Connexion

- BLE standard, **sans appairage ni chiffrement** (GATT en clair).
- Découverte : par le nom annoncé (ex. `Urban`) ou par l'UUID du service de contrôle ci-dessous.
- **Un seul client à la fois.** Tant qu'un client est connecté, la centrale n'émet plus d'annonces :
  l'app et Home Assistant ne peuvent pas être connectés en même temps.

| Rôle | UUID du service | UUID de la caractéristique | Propriétés |
|---|---|---|---|
| Contrôle (écritures) | `0003cbbb-0000-1000-8000-00805f9b0131` | `0003cbb1-0000-1000-8000-00805f9b0131` | Read, Write with response, Notify |
| Télémétrie (notifications) | `0003cab5-0000-1000-8000-00805f9b0131` | `0003caa2-0000-1000-8000-00805f9b0131` | Notify |

L'app contient aussi une seconde famille d'UUID (`7c4adc01`…`7c4adc07-2f33-11e7-93ae-92361f002671`),
probablement pour une autre gamme ; l'Urban ne l'utilise pas.

## Format des trames

Toutes les trames, dans les deux sens, ont la même forme :

```
A5 B6 [classe] 06 [len] [payload …] [crc]
```

- `A5 B6` : constante de début.
- `classe` : classe de trame (tableaux ci-dessous).
- `06` : constante (la toute première écriture d'une session utilise `00` : `a5b6100005030000000016`).
- `len` : longueur du payload.
- `crc` : somme de contrôle de tous les octets qui précèdent.

### Somme de contrôle

```python
def checksum(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 1) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc ^ 0x13
```

### Commandes (classe `0x10`)

Les commandes portent un payload de 5 octets `[REG, 0, 0, 0, VAL]` :

```python
def build_command(register: int, value: int) -> bytes:
    data = bytes([0xA5, 0xB6, 0x10, 0x06, 0x05, register, 0, 0, 0, value])
    return data + bytes([checksum(data)])
```

| Commande | Trame |
|---|---|
| Vitesse 1 / 2 / 3 | `a5b610060518000000000b` / `…010a` / `…0209` |
| Boost on / off | `a5b610060519000000010b` / `a5b610060519000000000a` |
| Bouton préchauffage on / off | `a5b61006052f000000013d` / `a5b61006052f000000003c` |
| Mode nuit (bascule) | `a5b61006050b0000000018` |

Les écritures sont des *Write Requests* GATT sur la caractéristique de contrôle. La centrale répond
sur la caractéristique de télémétrie.

## Classes de trames

App → centrale : `0x10` Command ✓, `0x11` Setting, `0x12` Config, `0x13` ConfigSensors, `0x15`
ConfigErp, `0x17` ConfigByPass, `0x19` ConfigTimeSlot ✓, `0x1a` UpdateDate ✓, `0x20` NewUpdate,
`0x21` Update, `0x22` UpdateAckData.

Centrale → app : `0x01` State ✓, `0x02` SensorsState ✓, `0x03` ProbesState ✓, `0x04` SimpleData,
`0x05` TimeSlotState ✓, `0x16` ErpState, `0x18` ByPassState ✓, `0x1b` AutoTestDatas, `0x23`
AckData, `0x30` Csv, `0x31` Histo, `0xff` Nack.

## Registres de commande

| Reg | Nom dans l'app | Usage |
|---|---|---|
| `0x01` | Test | |
| `0x02` | Localisation | fait clignoter la LED pour trouver la centrale ✓ |
| `0x03` | State | lecture → trame State ✓ |
| `0x04` | Update | mise à jour firmware |
| `0x05` | NewFilter | filtre remplacé, valeur = intervalle en mois (6 ou 12). **Remet le compteur filtre à zéro.** |
| `0x06` | Sensors | lecture → SensorsState ✓ |
| `0x07` | Probes | lecture → ProbesState ✓ |
| `0x09` / `0x22` / `0x21` / `0x20` | StartCsv / StartCsvV2 / StopCSV / CsvLength | export de l'historique |
| `0x0a` / `0x1f` | Old / NewSerialisation | usine |
| `0x0b` | Surventilation | mode nuit ✓, **bascule** à chaque écriture (valeur ignorée) |
| `0x0d` | Calibration | |
| `0x10` | DeleteSensor | |
| `0x12` | ErpState | lecture → ErpState |
| `0x13` | Reset | **reset usine, ne jamais envoyer** |
| `0x14` / `0x15` | ByPass / ByPassForced | `0x14` = lecture ByPassState ✓ |
| `0x16` / `0x23` | AutoTest / AutoTestDatas | autotest |
| `0x17` | Tmax | limite de soufflage été, °C ✓ |
| `0x18` | Mode | vitesse 0 / 1 / 2 ✓ |
| `0x19` | Boost | boost 30 min 1 / 0 ✓ |
| `0x1a` | Hollidays | mode vacances 1 / 0 ✓ (le nombre de jours reste dans l'app) |
| `0x1b` | FixedFlow | débit fixe (radon) 1 / 0 ✓ |
| `0x1c` | Temp | consigne de préchauffage, °C, `0` = pas de préchauffage ✓ |
| `0x1d` | TimeSlot | plages horaires 1 / 0 ✓ (répond par TimeSlotState) |
| `0x1e` | TempElec | |
| `0x24` / `0x25` | GeoVersion / ElecVersion | |
| `0x2c` | — | envoyé une fois par connexion par les apps récentes, rôle inconnu |
| `0x2f` | — | bouton préchauffage de l'écran d'accueil, 1 / 0 ✓ (apps récentes) |
| `0xf9`–`0xff` | Sav7 … Sav1 | actions SAV, **ne jamais envoyer** |

L'app interroge `0x03`, `0x06` et `0x07` tant qu'un écran est ouvert. Tous les écrans de l'app sont
construits à partir des trames State, SensorsState et ProbesState : ouvrir un écran n'envoie aucune
autre lecture.

## Trame State (`0x01`)

Réponse au registre `0x03` (et `0x0b`). Les positions sont des index dans la notification brute,
en-tête compris (`[0]` = `a5`).

| Position | Clé dans l'app | Signification |
|---|---|---|
| `[3]` | — | sert à l'app pour un contrôle de version |
| `[5:9]` LE | machineId | numéro de série (hexa), affiché avec un préfixe de modèle par l'app ✓ |
| `[9]` | — | action en cours (ex. localisation) ✓ |
| `[10]` bits | testStatus | 5 bits de résultat d'autotest, `0x1f` = tout OK ✓ |
| `[11]`–`[14]` | probe / preheat / engine / qai | détail par test |
| `[15]` | gtcEnabled | gestion technique du bâtiment (GTC / Modbus) activée |
| `[16]` | calibration | |
| `[17]` | surface | surface = valeur × 2 m² ✓ |
| `[18]` | height / flowPerPerson | |
| `[19]` | box | 1 Purevent, 2 Urban ✓, 3 PRO, 5 Cube |
| `[20]` | softwareVersion | majeure.mineure en quartets (`0x64` → 6.4) ✓ |
| `[21]` | elec | version électronique (quartet haut), version logicielle de la carte (quartet bas) ✓ |
| `[22:24]` LE | ventilateVolume | volume à ventiler, m³ ✓ |
| `[24]` | preheatType | 1 électrique ✓, 2 solaire, 3 smart, 4 smart partner, 5 partner |
| `[25]` | bypass | bypass de l'échangeur ouvert ✓ |
| `[26:28]` LE | upTime | jours de fonctionnement ✓ |
| `[28:30]` LE | autonomy | autonomie restante du filtre, jours (max 360) ✓ |
| `[32]` | theoreticalFlow | débit × 10 m³/h (anciennes apps) |
| `[33]` | surventilation | mode nuit, **inversé** : `0` = actif ✓ |
| `[34]` | mode | vitesse 0 / 1 / 2 ✓ |
| `[35]` | tempElec | consigne de préchauffage ✓ |
| `[36]` | tempHydro | consigne de préchauffage hydraulique |
| `[37]` bits | boxDefined | |
| `[38]` | tempBlowing | limite été ✓ |
| `[39:43]` LE | date | |
| `[43]` | hollidaysMode | ✓ |
| `[44]` | boost | ✓ |
| `[45]` | fixedFlow | ✓ |
| `[46]` | timeSlot | ✓ |
| `[47:49]` LE | — | débit théorique en 1/5 m³/h ✓ (apps récentes) |
| `[49]` | — | correctif de la version logicielle (`6.4.` + 3 chiffres) ✓ |
| `[50]` | meca | version mécanique ✓ |
| `[51]` | season | 0 été, 1 hiver, 2 mi-saison ✓ |
| `[52]` | turbo_heater | turbo chauffage ✓ |
| `[53]` | — | état du bouton préchauffage (registre `0x2f`) ✓ |

Le dernier octet est la somme de contrôle de la trame.

## SensorsState (`0x02`)

Réponse au registre `0x06`. Jusqu'à 10 capteurs sans fil, 10 octets chacun à partir de la position 5 :

| Octet | Signification |
|---|---|
| `+0..+3` LE | identifiant du capteur (hexa) ✓ |
| `+4` | pièce : 0 inconnue, 1 séjour, 2 cuisine, 3 salle de bain 1, 4 salle de bain 2, 5–8 chambre 1–4, 9 cave ✓ |
| `+5` | type : 0 absent, 1 Nexelec CO₂, 2 Nexelec température, 3 télécommande ✓, 4 box, 5 Nanosense |
| `+6..+7` | capteurs CO₂ : CO₂ en ppm (LE). Autres : `+6` = température °C (≥ 128 = négatif : valeur − 255) ✓ |
| `+8` | humidité % ✓ |
| `+9` | troisième valeur |

Le préfixe de l'identifiant indique le modèle à l'appairage : `I420` CO₂, `I880` température,
`ASI ` / `SNE ` télécommande.

## ProbesState (`0x03`)

Réponse au registre `0x07`. Jusqu'à 5 sondes filaires, 5 octets chacune à partir de la position 5 :
`[emplacement, température (signée), ?, humidité, ?]` ✓. Les emplacements vides lisent `0x08`.

## TimeSlotState (`0x05`) et ConfigTimeSlot (`0x19`)

- TimeSlotState : `[5]` = activé, puis 7 jours × 5 plages × `[heure de début, vitesse, temp]` à
  partir de la position 6. `début = 0xff` = plage vide. Vitesse 0 / 1 / 2.
- ConfigTimeSlot (app → centrale), une trame par jour : `[jour 1–7, (début, vitesse + 1, temp) × 5]`,
  plage vide `ff 00 00`. L'app envoie la vitesse 1 / 2 / 3, la centrale la stocke et la renvoie en
  0 / 1 / 2 ✓.
- `temp` est la consigne de préchauffage de la plage.
- Activer les plages horaires (registre `0x1d`) applique le programme tout de suite ; avec un
  programme vide, la centrale passe en vitesse la plus basse ✓.

## ByPassState (`0x18`)

Réponse au registre `0x14`.

| Position | Clé dans l'app |
|---|---|
| `[5]` | position % ✓ |
| `[6]` | type |
| `[8]` | température °C ✓ |
| `[11]` | inconnu |
| `[17:21]` LE | identifiant |
| `[21]` | forcé |
| `[22]` | position demandée % |

Le registre `0x15` force le bypass. Les réglages installateur passent par une trame ConfigByPass
(`0x17` : température, type, identifiant).

## Autres trames

- **UpdateDate** (`0x1a`) : mise à l'heure `[aa, mm, jj, hh, mi, ss]`, envoyée par l'app à chaque
  connexion ✓.
- **ErpState** (`0x16`, registre `0x12`) : réglages GTC / Modbus `[5]` mode, `[6]` adresse esclave,
  `[7]` vitesse, `[8]` parité, `[9]` bit de stop. Les centrales sans GTC ne répondent pas. Écrits
  avec ConfigErp (`0x15`).
- **Config** (`0x12`) : assistant d'installation, 18 octets : volume (2), type de box, type de bypass,
  durée de vie du filtre (mois), mode, température de préchauffage, limite été, température
  hydraulique, 0, date (`aa mm jj hh mi ss`), surface, hauteur.
- **Autotest** (`0x16` / `0x23` → `0x1b`) : l'écran Diagnostic des apps récentes n'affiche que les
  bits d'état `[10]`–`[14]`.
- **Historique** (`0x09`/`0x22`, `0x20`, `0x21` → `0x30` / `0x31`) : export CSV ; les apps récentes
  l'envoient par e-mail via le cloud du fabricant.
- **Mise à jour firmware** (`0x04`, `0x20`, `0x21`, `0x22`) : téléchargée par l'app puis envoyée par
  paquets.
- Notification `0x50` : envoyée par les firmwares récents, contenu inconnu.

## Menu SAV

Les apps récentes cachent un menu SAV derrière un code d'intervention : retour aux réglages usine,
forcer la mise à jour de la machine, forcer le firmware extraction (VMC-E) ou insufflation (VMC-I),
forcer l'installation, deux options de mot de passe et un lien pour déclarer un SAV. Chaque option
aboutit à l'un des registres Sav1–Sav7 (`0xff`…`0xf9`) et la centrale redémarre. Les anciennes apps
affichaient simplement des boutons « Command 1 »…« Command 7 ». **Aucun de ces registres ne doit être
envoyé à la main.**

## Codes d'erreur

Tirés des fichiers de traduction de l'app (`error_code_XX`). Leur emplacement dans les trames n'est
pas encore connu.

| Code | Signification |
|---|---|
| `01` | Panne de la résistance |
| `02` | Le préchauffage ne permet pas d'atteindre la consigne |
| `10` | Panne moteur |
| `20` | Remplacer le filtre |
| `30` | Panne d'un capteur de qualité d'air |
| `31`–`39` | Panne du capteur de qualité d'air n° 1 à 9 |
| `3A` | Plusieurs capteurs de qualité d'air |
| `3B` | Problème d'appairage d'un capteur de qualité d'air |
| `40` | Problème inconnu de la télécommande |
| `41` | Erreur de température de la télécommande |
| `42` | Perte de communication avec la télécommande |
| `43` | Pile de la télécommande faible |
| `44` | Plusieurs pannes de la télécommande |
| `50` | Panne de la sonde du caisson |
| `51` | Panne de la sonde de sortie résistance |
| `52` | Panne de la sonde d'entrée machine |
| `53` | Panne de la sonde de sortie HydroR® |
| `55` | Panne de la sonde de sortie bypass |
| `56` | Panne de la sonde bypass côté air extérieur |
| `57` | Panne de la sonde bypass côté combles |
| `5E` | Panne de la sonde de pression du filtre |
| `5F` | Plusieurs pannes de sondes |
| `61` | Erreur bypass |
| `65` | Erreur de téléchargement du logiciel |
| `70` | Erreurs multiples |
| `81` / `82` | Erreur de communication bypass |
| `83` | Volet de bypass bloqué |
| `vmc_51` | Panne de la sonde du caisson |
| `vmc_58` | Sonde du caisson gelée |

## Refaire la décompilation

L'app est écrite en Flutter : sa logique est du code Dart compilé dans `lib/arm64-v8a/libapp.so`.
[blutter](https://github.com/worawit/blutter) en reconstruit un pseudo-code lisible, avec les noms de
fonctions et le pool d'objets.

L'APK n'est pas fournie dans ce dépôt (elle appartient à son éditeur). La version utilisée :

| | |
|---|---|
| App | VMI+ `com.ventilairsec.ventilairsecinstallateur` |
| Version | 3.19.5 (version code 319051), Dart 3.5.3 |
| Source | [APKPure, versions précédentes](https://apkpure.com/vmi/com.ventilairsec.ventilairsecinstallateur/versions), XAPK |
| SHA-256 du XAPK | `d16b987f0df0723e76d98962ce78132b3b43463f37c251112993f97a7a25c411` |
| SHA-256 de `config.arm64_v8a.apk` | `c1acb2a13aa174b1de2ad433b49e40f508b2881cfe12a7570eddd983e35ca4d1` |
| SHA-256 de `libapp.so` | `97c2c6aace70cc0c6a889d12af2f27c948c056d0cb223de69f7569b5a9c6a4fa` |

Les versions récentes (3.2x) utilisent une version de Dart que blutter ne sait pas encore lire, et
blutter ne gère que les bibliothèques **arm64-v8a**, pas les `armeabi-v7a` en 32 bits.

Étapes (macOS ou Linux) :

```bash
# 1. Extraire les bibliothèques natives du XAPK (un ZIP d'APK découpées)
mkdir vmi && cd vmi
unzip ../VMI+_3.19.5_APKPure.xapk config.arm64_v8a.apk
unzip config.arm64_v8a.apk 'lib/arm64-v8a/*'
shasum -a 256 lib/arm64-v8a/libapp.so   # comparer avec le tableau ci-dessus

# 2. Installer blutter et ses dépendances
#    macOS : brew install cmake ninja pkg-config icu4c capstone
#    Debian/Ubuntu : apt install python3-pyelftools python3-requests git cmake ninja-build \
#                    build-essential pkg-config libicu-dev libcapstone-dev
git clone https://github.com/worawit/blutter
python3 -m pip install pyelftools requests

# 3. Décompiler (le premier lancement compile le runtime Dart de l'app, c'est un peu long)
python3 blutter/blutter.py lib/arm64-v8a out
```

Où regarder dans `out/` :

- `asm/ventilairsec_installateur/ventilairsec-bluetooth-connector/bluetooth_connector.dart` :
  `readMachineState` et les autres fonctions `read…` décodent chaque classe de trame.
- `pp.txt` (pool d'objets) : la table nom de commande → registre et les tables de correspondance
  (pièces, types de capteurs, types de box).
- Les fichiers de traduction de l'app (`assets/flutter_assets/assets/langs/*.json` dans l'APK de
  base) donnent les libellés des écrans et les codes d'erreur.

## Encore inconnu

1. Confirmer la commande de changement de filtre (`0x05` + mois) lors d'un vrai remplacement, et la
   façon dont l'app calcule son pourcentage FILTRE.
2. Capteurs CO₂ / Nexelec / Nanosense et préchauffage hydraulique ou solaire : décodés depuis le code
   de l'app uniquement.
3. L'emplacement des codes d'erreur dans les trames.
4. État `[3]`, `[18]`, `[36]`, `[37]`, `[39:43]`, ByPassState `[11]`, registre `0x2c` et
   notification `0x50`.
