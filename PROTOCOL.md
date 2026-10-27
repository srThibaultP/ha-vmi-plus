🇬🇧 English · [🇫🇷 Français](PROTOCOL.fr.md)

# VMI+ (Ventilairsec) BLE protocol

Reverse-engineered description of the Bluetooth Low Energy protocol spoken by Ventilairsec VMI+ /
VMCI ventilation units (tested on an **Urban** unit) and the official **VMI+** Android app
(`com.ventilairsec.ventilairsecinstallateur`, Flutter).

Sources:

- Bluetooth HCI captures of the official app driving a real unit, changing one setting at a time
  and diffing the frames.
- Direct reads and writes from a Linux machine with [bleak](https://github.com/hbldh/bleak).
- The app's own frame decoder, recovered by decompiling an older build of the app (see
  [Reproducing the decompilation](#reproducing-the-decompilation)).

Values marked ✓ were checked against a real unit and the app's screens. The rest comes from the
app's code only.

## Connection

- Standard BLE, **no pairing or encryption** (plain GATT).
- Discovery: by advertised name (e.g. `Urban`) or by the control service UUID below.
- **One central at a time.** While a client is connected, the unit stops advertising, so the app
  and Home Assistant cannot be connected at the same time.

| Role | Service UUID | Characteristic UUID | Properties |
|---|---|---|---|
| Control (writes) | `0003cbbb-0000-1000-8000-00805f9b0131` | `0003cbb1-0000-1000-8000-00805f9b0131` | Read, Write with response, Notify |
| Telemetry (notifications) | `0003cab5-0000-1000-8000-00805f9b0131` | `0003caa2-0000-1000-8000-00805f9b0131` | Notify |

The app also contains a second UUID family (`7c4adc01`…`7c4adc07-2f33-11e7-93ae-92361f002671`),
probably for another product range; it is not used by the Urban.

## Frame format

Every frame, in both directions, has the same layout:

```
A5 B6 [class] 06 [len] [payload …] [crc]
```

- `A5 B6`: magic.
- `class`: frame class (tables below).
- `06`: constant (the very first write of a session uses `00`: `a5b6100005030000000016`).
- `len`: payload length.
- `crc`: checksum of every byte before it.

### Checksum

```python
def checksum(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 1) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc ^ 0x13
```

### Commands (class `0x10`)

Commands carry a 5-byte payload `[REG, 0, 0, 0, VAL]`:

```python
def build_command(register: int, value: int) -> bytes:
    data = bytes([0xA5, 0xB6, 0x10, 0x06, 0x05, register, 0, 0, 0, value])
    return data + bytes([checksum(data)])
```

| Command | Frame |
|---|---|
| Speed 1 / 2 / 3 | `a5b610060518000000000b` / `…010a` / `…0209` |
| Boost on / off | `a5b610060519000000010b` / `a5b610060519000000000a` |
| Preheat button on / off | `a5b61006052f000000013d` / `a5b61006052f000000003c` |
| Night boost (toggle) | `a5b61006050b0000000018` |

Writes are GATT *Write Requests* on the control characteristic. The unit answers on the telemetry
characteristic.

## Frame classes

App → unit: `0x10` Command ✓, `0x11` Setting, `0x12` Config, `0x13` ConfigSensors, `0x15`
ConfigErp, `0x17` ConfigByPass, `0x19` ConfigTimeSlot ✓, `0x1a` UpdateDate ✓, `0x20` NewUpdate,
`0x21` Update, `0x22` UpdateAckData.

Unit → app: `0x01` State ✓, `0x02` SensorsState ✓, `0x03` ProbesState ✓, `0x04` SimpleData,
`0x05` TimeSlotState ✓, `0x16` ErpState, `0x18` ByPassState ✓, `0x1b` AutoTestDatas, `0x23`
AckData, `0x30` Csv, `0x31` Histo, `0xff` Nack.

## Command registers

| Reg | App name | Use |
|---|---|---|
| `0x01` | Test | |
| `0x02` | Localisation | blink the LED to find the unit ✓ |
| `0x03` | State | read → State frame ✓ |
| `0x04` | Update | firmware update |
| `0x05` | NewFilter | filter replaced, value = interval in months (6 or 12). **Restarts the filter counter.** |
| `0x06` | Sensors | read → SensorsState ✓ |
| `0x07` | Probes | read → ProbesState ✓ |
| `0x09` / `0x22` / `0x21` / `0x20` | StartCsv / StartCsvV2 / StopCSV / CsvLength | history export |
| `0x0a` / `0x1f` | Old / NewSerialisation | factory |
| `0x0b` | Surventilation | night ventilation boost ✓, **toggles** on every write (value ignored) |
| `0x0d` | Calibration | |
| `0x10` | DeleteSensor | |
| `0x12` | ErpState | read → ErpState |
| `0x13` | Reset | **factory reset, never send** |
| `0x14` / `0x15` | ByPass / ByPassForced | `0x14` = read ByPassState ✓ |
| `0x16` / `0x23` | AutoTest / AutoTestDatas | self-test |
| `0x17` | Tmax | summer supply-air limit, °C ✓ |
| `0x18` | Mode | speed 0 / 1 / 2 ✓ |
| `0x19` | Boost | 30 min boost 1 / 0 ✓ |
| `0x1a` | Hollidays | holiday mode 1 / 0 ✓ (the number of days stays in the app) |
| `0x1b` | FixedFlow | fixed air flow (radon) 1 / 0 ✓ |
| `0x1c` | Temp | preheat target, °C, `0` = no preheating ✓ |
| `0x1d` | TimeSlot | time slots 1 / 0 ✓ (answers TimeSlotState) |
| `0x1e` | TempElec | |
| `0x24` / `0x25` | GeoVersion / ElecVersion | |
| `0x2c` | — | sent once per connection by recent apps, role unknown |
| `0x2f` | — | preheat button of the home screen, 1 / 0 ✓ (recent apps) |
| `0xf9`–`0xff` | Sav7 … Sav1 | after-sales actions, **never send** |

The app polls `0x03`, `0x06` and `0x07` while a screen is open. Every screen of the app is built
from the State, SensorsState and ProbesState frames: opening a screen sends no other read.

## State frame (`0x01`)

Answer to register `0x03` (and `0x0b`). Offsets are indexes in the raw notification, header
included (`[0]` = `a5`).

| Offset | App key | Meaning |
|---|---|---|
| `[3]` | — | used by the app for a version check |
| `[5:9]` LE | machineId | serial number (hex), shown with a model prefix by the app ✓ |
| `[9]` | — | action in progress (e.g. locate) ✓ |
| `[10]` bits | testStatus | 5 self-test result bits, `0x1f` = all OK ✓ |
| `[11]`–`[14]` | probe / preheat / engine / qai | per-test detail |
| `[15]` | gtcEnabled | building management (GTC / Modbus) enabled |
| `[16]` | calibration | |
| `[17]` | surface | surface = value × 2 m² ✓ |
| `[18]` | height / flowPerPerson | |
| `[19]` | box | 1 Purevent, 2 Urban ✓, 3 PRO, 5 Cube |
| `[20]` | softwareVersion | major.minor in nibbles (`0x64` → 6.4) ✓ |
| `[21]` | elec | electronic version (high nibble), board software version (low nibble) ✓ |
| `[22:24]` LE | ventilateVolume | volume to ventilate, m³ ✓ |
| `[24]` | preheatType | 1 electric ✓, 2 solar, 3 smart, 4 smart partner, 5 partner |
| `[25]` | bypass | heat-exchanger bypass open ✓ |
| `[26:28]` LE | upTime | operating days ✓ |
| `[28:30]` LE | autonomy | remaining filter life, days (max 360) ✓ |
| `[32]` | theoreticalFlow | air flow × 10 m³/h (older apps) |
| `[33]` | surventilation | night boost, **inverted**: `0` = on ✓ |
| `[34]` | mode | speed 0 / 1 / 2 ✓ |
| `[35]` | tempElec | preheat target ✓ |
| `[36]` | tempHydro | hydraulic preheat target |
| `[37]` bits | boxDefined | |
| `[38]` | tempBlowing | summer limit ✓ |
| `[39:43]` LE | date | |
| `[43]` | hollidaysMode | ✓ |
| `[44]` | boost | ✓ |
| `[45]` | fixedFlow | ✓ |
| `[46]` | timeSlot | ✓ |
| `[47:49]` LE | — | theoretical air flow in 1/5 m³/h ✓ (recent apps) |
| `[49]` | — | software version patch (`6.4.` + 3 digits) ✓ |
| `[50]` | meca | mechanical version ✓ |
| `[51]` | season | 0 summer, 1 winter, 2 intermediate ✓ |
| `[52]` | turbo_heater | turbo heat ✓ |
| `[53]` | — | preheat button state (register `0x2f`) ✓ |

The last byte is the frame checksum.

## SensorsState (`0x02`)

Answer to register `0x06`. Up to 10 wireless sensors, 10 bytes each from offset 5:

| Byte | Meaning |
|---|---|
| `+0..+3` LE | sensor id (hex) ✓ |
| `+4` | room: 0 unknown, 1 living room, 2 kitchen, 3 bathroom 1, 4 bathroom 2, 5–8 bedroom 1–4, 9 cellar ✓ |
| `+5` | kind: 0 absent, 1 Nexelec CO₂, 2 Nexelec temperature, 3 remote control ✓, 4 box, 5 Nanosense |
| `+6..+7` | CO₂ sensors: CO₂ ppm (LE). Others: `+6` = temperature °C (≥ 128 means negative: value − 255) ✓ |
| `+8` | humidity % ✓ |
| `+9` | third value |

The id prefix tells the app the model when pairing: `I420` CO₂, `I880` temperature, `ASI ` /
`SNE ` remote control.

## ProbesState (`0x03`)

Answer to register `0x07`. Up to 5 wired probes, 5 bytes each from offset 5:
`[location, temperature (signed), ?, humidity, ?]` ✓. Unused slots read location `0x08`.

## TimeSlotState (`0x05`) and ConfigTimeSlot (`0x19`)

- TimeSlotState: `[5]` = enabled, then 7 days × 5 slots × `[start hour, speed, temp]` from offset
  6. `start = 0xff` = empty slot. Speed 0 / 1 / 2.
- ConfigTimeSlot (app → unit), one frame per day: `[day 1–7, (start, speed + 1, temp) × 5]`, empty
  slot `ff 00 00`. The app sends speed 1 / 2 / 3, the unit stores and reports 0 / 1 / 2 ✓.
- `temp` is the preheat setpoint of the slot.
- Turning time slots on (register `0x1d`) applies the schedule at once; with an empty schedule the
  unit falls back to the lowest speed ✓.

## ByPassState (`0x18`)

Answer to register `0x14`.

| Offset | App key |
|---|---|
| `[5]` | position % ✓ |
| `[6]` | type |
| `[8]` | temperature °C ✓ |
| `[11]` | unknown |
| `[17:21]` LE | id |
| `[21]` | forced |
| `[22]` | requested position % |

Register `0x15` forces the bypass. Installer settings go in a ConfigByPass frame (`0x17`:
temperature, type, id).

## Other frames

- **UpdateDate** (`0x1a`): clock sync `[yy, mm, dd, hh, mi, ss]`, sent by the app on every
  connection ✓.
- **ErpState** (`0x16`, register `0x12`): GTC / Modbus settings `[5]` mode, `[6]` slave address,
  `[7]` baud rate, `[8]` parity, `[9]` stop bit. Units without GTC do not answer. Written with
  ConfigErp (`0x15`).
- **Config** (`0x12`): installation wizard, 18 bytes: volume (2), box type, bypass type, filter
  lifespan (months), mode, preheat temperature, summer limit, hydraulic temperature, 0, date
  (`yy mm dd hh mi ss`), surface, height.
- **Self-test** (`0x16` / `0x23` → `0x1b`): the Diagnostic screen of recent apps only shows the
  status bits `[10]`–`[14]`.
- **History** (`0x09`/`0x22`, `0x20`, `0x21` → `0x30` / `0x31`): CSV export; recent apps send it by
  e-mail through the vendor's cloud.
- **Firmware update** (`0x04`, `0x20`, `0x21`, `0x22`): downloaded by the app and sent in packets.
- Notification `0x50`: sent by recent firmware, content unknown.

## After-sales menu

Recent apps hide an after-sales menu behind a work code: reset to factory settings, force a machine
update, force the extract (MEV) or supply (PIV) firmware, force install, two password options and a
link to report an after-sales case. Each option ends up as one of the Sav1–Sav7 registers
(`0xff`…`0xf9`) and the unit restarts. Older apps showed plain "Command 1"…"Command 7" buttons.
**None of these registers should be sent by hand.**

## Error codes

From the app's translation files (`error_code_XX`). Where they travel in the frames is not known
yet.

| Code | Meaning |
|---|---|
| `01` | Resistor failure |
| `02` | Preheating cannot reach the setpoint temperature |
| `10` | Motor failure |
| `20` | Replace filter |
| `30` | IAQ sensor failure |
| `31`–`39` | IAQ sensor no. 1–9 failure |
| `3A` | Several IAQ sensors |
| `3B` | IAQ sensor pairing problem |
| `40` | Unknown remote control problem |
| `41` | Remote control temperature error |
| `42` | Loss of remote control communication |
| `43` | Remote control low battery |
| `44` | Multiple remote control failures |
| `50` | Housing unit probe failure |
| `51` | Resistor outlet probe failure |
| `52` | Machine inlet probe failure |
| `53` | HydroR® outlet probe failure |
| `55` | Bypass outlet probe failure |
| `56` | Bypass outdoor-side probe failure |
| `57` | Bypass roof-space-side probe failure |
| `5E` | Filter pressure probe failure |
| `5F` | Several probe failures |
| `61` | Bypass error |
| `65` | Software download error |
| `70` | Multiple errors |
| `81` / `82` | Bypass communication error |
| `83` | Bypass damper blocked |
| `vmc_51` | Housing unit probe failure |
| `vmc_58` | Housing unit probe frozen |

## Reproducing the decompilation

The app is written in Flutter: its logic is compiled Dart code in `lib/arm64-v8a/libapp.so`.
[blutter](https://github.com/worawit/blutter) rebuilds readable pseudo-code, function names and the
object pool from it.

The APK is not shipped in this repository (it belongs to its vendor). The build that was used:

| | |
|---|---|
| App | VMI+ `com.ventilairsec.ventilairsecinstallateur` |
| Version | 3.19.5 (version code 319051), Dart 3.5.3 |
| Source | [APKPure, previous versions](https://apkpure.com/vmi/com.ventilairsec.ventilairsecinstallateur/versions), XAPK |
| SHA-256 of the XAPK | `d16b987f0df0723e76d98962ce78132b3b43463f37c251112993f97a7a25c411` |
| SHA-256 of `config.arm64_v8a.apk` | `c1acb2a13aa174b1de2ad433b49e40f508b2881cfe12a7570eddd983e35ca4d1` |
| SHA-256 of `libapp.so` | `97c2c6aace70cc0c6a889d12af2f27c948c056d0cb223de69f7569b5a9c6a4fa` |

Recent builds (3.2x) use a Dart version blutter cannot read yet, and blutter only handles the
**arm64-v8a** libraries, not 32-bit `armeabi-v7a` ones.

Steps (macOS or Linux):

```bash
# 1. Extract the native libraries from the XAPK (a ZIP of split APKs)
mkdir vmi && cd vmi
unzip ../VMI+_3.19.5_APKPure.xapk config.arm64_v8a.apk
unzip config.arm64_v8a.apk 'lib/arm64-v8a/*'
shasum -a 256 lib/arm64-v8a/libapp.so   # compare with the table above

# 2. Install blutter and its dependencies
#    macOS: brew install cmake ninja pkg-config icu4c capstone
#    Debian/Ubuntu: apt install python3-pyelftools python3-requests git cmake ninja-build \
#                   build-essential pkg-config libicu-dev libcapstone-dev
git clone https://github.com/worawit/blutter
python3 -m pip install pyelftools requests

# 3. Decompile (the first run builds the Dart runtime matching the app, it takes a while)
python3 blutter/blutter.py lib/arm64-v8a out
```

Where to look in `out/`:

- `asm/ventilairsec_installateur/ventilairsec-bluetooth-connector/bluetooth_connector.dart`:
  `readMachineState` and the other `read…` functions decode each frame class.
- `pp.txt` (object pool): the command name → register table and the lookup tables (rooms, sensor
  kinds, box types).
- The app's translation files (`assets/flutter_assets/assets/langs/*.json` in the base APK)
  give the screen labels and error codes.

## Still unknown

1. Confirm the filter-change command (`0x05` + months) on a real filter replacement, and how the
   app computes its FILTER %.
2. CO₂ / Nexelec / Nanosense sensors and hydraulic or solar preheating: decoded from the app's code
   only.
3. Where the error codes appear in the frames.
4. Status `[3]`, `[18]`, `[36]`, `[37]`, `[39:43]`, ByPassState `[11]`, register `0x2c` and
   notification `0x50`.
