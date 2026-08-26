# Protocole BLE de la centrale VMI+ (Ventilairsec) — rétro-ingénierie

Reversé à partir de :
- Décompilation partielle de l'app Android **VMI+** v3.21.14 (`com.ventilairsec.ventilairsecinstallateur`, Flutter/Dart, utilise le plugin `flutter_blue_plus`)
- Capture Bluetooth HCI snoop en conditions réelles (Pixel Fold, Android 17) contre une centrale **VMCI "Urban"** (MAC `00:A0:50:3A:18:23`), le 2026-08-26

Statut : **le canal de commande (contrôle vitesse/boost/bypass) et une partie du canal de télémétrie (température/humidité des deux sondes) sont entièrement vérifiés contre le matériel réel.**

## Connexion

- Bluetooth Low Energy standard, **sans appairage/chiffrement** (aucun échange SMP observé dans la capture — GATT en clair).
- Découverte : filtrer sur le nom annoncé (ex. `"Urban"`) ou sur l'UUID de service ci-dessous.
- Une seule connexion GATT centrale à la fois (déconnecter l'app officielle si elle est déjà connectée).

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

### Type `0x01` — statut général (déclenché par écriture registre `0x03`)

Contient l'état vitesse/boost/bypass (voir table des registres ci-dessus — mêmes offsets `[34]`/`[44]`/`[53]` que les valeurs écrites en `0x18`/`0x19`/`0x2f`) ainsi que les RPM moteur (`uint16` little-endian, offset `[47:49]` dans nos captures — ex. `0x0168`=360 RPM en vitesse 1, `0x01c2`=450 en vitesse 2, `0x0226`=550 en vitesse 3, valeurs approximatives, à revalider).

Attention : les offsets exacts de cette trame ont légèrement varié entre deux captures à des moments différents (probablement un champ de longueur variable en tête de trame) — se fier plutôt aux types `0x02`/`0x03` ci-dessous, plus stables et simples.

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

## Ce qui reste à faire

1. Localiser le **% de filtre** et les **numéros de série** dans les trames (probablement dans les zones encore non décodées des types `0x01`/`0x02`/`0x03`, ou dans un type de trame pas encore observé).
2. Décoder le tableau de 10 blocs du type `0x02` (historique horaire ?).
3. Revalider les offsets RPM du type `0x01` (l'offset a semblé bouger d'une capture à l'autre — la longueur d'un champ en tête de trame varie peut-être selon un compteur ou la longueur d'un nom).
4. **Tester la famille EXTRACTOR** si l'utilisateur possède aussi ce type d'appareil (UUID différents, non capturés ici).
5. Vérifier si les handles ATT (`0x0013`/`0x000e`) sont stables entre reconnexions/redémarrages de la centrale, ou s'il vaut mieux toujours résoudre par UUID (recommandé, déjà fait dans le code fourni).
