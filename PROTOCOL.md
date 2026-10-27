# Protocole BLE de la centrale VMI+ (Ventilairsec) — rétro-ingénierie

Reversé à partir de :
- Décompilation partielle de l'app Android **VMI+** v3.21.14 (`com.ventilairsec.ventilairsecinstallateur`, Flutter/Dart, utilise le plugin `flutter_blue_plus`)
- Capture Bluetooth HCI snoop en conditions réelles (Pixel Fold, Android 17) contre une centrale **VMCI "Urban"** (MAC `00:A0:50:3A:18:23`), les 2026-08-26 et 2026-08-27 (`adb bugreport` + analyse `tshark`, changement d'un seul réglage à la fois pour isoler chaque offset par diff)

Statut : **le canal de commande (vitesse/boost/bypass/holiday/mode nuit) et le canal de télémétrie (température/humidité des deux sondes + statut complet vitesse/boost/bypass/holiday/mode nuit) sont entièrement vérifiés contre le matériel réel.**

## Connexion

- Bluetooth Low Energy standard, **sans appairage/chiffrement** (aucun échange SMP observé dans la capture — GATT en clair).
- Découverte : filtrer sur le nom annoncé (ex. `"Urban"`) ou sur l'UUID de service ci-dessous.
- Une seule connexion GATT centrale à la fois (déconnecter l'app officielle si elle est déjà connectée).
- L'app officielle demande de scanner un QR code sur la centrale à la toute première connexion. Vu l'absence totale de pairing/chiffrement BLE confirmée ci-dessus, ce n'est très probablement **pas** un mécanisme de sécurité du protocole — plus vraisemblablement un raccourci pour renseigner automatiquement l'adresse MAC/n° de série dans l'app (évite la saisie manuelle) et/ou associer la centrale au compte de l'installateur côté app. Sans effet sur `vmi_plus`, qui connaît déjà l'adresse MAC directement (découverte Bluetooth ou saisie manuelle) — aucun scan requis.

## Services et caractéristiques (famille VMCI)

Deux services custom coexistent avec les services BLE standards (Generic Access `1800`, Generic Attribute `1801`) :

| Rôle | Service UUID | Characteristic UUID | Propriétés |
|---|---|---|---|
| **Contrôle** (écriture des commandes) | `0003cbbb-0000-1000-8000-00805f9b0131` | `0003cbb1-0000-1000-8000-00805f9b0131` | Read, Write (with response), Notify |
| **Télémétrie** (état poussé par l'appareil) | `0003cab5-0000-1000-8000-00805f9b0131` | `0003caa2-0000-1000-8000-00805f9b0131` | Notify |

> Note : l'app contient aussi une autre famille d'UUID (`7c4adc01`…`7c4adc07-2f33-11e7-93ae-92361f002671`), non observée dans cette capture — probablement utilisée par une autre gamme d'appareil (ex. la famille **EXTRACTOR**, non testée).

Dans la capture, ces caractéristiques sont apparues aux handles ATT `0x0013` (contrôle) et `0x000e` (télémétrie) — bleak accepte soit l'UUID soit le handle entier directement.

## Trame de commande (canal contrôle)

Toutes les commandes observées suivent un format fixe de 11 octets :

```
A5 B6 10 06 05 [REG] 00 00 00 [VAL] [CRC]
 └magic─┘ └hdr┘ len  reg  reserved  val  checksum
```

- `A5 B6` : constante magique de début de trame
- `10 06` : constante (classe de commande "écriture/lecture registre")
- `05` : longueur du payload utile qui suit (5 octets : `REG 00 00 00 VAL`)
- `REG` : numéro de registre (voir tableau ci-dessous)
- `00 00 00` : réservé, toujours nul dans nos échantillons
- `VAL` : valeur à écrire dans le registre
- `CRC` : checksum sur les 10 octets précédents (voir algorithme ci-dessous)

Écriture : GATT **Write Request** (avec accusé de réception) sur la caractéristique de contrôle.

### Registres identifiés (confirmés par test direct sur l'appareil)

| Registre | Fonction | Valeurs observées |
|---|---|---|
| `0x18` | Vitesse de ventilation | `0x00`=vitesse 1, `0x01`=vitesse 2, `0x02`=vitesse 3 |
| `0x19` | Boost (surventilation 30 min) | `0x00`=off, `0x01`=on |
| `0x2f` | Bypass (contourne l'échangeur pour faire entrer l'air extérieur/une source chaude directement — utile en hiver pour préchauffer gratuitement, confirmé par l'utilisateur) | `0x00`=off, `0x01`=on |
| `0x1a` | Holiday mode (écran Special modes, absence prolongée) | `0x00`=off, `0x01`=on — **les deux confirmés par capture réelle**. Le nombre de jours saisi dans l'app n'est **jamais transmis en Bluetooth** (vérifié : une seule trame d'écriture, juste l'interrupteur) — purement local à l'app |
| `0x0b` | Mode nuit (Night ventilation boost, écran Special modes) | Pas de valeur explicite : chaque écriture (toujours `0x00`) **bascule** l'état courant plutôt que de l'imposer — confirmé par 3 bascules réelles indépendantes (A→B→A à chaque fois), voir section Télémétrie ci-dessous |
| `0x03` | Déclenche une notification **type `0x01`** (statut général : vitesse/boost/bypass, cf. ci-dessus) | — (lecture) |
| `0x06` | Déclenche une notification **type `0x02`** (sonde télécommande/pièce ventilée, ex. Bathroom 1) | — (lecture) |
| `0x07` | Déclenche une notification **type `0x03`** (sonde interne "Probe N°1", ex. sortie résistance) | — (lecture) |
| `0x2c` | Vu une fois pendant la séquence d'initialisation (rôle non déterminé) | — |

Ces trois registres de lecture sont polés en boucle par l'app selon l'écran affiché (ex. le Dashboard poll `0x03`+`0x06`, l'écran "Instantaneous measurements" poll `0x07`+`0x06`) — dans les faits, écrire les trois en rotation toutes les ~10s suffit à obtenir un flux complet et continu.

### Algorithme du checksum (CRC)

Vérifié sur 11 trames de commande réelles capturées (correspondance exacte à 100%) :

```python
def checksum(data_10_bytes: bytes) -> int:
    crc = 0
    for byte in data_10_bytes:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 1) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ 0x13

def build_frame(register: int, value: int) -> bytes:
    data = bytes([0xA5, 0xB6, 0x10, 0x06, 0x05, register, 0, 0, 0, value])
    return data + bytes([checksum(data)])
```

Exemples vérifiés (capturés réellement sur l'appareil) :

| Commande | Trame hex |
|---|---|
| Vitesse 1 | `a5b610060518000000000b` |
| Vitesse 2 | `a5b610060518000000010a` |
| Vitesse 3 | `a5b6100605180000000209` |
| Boost ON | `a5b610060519000000010b` |
| Boost OFF | `a5b610060519000000000a` |
| Bypass ON | `a5b61006052f000000013d` |
| Bypass OFF | `a5b61006052f000000003c` |

## Télémétrie (canal notify)

L'appareil pousse des notifications sur la caractéristique télémétrie (handle `0x000e` dans nos captures), toutes préfixées `A5 B6`, avec un octet de **type** en position `[2]` qui indique le format du reste de la trame :

### Type `0x01` — statut général (déclenché par écriture registre `0x03` **ou `0x0b`**)

Trame la plus riche (longueur `0x37`=55 octets de payload, cf. structure générale ci-dessus) : contient l'état vitesse/boost/bypass ainsi que les modes spéciaux (Holiday/Boost-30min/Night boost, écran "Special modes" de l'app). Le registre `0x0b` (déclenché en ouvrant l'écran Special modes, ou en basculant le mode nuit) renvoie **exactement la même trame** que `0x03` — probablement un alias/sur-ensemble du statut général plutôt qu'un registre dédié.

Tous les champs ci-dessous ont été confirmés le 2026-08-27 par une méthode systématique : changer un seul réglage à la fois depuis l'app (capture Bluetooth HCI snoop + `adb bugreport`, analysée avec `tshark`), et differ octet par octet la trame de statut juste avant/après. `protocol.py` (`parse_notification`) les décode tous :

| Offset | Champ | Valeurs observées |
|---|---|---|
| `[33]` | Mode nuit (Night ventilation boost) actif | `0x00`=activé, `0x01`=désactivé (logique inversée) — 3 bascules réelles indépendantes, toujours cohérent |
| `[34]` | Vitesse active | `0x00`/`0x01`/`0x02` = Faible/Moyenne/Forte, confirmé en changeant les 3 vitesses pendant une capture |
| `[43]` | Holiday mode actif | `0x00`=off, `0x01`=on |
| `[44]` | Boost (surventilation 30 min) actif | `0x00`=off, `0x01`=on |
| `[53]` | Bypass actif | `0x00`=off, `0x01`=on |

Champs corrélés mais non exposés (redondants ou pas assez fiables pour être utiles) :

- `[32]` corrèle avec la vitesse (`0x07`/`0x09`/`0x0b` pour Faible/Moyenne/Forte, = `7 + 2×vitesse`) — rôle exact inconnu, ignoré au profit de `[34]`.
- `[35]` corrèle avec Bypass (`0x00`=off, `0x12`=on) — même info que `[53]` sous une autre forme (peut-être une durée/pourcentage plutôt qu'un booléen pur), ignoré au profit de `[53]`.
- `[47:49]` (little-endian) change avec la vitesse : `0x0168`=360, `0x01c2`=450, `0x0226`=550 — probablement le débit théorique en m³/h pour chaque vitesse (configuré par l'installateur, cf. écran "Equipment life"), non exposé car non essentiel et pas revérifié sur une autre centrale.

Byte de fin (offset `[60]` dans nos échantillons) : compteur/checksum roulant qui change à quasi chaque notification, sans lien apparent avec l'état — ignoré.

**Registre `0x0b` (mode nuit) : confirmé comme bascule (toggle), pas une valeur explicite.** Sur 3 bascules réelles indépendantes (deux dans cette session, une observée dans l'historique du snoop log), la trame envoyée vers l'appareil est **systématiquement identique** (`a5b61006050b0000000018`, valeur toujours `0x00`) quel que soit le sens du changement — c'est bien la relecture du champ `[33]` après coup qui montre que l'état a basculé dans l'un ou l'autre sens. Contrairement à `0x18`/`0x19`/`0x2f`/`0x1a` qui imposent une valeur explicite, ce registre suit donc un modèle différent. Exposé côté Home Assistant en `switch` (`REG_NIGHT_BOOST_TOGGLE`), qui ne déclenche une écriture que si l'état actuellement connu diffère de l'état demandé (pour éviter d'inverser par erreur si l'entité est appelée alors que l'état est déjà bon).

**Holiday mode et nombre de jours** : en activant Holiday avec l'app (jours=`1`, confirmé via le bouton ✓ du clavier numérique), une **seule** trame d'écriture a été observée : `a5b61006051a0000000108` (registre `0x1a`, valeur `0x01`). Aucune autre trame contenant le nombre de jours n'apparaît dans la capture — cette valeur est donc purement locale à l'app (affichage/rappel), sans effet sur la centrale. `switch.*_holiday` côté Home Assistant couvre donc déjà 100% du comportement réel du Bluetooth pour ce mode.

### Type `0x03` — sonde interne "Probe N°1" (déclenché par écriture registre `0x07`)

Vérifié par correspondance exacte avec l'écran "Instantaneous measurements → Internal equipment → Probe N°1" de l'app (capturé deux fois, avec une variation d'humidité 56%→57% qui confirme une vraie lecture live) :

| Offset | Champ | Exemple observé |
|---|---|---|
| `[6]` | Température (°C, uint8) | `28` |
| `[8]` | Humidité (%, uint8) | `56` |

Position affichée par l'app pour cette sonde : "Resistor outlet" (sortie résistance de préchauffage). Numéro de série vu à l'écran : `1` (pas encore localisé dans la trame).

### Type `0x02` — sonde télécommande / pièce ventilée (déclenché par écriture registre `0x06`)

Vérifié de la même façon, correspond à l'écran "Instantaneous measurements → Ventilated space → Remote control" (pièce "Bathroom 1" dans notre test) :

| Offset | Champ | Exemple observé |
|---|---|---|
| `[11]` | Température (°C, uint8) | `24` |
| `[13]` | Humidité (%, uint8) | `74` |

Numéro de série vu à l'écran : `04249B00` (pas encore localisé dans la trame). Le reste de la trame (10 blocs de 9 octets, chacun commençant par `0xff`) ressemble à un tableau/historique non décodé — peut-être un relevé horaire.

### Type `0x50` et `0x23`

Vus une fois chacun à la connexion initiale, contenu non décodé (probablement des accusés de réception ou des méta-données de session).

## Écran "Equipment life" / "General info" (filtre, n° de série, versions...)

> **Superseded (2026-10-27):** all these values are in the status frame, see "The app's own decoder" below. The text of this section is kept for history.

L'app affiche un écran très riche (Maintenance → Available info → Equipment life) avec : jours restants de filtre, jours de fonctionnement, n° de série, saison, débit théorique, volume à ventiler, versions logicielles/matérielles. **Ces données ne sont PAS réémises en Bluetooth pendant une session normale** : capturées à 3 reprises (connexion initiale, polling en cours, navigation directe vers cet écran), aucune n'a fait apparaître de trame contenant ces valeurs (recherche ciblée de la chaîne "MUV2310129" en hexadécimal — infructueuse à chaque fois). Hypothèse la plus probable : l'app les lit une fois au tout premier appairage (avant nos captures) et les met en cache localement (SQLite/SharedPreferences), plutôt que de les relire à chaque connexion. Pour les capturer, il faudrait vider les données de l'app (ou la réinstaller) et recapturer *exactement* la toute première connexion — pas tenté ici (destructif pour l'app installée, risque de perdre la configuration).

## Écran "Diagnostic" (autotest)

Maintenance → Available info → Diagnostic affiche 4 autotests (IAQ Sensor, Motor, Pre-heating, Probes), tous ✓ verts sur notre appareil. Registre/notification déclencheur non identifié — écran non instrumenté (pas de test en échec disponible pour observer le format d'une erreur de toute façon).

## "Vision'R"

Chaîne trouvée dans le binaire de l'app, dont le rôle n'était pas clair au départ. Confirmé par recherche externe : **"Vision'R" est le nom commercial du système de gestion/pilotage** que Ventilairsec utilise pour ses gammes **Urban** et **Cube** (cf. "Gestion Urban et Cube Vision'R avec boîtier" sur la boutique officielle) — ce n'est pas un modèle d'appareil distinct. La centrale "Urban" de l'utilisateur *est* un système Vision'R : aucune intégration ni registre séparé n'est donc nécessaire, `vmi_plus` la couvre déjà.

## 2026-10-27 capture (app v3.23.19, firmware 6.4.002)

New capture (phone HCI snoop + direct reads from a Raspberry Pi with bleak), reading the app's
"Equipment life" screen side by side with the raw frames:

- **Equipment life values do come from the type `0x01` status frame**, not from a one-time cached
  read. Opening that screen sends no extra register write. Confirmed offset:
  - `[26:28]` little-endian uint16 = **operating days** (`3c 04` = 1084, exact match with the app).
    Exposed as `sensor.*_jours_de_fonctionnement`.
- Candidate offsets (single-byte matches, not yet confirmed by a diff):
  - `[22]` = `0xc8` = 200 → "Volume to ventilate : 200 m³".
  - `[38]` = `0x18` = 24 → "Max. supply air temp. : 24 °C".
  - `[28:30]` = `00 00` → maybe "Filter life : 0 days" (the app shows FILTER 0 %, "to be
    replaced"). Can only be confirmed by capturing before/after a filter RESET.
- Type `0x02`: `[5:9]` little-endian = remote control serial (`00 9b 24 04` → `04249B00`, matches
  the app).
- Write frame `A5 B6 1A 06 06 ...` is **confirmed as a clock sync**: payload
  `1a 0a 1b 0f 32 01` = 2026-10-27 15:50:01 (`[yy][mm][dd][hh][mm][ss]`), sent at that exact time.
- The first write of a session is `a5b6100005030000000016` (class `10 00` instead of `10 06`),
  then the usual `0x2c`, `0x03`, `0x06`, `0x07` polling.
- **Register `0x17` = summer supply-air limit (°C)**, confirmed by changing it in the app
  (24 → 26 → 24 °C, frames `a5b6100605170000001a1e` / `a5b610060517000000181c`). Read back at status
  offset `[38]`. Exposed as `number.*_limite_temperature_ete` (22–35 °C, like the app).
- **Register `0x1c` = preheat target (°C), `0` = no preheating**, confirmed by changing it in the
  app: 18 → 16 → "no preheating" (`0`) → "Mini" (`12`) → 18. Read back at status offset `[35]`.
  Exposed as `number.*_temperature_de_prechauffage` (12–18 °C, like the app).
  - Status `[53]` (so far called "bypass") dropped to `0` when "no preheating" was chosen and came
    back to `1` with any temperature: register `0x2f` is the app's **preheat button** (heat-wave
    icon on the home screen), not a heat-exchanger bypass. The HA switch is renamed "Préchauffage"
    (entity_id unchanged).
  - Status `[36]` went `0x14` (18/16 °C) → `0x00` (off, and also at 12 °C). Unknown, maybe the
    current heating demand.
- The "Theoretical air flow" slider of "Simplified configuration" is a 3-position slider that
  writes the **speed register `0x18`** (moved by hand to the lowest position: `a5b610060518000000000b`,
  the app then showed 72 m³/h instead of 90). So status `[47:49]` (360/450/550) is the theoretical
  air flow in **1/5 m³/h**: 72/90/110 m³/h for Faible/Moyenne/Forte. Exposed as
  `sensor.*_debit_theorique`. (adb-injected gestures are ignored by this slider.)
- Opening every Configuration / Maintenance / Sensor management screen sends **no extra read**: the
  app builds all of them from the status frame (`0x01`) and the probe frames. So everything the app
  shows is in those frames.
- The last byte of the status frame (`[60]`) is a checksum of the frame, not a rolling counter: it
  changes only when the content changes (`c7` → `c5` when `[38]` went from 24 to 26).
- The earlier "candidate offsets" are now all resolved by the app's own decoder, see the next
  section.
- Maintenance → History does not read anything over BLE: it asks for an e-mail address and the
  history is sent by the vendor's cloud.

## The app's own decoder (app 3.19.5, decompiled)

The app 3.19.5 (Dart 3.5.3, from APKPure) was decompiled with
[blutter](https://github.com/worawit/blutter). The current app (3.23.x) is built with a Dart version
blutter cannot read yet. Offsets below are indexes in the raw notification, header included
(`[0]`=`a5`, `[1]`=`b6`, `[2]`=frame type). Values checked against our 2026-10-27 frame and the
app's screens are marked ✓.

### Frame classes (byte `[2]`)

App → unit: `0x10` Command, `0x11` Setting, `0x12` Config, `0x13` ConfigSensors, `0x15` ConfigErp,
`0x17` ConfigByPass, `0x19` ConfigTimeSlot, `0x1a` UpdateDate (clock sync ✓), `0x20` NewUpdate,
`0x21` Update, `0x22` UpdateAckData.

Unit → app: `0x01` State ✓, `0x02` SensorsState ✓, `0x03` ProbesState ✓, `0x04` SimpleData,
`0x05` TimeSlotState, `0x16` ErpState, `0x18` ByPassState, `0x1b` AutoTestDatas, `0x23` AckData,
`0x30` Csv, `0x31` Histo, `0xff` Nack.

### Command registers (class `0x10`, `A5 B6 10 06 05 [REG] 00 00 00 [VAL] [CRC]`)

| Reg | App name | Notes |
|---|---|---|
| `0x01` | Test | |
| `0x02` | Localisation | LED blink (find the unit) ✓ |
| `0x03` | State | read → State frame ✓ |
| `0x04` | Update | firmware update |
| `0x05` | NewFilter | filter changed, payload = interval (6/12 months). **Resets the filter counter.** |
| `0x06` | Sensors | read → SensorsState ✓ |
| `0x07` | Probes | read → ProbesState ✓ |
| `0x09` / `0x22` / `0x21` / `0x20` | StartCsv / StartCsvV2 / StopCSV / CsvLength | history export |
| `0x0a` / `0x1f` | Old/NewSerialisation | |
| `0x0b` | Surventilation | night ventilation boost ✓ (toggle) |
| `0x0d` | Calibration | |
| `0x10` | DeleteSensor | |
| `0x12` | ErpState | |
| `0x13` | Reset | **factory reset, never send** |
| `0x14` / `0x15` | ByPass / ByPassForced | `0x14` = read ByPassState ✓ |
| `0x16` / `0x23` | AutoTest / AutoTestDatas | Diagnostic screen |
| `0x17` | Tmax | summer limit ✓ |
| `0x18` | Mode | speed ✓ |
| `0x19` | Boost | ✓ |
| `0x1a` | Hollidays | ✓ (app 3.19.5 sent the number of days as value; the current app sends 1/0) |
| `0x1b` | FixedFlow | fixed air flow (radon) mode, 1/0 ✓ (status `[45]`) |
| `0x1c` | Temp | preheat target ✓ |
| `0x1d` | TimeSlot | time slots on/off ✓ (status `[46]`, answers TimeSlotState) |
| `0x1e` | TempElec | |
| `0x24` / `0x25` | GeoVersion / ElecVersion | |
| `0xf9`–`0xff` | Sav7…Sav1 | after-sales actions (work code) |

`0x2c` and `0x2f` (sent by the newer app) are not in the 3.19.5 table.

### State frame (`0x01`) fields

| Offset | App key | Our frame | Meaning |
|---|---|---|---|
| `[3]` | — | `06` | used for a version check |
| `[5:9]` LE, hex | machineId | `22310129` | serial number, the app shows `MUV2310129` ✓ |
| `[9]` | — | `00` | diagnostic "in progress" flag |
| `[10]` bits | testStatus | `1f` | 5 self-test result bits |
| `[11]`–`[14]` | probe / preheat / engine / qai | `ff` ×4 | per-test detail (Diagnostic screen) |
| `[15]` | gtcEnabled | `00` | building management (GTC) |
| `[16]` | calibration | `01` | |
| `[17]` | nbPersons / surface | `28` | surface = value × 2 m² (80 m²) |
| `[18]` | height / flowPerPerson | `32` | |
| `[19]` | box | `02` | 1 Purevent, 2 Urban ✓, 3 PRO, 5 Cube |
| `[20]` | softwareVersion | `64` | `6.4` + `[49]` → `6.4.002` ✓ |
| `[21]` | elec | `11` | electronic version (high nibble) + software version (low nibble), app shows 1 / 1 ✓ |
| `[22:24]` LE | ventilateVolume | `200` | m³ ✓ |
| `[24]` | preheatType / hasHydro | `01` | electric ✓ |
| `[25]` | bypass | `00` | real heat-exchanger bypass state |
| `[26:28]` LE | upTime | `1084` | operating days ✓ |
| `[28:30]` LE | autonomy | `0` | remaining filter life in days ✓ (max 360) |
| `[32]` | theoreticalFlow | `09` | ×10 m³/h (older app); newer app uses `[47:49]`/5 ✓ |
| `[33]` | surventilation | `00` | night boost, inverted ✓ |
| `[34]` | mode | `01` | speed ✓ |
| `[35]` | tempElec | `12` | preheat target ✓ |
| `[36]` | tempHydro | `14` | hydraulic preheat target (unused here) |
| `[37]` bits | boxDefined | `05` | |
| `[38]` | tempBlowing | `18` | summer limit ✓ |
| `[39:43]` LE | date | `0b161db1` | |
| `[43]` | hollidaysMode | `00` | ✓ |
| `[44]` | boost | `00` | ✓ |
| `[45]` | fixedFlow | `00` | fixed air flow mode |
| `[46]` | timeSlot | `00` | time slots on/off |
| `[49]` | (version patch) | `02` | |
| `[50]` | meca | `01` | mechanical version ✓ |
| `[51]` | season | `02` | 0 summer, 1 winter, 2 intermediate ✓ |
| `[52]` | turbo_heater | `00` | "turbo heat: No" ✓ |
| `[53]` | (newer app) | `01` | preheat button state, register `0x2f` ✓ |

Since v0.7.0, `[22:24]` (volume), `[17]` (surface), `[24]` (preheat type), `[52]` (turbo heat),
`[15]` (GTC) and `[9]` (action in progress) are also exposed in Home Assistant as diagnostic
entities.

### Generic frame format

Every frame in both directions is `A5 B6 [class] 06 [len] [payload…] [crc]`, with the same CRC as
the command frames computed over everything before it (checked on State, UpdateDate and Command
frames). Commands are class `0x10` with a 5-byte payload `[REG, 0, 0, 0, VAL]`. The very first
write of a session uses `10 00` instead of `10 06` (`a5b6100005030000000016`).

### SensorsState (`0x02`, answer to register `0x06`)

Up to 10 wireless sensors, 10 bytes each from offset 5 (app's `readSensorsData`):

| Byte | Meaning |
|---|---|
| `+0..+3` LE | sensor id (hex, `04249B00` for our remote control) |
| `+4` | room: 0 unknown, 1 living, 2 kitchen, 3 bathroom 1, 4 bathroom 2, 5–8 bedroom 1–4, 9 cellar |
| `+5` | kind: 0 absent, 1 Nexelec CO₂, 2 Nexelec temperature, 3 remote control ("assistant"), 4 box, 5 Nanosense |
| `+6..+7` | CO₂ sensors: CO₂ ppm (LE uint16). Others: `+6` = temperature (°C, ≥128 means negative: value − 255) |
| `+8` | humidity (%) |
| `+9` | third value (`dataC`, 0 on our remote) |

The id prefix tells the app the sensor model when pairing: `I420` CO₂, `I880` temperature,
`ASI ` / `SNE ` remote control.

### ProbesState (`0x03`, answer to register `0x07`)

Up to 5 wired probes, 5 bytes each from offset 5: `[location, temperature (signed), ?, humidity, ?]`.
Our unit has one probe ("Probe n°1 – Resistor outlet"), the 4 other slots read location `0x08`.

### TimeSlotState (`0x05`) and ConfigTimeSlot (`0x19`)

- Register `0x1d` = time slots on (1) / off (0), status `[46]`. The unit always answers with a
  TimeSlotState frame. Turning it on applies the schedule at once: with an empty schedule our unit
  dropped to Faible (we set Moyenne back afterwards).
- TimeSlotState: `[5]` = enabled, then 7 days × 5 slots × `[start hour, speed, temp]` from offset 6.
  `start = 0xff` means an empty slot. Speed is 0/1/2 (Faible/Moyenne/Forte).
- ConfigTimeSlot (app → unit), one frame per day: payload `[day 1–7, (start, speed + 1, temp) × 5]`,
  empty slot `ff 00 00`. **The unit stores the speed byte minus one**: the app sends 1/2/3, the state
  frame reports 0/1/2. Verified on the device: Monday written with a slot at 07 h speed 2, read
  back `07 01 ff`, then restored to `ff 00 00` ×5 (read back `ff ff 00`, identical to before).
- `temp` is the preheat setpoint of the slot (the app offers the same list as the preheat target,
  plus "elec+" / "hydro" on units that have them).

### ByPassState (`0x18`, answer to register `0x14`)

| Offset | App key | Our unit |
|---|---|---|
| `[5]` | position (%) | 100 |
| `[6]` | type | 0 |
| `[8]` | temp (°C) | 28 |
| `[11]` | (hex) | `ff` |
| `[17:21]` LE | id | 0 |
| `[21]` | forced | 0 |
| `[22]` | ask_position (%) | 100 |

Register `0x15` (ByPassForced) forces the bypass; the installer settings are sent with a
ConfigByPass frame (`0x17`: bypass_temp, bypass_type, bypass_id).

### ErpState (`0x16`, answer to register `0x12`)

GTC / Modbus settings: `[5]` mode, `[6]` slave address, `[7]` baud rate, `[8]` parity, `[9]` stop
bit. Our unit (no GTC) does not answer. Written with ConfigErp (`0x15`): nb_persons,
debit_per_person, elec_temp, gtc_slaveAdress, gtc_baudrate, gtc_mode, gtc_parity, gtc_stopBit, then
the date (`yy mm dd hh mi ss`).

### Installer configuration (Config `0x12`)

Sent by the installation wizard, 18 bytes in this order: volume (2 bytes), box type, bypass_type,
filterLifespan (months), mode, elec_temp, blowing_temp (summer limit), hydro_temp, 0, then the date
(`yy mm dd hh mi ss`), surface, height. Not exposed in Home Assistant (it rewrites the whole
installation).

### Other functions (documented, not exposed)

- **Clock sync** (UpdateDate `0x1a`): `[yy, mm, dd, hh, mi, ss]`, sent by the app on every
  connection.
- **Locate** (register `0x02`): LED blink; the status frame then reports `[9] = 1` while it runs.
  Exposed as a button.
- **Filter change** (register `0x05`, value = 6 or 12 months): from the app's code (both call sites
  pass the number of months). Exposed as two buttons; not sent on our unit yet (filter to be
  replaced soon, the first real use will confirm it).
- **Self-test** (AutoTest `0x16` / AutoTestDatas `0x23` → frame `0x1b`): the Diagnostic screen of
  the current app only shows the status bits `[10]`–`[14]`, it does not start a test.
- **History** (Maintenance → History): StartCsv `0x09` / StartCsvV2 `0x22`, CsvLength `0x20`,
  StopCSV `0x21`; the unit streams Csv (`0x30`) and Histo (`0x31`) frames that the app turns into a
  CSV file and e-mails through the vendor's cloud. Not needed in Home Assistant.
- **Firmware update** (Update `0x04`, NewUpdate `0x20`, Update `0x21`, UpdateAckData `0x22`): the app
  downloads the firmware from Firebase and sends it in packets. Never send this by hand.
- **Factory reset** (Reset `0x13`), **calibration** (`0x0d`), **sensor pairing / removal**
  (ConfigSensors `0x13`, DeleteSensor `0x10`), **serialisation** (`0x0a` / `0x1f`) and
  **after-sales work codes** (Sav1–Sav7 = `0xff`…`0xf9`): installer / after-sales only.
- Newer app only: register `0x2c` (sent once per connection), register `0x2f` (preheat button) and
  notification `0x50` (`…59…` at offset 19, content unknown).

### After-sales menu (current app 3.23.x)

Maintenance → "Action by the after-sales service" asks for a work code, then offers (labels from
the app's translation files): reset factory settings, force machine update, force MEV firmware
(VMC-E), force PIV firmware (VMC-I), force install, "password cycle", "password N6", and declare an
after-sales case (report link). They are part of the production build. Each one ends up as one of
the Sav1–Sav7 command registers (`0xff`…`0xf9`) and the unit restarts and disconnects. Which work
code unlocks which option, and whether codes are checked online, is in the part of the current app
blutter cannot decompile. The 3.19.5 app had no code at all: buttons "Command 1"…"Command 7" plus
"Force install". **Never send these registers.**

### Error codes known by the app

From the app's translation files (`error_code_XX`); where the code travels in the frames is not
located yet (no fault on our unit).

| Code | Meaning |
|---|---|
| `01` | Resistor failure |
| `02` | Preheating cannot be used to reach the setpoint temperature |
| `10` | Motor failure |
| `20` | Replace filter |
| `30` | IAQ sensor failure |
| `31` | IAQ sensor no. 1 failure |
| `32` | IAQ sensor no. 2 failure |
| `33` | IAQ sensor no. 3 failure |
| `34` | IAQ sensor no. 4 failure |
| `35` | IAQ sensor no. 5 failure |
| `36` | IAQ sensor no. 6 failure |
| `37` | IAQ sensor no. 7 failure |
| `38` | IAQ sensor no. 8 failure |
| `39` | IAQ sensor no. 9 failure |
| `3A` | Problem with several IAQ sensors |
| `3B` | Pairing problem for an IAQ sensor |
| `40` | Unknown problem with the remote control. |
| `41` | Remote control temperature error. |
| `42` | Loss of remote control communication. |
| `43` | Remote control low battery. |
| `44` | Multiple remote control failures. |
| `50` | Probe failure in the housing unit |
| `51` | Resistor outlet probe failure |
| `52` | Machine inlet probe failure |
| `53` | HydroR® outlet probe failure |
| `55` | Bypass outlet probe failure |
| `56` | Bypass external air side probe failure |
| `57` | Bypass roof space side probe failure |
| `5E` | Filter pressure probe failures |
| `5F` | Several probe failures |
| `61` | Bypass error |
| `65` | Software download error |
| `70` | Multiple errors |
| `81` | Bypass communications error |
| `82` | Bypass communications error |
| `83` | Blocked Bypass damper |
| `vmc_51` | Housing unit probe failure |
| `vmc_58` | Housing unit probe frozen |

## Ce qui reste à faire

Everything the app does for a private customer is decoded and available in Home Assistant (see the
README table). What is left can only be checked on other hardware or at a specific moment:

1. Confirm the filter change command (`0x05` + months) the day the filter is replaced, and how the
   app computes the FILTER % (days left / lifespan).
2. CO₂ / Nexelec / Nanosense sensors and hydraulic or solar preheating: decoded from the app's code,
   but our unit has none of them.
3. Where the error codes above appear in the frames (needs a unit with a fault).
4. Meaning of a few bytes the app reads but never displays: status `[3]`, `[18]`, `[36]`,
   `[39:43]` ("date"), ByPassState `[11]`, notification `0x50`.
