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

L'app affiche un écran très riche (Maintenance → Available info → Equipment life) avec : jours restants de filtre, jours de fonctionnement, n° de série, saison, débit théorique, volume à ventiler, versions logicielles/matérielles. **Ces données ne sont PAS réémises en Bluetooth pendant une session normale** : capturées à 3 reprises (connexion initiale, polling en cours, navigation directe vers cet écran), aucune n'a fait apparaître de trame contenant ces valeurs (recherche ciblée de la chaîne "MUV2310129" en hexadécimal — infructueuse à chaque fois). Hypothèse la plus probable : l'app les lit une fois au tout premier appairage (avant nos captures) et les met en cache localement (SQLite/SharedPreferences), plutôt que de les relire à chaque connexion. Pour les capturer, il faudrait vider les données de l'app (ou la réinstaller) et recapturer *exactement* la toute première connexion — pas tenté ici (destructif pour l'app installée, risque de perdre la configuration).

## Écran "Diagnostic" (autotest)

Maintenance → Available info → Diagnostic affiche 4 autotests (IAQ Sensor, Motor, Pre-heating, Probes), tous ✓ verts sur notre appareil. Registre/notification déclencheur non identifié — écran non instrumenté (pas de test en échec disponible pour observer le format d'une erreur de toute façon).

## "Vision'R"

Chaîne trouvée dans le binaire de l'app, dont le rôle n'était pas clair au départ. Confirmé par recherche externe : **"Vision'R" est le nom commercial du système de gestion/pilotage** que Ventilairsec utilise pour ses gammes **Urban** et **Cube** (cf. "Gestion Urban et Cube Vision'R avec boîtier" sur la boutique officielle) — ce n'est pas un modèle d'appareil distinct. La centrale "Urban" de l'utilisateur *est* un système Vision'R : aucune intégration ni registre séparé n'est donc nécessaire, `vmi_plus` la couvre déjà.

## Ce qui reste à faire

1. ~~Confirmer la sémantique d'écriture du registre `0x0b`~~ → confirmé bascule (toggle), voir type `0x01` ci-dessus. Exposé en `switch` avec écriture conditionnelle (ne bascule que si l'état diffère de l'état demandé).
2. ~~Localiser le registre de Holiday mode~~ → trouvé, `0x1a`, ON et OFF confirmés (voir table ci-dessus), exposé en `switch`. ~~Reste à localiser le registre du nombre de jours~~ → confirmé que ce nombre n'est **jamais transmis en Bluetooth** (une seule trame d'écriture observée en activant Holiday avec jours=1), purement local à l'app. "Boost mode 30 min" de l'écran Special modes est confirmé (par l'utilisateur, et par capture : offset `[44]`) être le même contrôle que le bouton Boost du Dashboard principal — déjà couvert par `switch.*_boost` (registre `0x19`), rien à faire de plus ici. **Fixed air flow rate mode** et **Activating time slots** (Configuration) résistent tous les deux à un simple tap sur leur toggle — aucun changement visuel après plusieurs tentatives, alors que Holiday/Night boost/Boost réagissent immédiatement au même geste. Hypothèse : ces deux modes nécessitent de renseigner une donnée associée (un débit cible en m³/h pour le premier, des horaires pour le second) avant que le toggle n'accepte de s'activer — pas creusé plus loin (nécessiterait de configurer une valeur réelle sur la centrale de l'utilisateur sans supervision, risqué).
3. Localiser le **% de filtre** et les **numéros de série**. Nouveau : le dashboard principal de l'app affiche en fait une jauge "FILTER" (pourcentage) en permanence, pas seulement l'écran "Equipment life" — donc potentiellement transmise en direct dans la trame de statut type `0x01`, contrairement à l'hypothèse initiale (offset non identifié, à chercher en comparant deux centrales avec un niveau de filtre différent, ou avant/après un `RESET` filtre). Les numéros de série (cf. section "Equipment life") nécessitent toujours de capturer un tout premier appairage.
4. Décoder le tableau de 10 blocs du type `0x02` (historique horaire ?) — sur plusieurs captures espacées de quelques minutes à quelques heures, ce tableau est resté strictement identique (blocs à `0xff` suivis de zéros), cohérent avec une granularité horaire/journalière qui n'a pas eu l'occasion de changer pendant nos fenêtres de capture.
5. ~~Vérifier si offset `[34]` du type `0x01` encode bien la vitesse~~ → confirmé (voir table ci-dessus).
6. **Famille EXTRACTOR** (UUID différents, non capturés ici) — hors scope pour ce projet, l'utilisateur ne possède pas ce type d'appareil. Reste valable pour un futur contributeur qui en aurait un.
7. ~~Vérifier si les handles ATT (`0x0013`/`0x000e`) sont stables entre reconnexions~~ → confirmé stables sur 12 (re)connexions réelles indépendantes, réparties sur plus de 21h de capture. La résolution par UUID reste conservée dans le code (plus robuste, coût nul).
8. **Nouveau** — trame d'écriture non documentée envoyée une fois par connexion, juste après le registre `0x2c` : classe `0x1a` (même préfixe que le registre Holiday mais framing différent, proche de celui des notifications : `A5 B6 1a 06 06 [6 octets payload] [crc]`). Deux échantillons capturés à ~21h d'intervalle réel : `1a081a0c1f38` puis `1a081b093823`. Hypothèse (non confirmée) — synchronisation de l'horloge de la centrale sur celle du téléphone : `[mois][jour][heure][minute][seconde]` après un premier octet constant `0x1a` (le jour passe de `0x1a`=26 à `0x1b`=27 entre les deux captures, cohérent avec le passage à minuit réel). Sans effet observé sur le reste du protocole — à confirmer si besoin en comparant avec l'heure système du téléphone au moment exact de la capture.
