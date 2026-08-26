<p align="center"><img src="logo.png" width="96" alt="Logo VMI+"></p>

# VMI+ → Home Assistant

Intégration non-officielle pour piloter en Bluetooth Low Energy une centrale de ventilation
**VMI+ / VMCI (Ventilairsec)**, reverse-engineered à partir de l'app Android officielle et
d'une capture BLE réelle. Détails complets du protocole : [PROTOCOL.md](PROTOCOL.md).

**Vérifié contre du matériel réel** : vitesse (1/2/3), Boost, et un 3e registre (probable
Bypass). **Pas encore fait** : décodage des capteurs (humidité, % filtre, RPM) — le canal
existe et pousse des données, mais sa structure interne n'est pas décodée.

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
```

⚠️ La centrale n'accepte qu'une connexion BLE à la fois — ferme l'app VMI+ sur ton téléphone
avant de tester, sinon la connexion échouera ou coupera l'app.

## 2. Installer l'intégration Home Assistant

Copie le dossier `custom_components/vmi_plus/` dans le dossier `custom_components/` de ta
config Home Assistant, puis redémarre HA. La centrale devrait être auto-détectée par
l'intégration Bluetooth (Paramètres → Appareils → une notification de découverte devrait
apparaître) ; sinon, ajoute-la manuellement via Paramètres → Appareils → Ajouter une
intégration → "VMI+ (Ventilairsec)" et saisis l'adresse MAC.

Entités créées :
- `fan.ventilation` — vitesse 1/2/3
- `switch.boost` — surventilation 30 min
- `switch.bypass` — contournement de l'échangeur (préchauffage gratuit de l'air, utile en hiver)
- `switch.connexion_bluetooth` — active/désactive la connexion BLE (utile pour libérer la
  centrale au profit de l'app officielle, une seule connexion GATT possible à la fois)

**Testé et fonctionnel en conditions réelles** (vitesse, boost) sur une vraie instance HA.

⚠️ **Limitation importante** : les états affichés dans HA (`66%`, `Boost: On`...) sont purement
optimistes — c'est la mémoire de la dernière commande *envoyée par HA*, pas une lecture réelle
de l'appareil. Si tu changes une vitesse via l'app officielle ou la télécommande physique, HA
ne le saura pas et affichera un état obsolète jusqu'à sa prochaine commande. Ça vaut aussi pour
le switch "Connexion Bluetooth" : le désactiver coupe les écritures, mais aucune lecture
n'était de toute façon en cours (pas de télémétrie décodée, voir PROTOCOL.md).

## 3. Prochaines étapes possibles

Voir la section "Ce qui reste à faire" dans [PROTOCOL.md](PROTOCOL.md) — principalement le
décodage de la télémétrie pour avoir des sensors (humidité, filtre, RPM) plutôt que juste du
contrôle.
