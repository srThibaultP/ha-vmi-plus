<p align="center"><img src="logo.png" width="96" alt="Logo VMI+"></p>

# VMI+ → Home Assistant

Intégration non-officielle pour piloter en Bluetooth Low Energy une centrale de ventilation
**VMI+ / VMCI (Ventilairsec)**, reverse-engineered à partir de l'app Android officielle et
d'une capture BLE réelle. Détails complets du protocole : [PROTOCOL.md](PROTOCOL.md).

**Vérifié contre du matériel réel** : vitesse (1/2/3), Boost, Bypass, et température/humidité
des deux sondes (interne + télécommande/pièce). **Pas encore fait** : % de filtre, numéros de
série, historique — voir "Ce qui reste à faire" dans [PROTOCOL.md](PROTOCOL.md).

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

Entités créées :
- `select.vitesse` — vitesse 1/2/3 (entité `select` et non `fan` : la centrale ventile en
  continu et ne peut pas être éteinte, alors que le domaine `fan` de HA impose toujours une
  position "Off")
- `switch.boost` — surventilation 30 min
- `switch.bypass` — contournement de l'échangeur (préchauffage gratuit de l'air, utile en hiver)
- `switch.connexion_bluetooth` — active/désactive la connexion BLE (utile pour libérer la
  centrale au profit de l'app officielle, une seule connexion GATT possible à la fois)
- `sensor.temperature_sonde_interne` / `sensor.humidite_sonde_interne` — sonde interne
  (ex. sortie résistance de préchauffage)
- `sensor.temperature_piece` / `sensor.humidite_piece` — sonde télécommande de la pièce
  ventilée (ex. salle de bain)

Les sensors sont alimentés par un polling automatique toutes les 10s (démarré dès qu'une
entité sensor est chargée) — pas besoin de configuration supplémentaire.

**Testé et fonctionnel en conditions réelles** (vitesse, boost, lecture des sondes) sur une
vraie instance HA.

⚠️ **Limitation** : `select.vitesse`, `switch.boost` et `switch.bypass` restent optimistes —
c'est la mémoire de la dernière commande *envoyée par HA*, pas une lecture réelle de l'appareil
(contrairement aux sensors température/humidité, qui eux sont de vraies lectures). Si tu changes
une vitesse via l'app officielle ou la télécommande physique, ces trois entités resteront
obsolètes jusqu'à leur prochaine commande depuis HA. Le statut vitesse/boost/bypass est en
réalité aussi diffusé par la centrale (notification type `0x01`, voir PROTOCOL.md) mais pas
encore branché sur ces entités — piste d'amélioration future.

## 3. Prochaines étapes possibles

Voir la section "Ce qui reste à faire" dans [PROTOCOL.md](PROTOCOL.md) — principalement le
décodage de la télémétrie pour avoir des sensors (humidité, filtre, RPM) plutôt que juste du
contrôle.
