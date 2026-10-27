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
integration first (Settings → Devices & services → VMI+ → ⋮ → Disable), then enable it again.

## Entities

All entities belong to one device. Entity ids start with your device name (e.g.
`select.urban_speed` for a device called "Urban"). Names follow the language of Home Assistant
(English and French are included).

| App feature | Entity | Type |
|---|---|---|
| Speed (3 levels, also the "Theoretical air flow" slider) | Speed | `select` |
| 30 min boost | Boost | `switch` |
| Preheat button | Preheat | `switch` |
| Holiday mode | Holiday mode | `switch` |
| Night ventilation boost | Night boost | `switch` |
| Fixed air flow (radon) | Fixed air flow (radon) | `switch` |
| Time slots on/off, weekly programme as attributes | Time slots | `switch` |
| Time slot editor | `vmi_plus.set_day_schedule` | service |
| Preheat target | Preheat target | `number` |
| Summer supply-air limit | Summer supply air limit | `number` |
| Remote control temperature / humidity | Room temperature / Room humidity | `sensor` |
| Internal probe temperature / humidity | Internal probe temperature / Internal probe humidity | `sensor` |
| Remaining filter life (days) | Filter life | `sensor` |
| Theoretical air flow (m³/h) | Theoretical air flow | `sensor` |
| Season | Season | `sensor` |
| Operating days | Operating days | `sensor` (diagnostic) |
| Software version | Software version | `sensor` (diagnostic) |
| Volume to ventilate, surface, preheat type | Volume to ventilate / Surface / Preheat type | `sensor` (diagnostic) |
| Turbo heat, building management (GTC), action in progress | Turbo heat / Building management / Action in progress | `binary_sensor` (diagnostic) |
| Paired wireless sensors, details as attributes | Paired sensors | `sensor` (diagnostic) |
| Heat-exchanger bypass (+ position, temperature) | Heat exchanger bypass / Bypass position / Bypass temperature | `binary_sensor` / `sensor` |
| Self-test (Diagnostic screen) | Self-test | `binary_sensor` (problem) |
| Find my unit | Locate | `button` |
| Filter replaced (6 or 12 months) | New filter (6 months) / (12 months) | `button`, **restarts the filter counter** |

Model, serial number, firmware and hardware versions are shown on the device page.

Not exposed on purpose: installer configuration (volume, surface, filter lifespan, bypass and
GTC / Modbus settings, sensor pairing), firmware update, history export, factory reset and
after-sales commands.

### Behaviour

- Readings are polled every 10 seconds. Every switch and select reflects the **state read from the
  unit**, so changes made with the app or the remote control show up at the next poll.
- Entities become unavailable while the unit cannot be reached (official app connected, out of range).

### Time slot programme

Example: Monday at medium speed from 7 am, low speed from 10 pm.

```yaml
action: vmi_plus.set_day_schedule
target:
  entity_id: switch.urban_plages_horaires
data:
  day: 1
  slots:
    - {start: 7, speed: medium}
    - {start: 22, speed: low, temperature: 16}
```

Turning time slots on applies the programme at once; an empty programme means the lowest speed.

## Dashboard

[`dashboard.yaml`](dashboard.yaml) is a dashboard laid out like the official app, using built-in
cards only. Install instructions are at the top of the file (adjust the entity id prefix to your
device name).

## Command-line tool and library

The Bluetooth protocol lives in the [vmi-plus-ble](https://github.com/srThibaultP/vmi-plus-ble)
Python library, which also ships a command-line tool to test a unit without Home Assistant:

```bash
pip install "vmi-plus-ble @ git+https://github.com/srThibaultP/vmi-plus-ble"
vmi-plus-ble scan
vmi-plus-ble status AA:BB:CC:DD:EE:FF
vmi-plus-ble speed AA:BB:CC:DD:EE:FF high
```

## Tests

The integration is tested with
[pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component):

```bash
pip install pytest-homeassistant-custom-component -e ../vmi-plus-ble
pytest --cov
```

## Uninstall

Settings → Devices & services → VMI+ → ⋮ → Delete, then remove `custom_components/vmi_plus/` if it
was installed by hand. Nothing is stored on the unit.

## Disclaimer

This project is not affiliated with Ventilairsec. Use it at your own risk: the after-sales and
factory registers listed in [PROTOCOL.md](PROTOCOL.md) must never be sent to a unit.
