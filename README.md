<p align="center"><img src="logo.png" width="96" alt="VMI+ logo"></p>

🇬🇧 English · [🇫🇷 Français](README.fr.md)

# VMI+ → Home Assistant

Unofficial Home Assistant integration that controls **Ventilairsec VMI+ / VMCI** ventilation units
over Bluetooth Low Energy, locally, without the vendor's cloud. It was built by reverse-engineering
the official VMI+ Android app and checked against a real **Urban** unit.

Everything the app shows or controls for a private customer is available in Home Assistant. The
protocol, including the installer and after-sales functions that are deliberately left out, is
described in [PROTOCOL.md](PROTOCOL.md).

## Installation

**HACS:** add this repository as a custom repository (category *Integration*), install
"VMI+ (Ventilairsec)", then restart Home Assistant.

**Manual:** copy `custom_components/vmi_plus/` into the `custom_components/` folder of your Home
Assistant configuration, then restart.

The unit is discovered by the Bluetooth integration (a notification appears under Settings →
Devices & services). Otherwise add it by hand: Add integration → "VMI+ (Ventilairsec)" → MAC address.
A Bluetooth adapter or an ESPHome Bluetooth proxy in range of the unit is needed.

⚠️ The unit accepts **one Bluetooth connection at a time**. To use the official app, turn off the
"Connexion Bluetooth" switch first, then turn it back on.

## Entities

All entities belong to one device. Entity ids start with your device name (e.g.
`select.urban_vitesse` for a device called "Urban").

| App feature | Entity | Type |
|---|---|---|
| Speed (3 levels, also the "Theoretical air flow" slider) | Vitesse | `select` |
| 30 min boost | Boost | `switch` |
| Preheat button | Préchauffage | `switch` |
| Holiday mode | Holiday | `switch` |
| Night ventilation boost | Mode nuit | `switch` |
| Fixed air flow (radon) | Débit fixe (radon) | `switch` |
| Time slots on/off, weekly programme as attributes | Plages horaires | `switch` |
| Time slot editor | `vmi_plus.set_day_schedule` | service |
| Preheat target | Température de préchauffage | `number` |
| Summer supply-air limit | Limite température été | `number` |
| Remote control temperature / humidity | Température pièce / Humidité pièce | `sensor` |
| Internal probe temperature / humidity | Température sonde interne / Humidité sonde interne | `sensor` |
| Remaining filter life (days) | Autonomie filtre | `sensor` |
| Theoretical air flow (m³/h) | Débit théorique | `sensor` |
| Season | Saison | `sensor` |
| Operating days | Jours de fonctionnement | `sensor` (diagnostic) |
| Software version | Version logicielle | `sensor` (diagnostic) |
| Volume to ventilate, surface, preheat type | Volume à ventiler / Surface / Type de préchauffage | `sensor` (diagnostic) |
| Turbo heat, building management (GTC), action in progress | Turbo chauffage / GTC / Action en cours | `binary_sensor` (diagnostic) |
| Paired wireless sensors, details as attributes | Capteurs associés | `sensor` (diagnostic) |
| Heat-exchanger bypass (+ position, temperature) | Bypass échangeur / Position bypass | `binary_sensor` / `sensor` |
| Self-test (Diagnostic screen) | Autotest | `binary_sensor` (problem) |
| Find my unit | Localiser (LED) | `button` |
| Filter replaced (6 or 12 months) | Filtre changé (6 mois) / (12 mois) | `button`, **restarts the filter counter** |
| Release the unit for the official app | Connexion Bluetooth | `switch` |

Model, serial number, firmware and hardware versions are shown on the device page.

Not exposed on purpose: installer configuration (volume, surface, filter lifespan, bypass and
GTC / Modbus settings, sensor pairing), firmware update, history export, factory reset and
after-sales commands.

### Behaviour

- Readings are polled every 10 seconds. Every switch and select reflects the **state read from the
  unit**, so changes made with the app or the remote control show up at the next poll.
- During a Bluetooth outage, entities keep their last known value instead of becoming unavailable.

### Time slot programme

Example: Monday at medium speed from 7 am, low speed from 10 pm.

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

Turning time slots on applies the programme at once; an empty programme means the lowest speed.

## Dashboard

[`dashboard.yaml`](dashboard.yaml) is a dashboard laid out like the official app, using built-in
cards only. Install instructions are at the top of the file (adjust the entity id prefix to your
device name).

## Command-line tool

[`vmi_ble.py`](vmi_ble.py) talks to the unit without Home Assistant, which is handy to test the
protocol from any machine with Bluetooth:

```bash
pip install bleak
python3 vmi_ble.py scan
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF speed 2
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF boost on
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF monitor
python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF raw --reg 0x18 --val 0x01
```

## Tests

`tests/test_protocol.py` checks the frame encoder and decoder against real frames, with no
dependency:

```bash
python3 -m unittest discover -s tests
```

## Uninstall

Settings → Devices & services → VMI+ → ⋮ → Delete, then remove `custom_components/vmi_plus/` if it
was installed by hand. Nothing is stored on the unit.

## Disclaimer

This project is not affiliated with Ventilairsec. Use it at your own risk: the after-sales and
factory registers listed in [PROTOCOL.md](PROTOCOL.md) must never be sent to a unit.
