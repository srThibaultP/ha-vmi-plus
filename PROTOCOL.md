# Protocole BLE de la centrale VMI+ (Ventilairsec) — rétro-ingénierie

Reversé à partir de :
- Décompilation partielle de l'app Android **VMI+** v3.21.14 (`com.ventilairsec.ventilairsecinstallateur`, Flutter/Dart, utilise le plugin `flutter_blue_plus`)
- Capture Bluetooth HCI snoop en conditions réelles (Pixel Fold, Android 17) contre une centrale **VMCI "Urban"** (MAC `00:A0:50:3A:18:23`), le 2026-08-26

Statut : **le canal de commande (contrôle vitesse/boost/bypass) est entièrement vérifié contre le matériel réel** (11/11 trames de commande capturées reproduites exactement par la formule ci-dessous). Le canal de télémétrie (capteurs) n'est **pas** décodé — voir section "Ce qui reste à faire".

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
| `0x03` | Lu en polling toutes les ~10s par l'app (lecture d'état, pas une commande) | — |
| `0x06` | Idem, heartbeat/lecture d'état périodique | — |
| `0x07`, `0x2c` | Vus une fois pendant la séquence d'initialisation (rôle non déterminé) | — |

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

## Télémétrie (canal notify) — non décodé

L'appareil pousse en continu (toutes les ~150-300ms pendant une session active, avec un "poll" applicatif toutes les ~10s) de gros paquets de notification (jusqu'à ~240 octets) sur la caractéristique télémétrie, préfixés eux aussi par `A5 B6`. Ils contiennent très probablement l'humidité, l'état des vitesses, le % de filtre, les RPM, etc., mais leur structure interne n'a pas été décodée dans cette session (nécessiterait de faire varier un seul paramètre physique à la fois — ex. souffler de l'humidité sur le capteur — en observant le delta d'octets, ce qui n'était pas faisable à distance).

## Ce qui reste à faire

1. **Décoder la télémétrie** pour exposer des sensors HA (humidité, % filtre, vitesse RPM réelle, alarmes). Nécessite plusieurs captures ciblées faisant varier un paramètre à la fois.
2. ~~Confirmer le rôle du registre `0x2f`~~ — **fait** : confirmé par l'utilisateur, le Bypass fait entrer de l'air chaud (préchauffage gratuit en hiver).
3. **Tester la famille EXTRACTOR** si l'utilisateur possède aussi ce type d'appareil (UUID différents, non capturés ici).
4. Vérifier si les handles ATT (`0x0013`/`0x000e`) sont stables entre reconnexions/redémarrages de la centrale, ou s'il vaut mieux toujours résoudre par UUID (recommandé, déjà fait dans le code fourni).
