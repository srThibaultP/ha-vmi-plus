"""Construction des trames de commande du protocole VMI+.

Voir PROTOCOL.md pour la rétro-ingénierie complète (capture BLE réelle,
vérifiée trame par trame contre une centrale VMCI physique).
"""


# Season byte of the status frame, as decoded by the app ("season_" + name).
SEASONS = {0x00: "ete", 0x01: "hiver", 0x02: "intermediaire"}

# Lookup tables copied from the app (3.19.5 object pool), see PROTOCOL.md.
BOXES = {0x01: "Purevent", 0x02: "Urban", 0x03: "PRO", 0x05: "Cube"}
PREHEAT_TYPES = {0x01: "electric", 0x02: "solar", 0x03: "smart", 0x04: "smart_partner", 0x05: "partner"}
SENSOR_TYPES = {
    0x00: "absent",
    0x01: "nexelec_co2",
    0x02: "nexelec_temp",
    0x03: "assistant",  # remote control with temperature/humidity probe
    0x04: "box",
    0x05: "nanosense",
}
ROOMS = {
    0x00: "unknown",
    0x01: "living",
    0x02: "kitchen",
    0x03: "bathroom1",
    0x04: "bathroom2",
    0x05: "bedroom1",
    0x06: "bedroom2",
    0x07: "bedroom3",
    0x08: "bedroom4",
    0x09: "cellar",
}

# Frame classes (byte [2]) used by build_raw_frame.
CLASS_CONFIG_TIME_SLOT = 0x19
CLASS_UPDATE_DATE = 0x1A
TIME_SLOT_DAYS = 7
TIME_SLOTS_PER_DAY = 5
EMPTY_SLOT_START = 0xFF


def checksum(data: bytes) -> int:
    """CRC-8 (poly triviale, init=0) XOR 0x13, vérifié sur 11 trames réelles."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 1) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ 0x13


def build_raw_frame(frame_class: int, payload: bytes) -> bytes:
    """Builds any app -> unit frame: A5 B6 [class] 06 [len] [payload] [crc]."""
    data = bytes([0xA5, 0xB6, frame_class, 0x06, len(payload)]) + bytes(payload)
    return data + bytes([checksum(data)])


def build_time_slot_frame(day: int, slots: list[dict]) -> bytes:
    """Builds a ConfigTimeSlot frame (class 0x19) for one day (1 = Monday).

    Each slot is {"start": hour 0-23, "speed": 0-2, "temp": preheat °C}; up to 5
    slots, missing ones are sent empty. The unit stores speed + 1 as sent by the
    app and reports it back minus one in the TimeSlotState frame (verified on
    the device 2026-10-27, see PROTOCOL.md).
    """
    payload = [day]
    for index in range(TIME_SLOTS_PER_DAY):
        if index < len(slots):
            slot = slots[index]
            payload += [slot["start"], slot["speed"] + 1, slot.get("temp", 0xFF)]
        else:
            payload += [EMPTY_SLOT_START, 0x00, 0x00]
    return build_raw_frame(CLASS_CONFIG_TIME_SLOT, bytes(payload))


def build_date_frame(year: int, month: int, day: int, hour: int, minute: int, second: int) -> bytes:
    """Builds the clock-sync frame the app sends on every connection (class 0x1a)."""
    return build_raw_frame(CLASS_UPDATE_DATE, bytes([year % 100, month, day, hour, minute, second]))


def build_frame(register: int, value: int) -> bytes:
    """Construit une trame de commande registre/valeur de 11 octets."""
    data = bytes([0xA5, 0xB6, 0x10, 0x06, 0x05, register, 0, 0, 0, value])
    return data + bytes([checksum(data)])


def parse_notification(data: bytes) -> dict | None:
    """Décode une notification de télémétrie (voir PROTOCOL.md, section Télémétrie).

    Retourne un dict {"type": ..., ...champs...} pour les types reconnus
    (probe/remote), ou None pour un type non décodé ou une trame trop courte.
    """
    if len(data) < 3 or data[0] != 0xA5 or data[1] != 0xB6:
        return None

    frame_type = data[2]

    if frame_type == 0x01 and len(data) >= 54:
        # Statut général (vitesse/boost/bypass/modes spéciaux), déclenché par
        # l'écriture du registre 0x03 (ou 0x0b). Tous les champs ci-dessous
        # sont vérifiés par capture BLE réelle (offsets confirmés en changeant
        # chaque réglage individuellement et en diffant la trame avant/après),
        # voir PROTOCOL.md.
        return {
            "type": "status",
            "night_boost": data[33] == 0x00,  # logique inversée : 0x00=activé
            "speed": data[34],  # 0x00/0x01/0x02, cf. SPEED_OPTIONS
            "holiday": data[43] == 0x01,
            "boost": data[44] == 0x01,
            "bypass": data[53] == 0x01,
            # Little-endian uint16, matches the app's "Equipment life ->
            # Operating days" (1084 = 0x043C on the 2026-10-27 capture).
            "operating_days": int.from_bytes(data[26:28], "little"),
            # Summer supply-air limit in °C, written with register 0x17.
            "summer_limit": data[38],
            # Preheat target in °C (0 = no preheating), written with register 0x1c.
            "preheat_target": data[35],
            # Theoretical air flow of the current speed, little-endian uint16
            # in 1/5 m³/h (360/450/550 = 72/90/110 m³/h, matches the app).
            "air_flow": int.from_bytes(data[47:49], "little") / 5,
            # Fields below come from the app's own status parser
            # (BluetoothModel.readMachineState, app 3.19.5), see PROTOCOL.md.
            # Remaining filter life in days ("autonomy"), little-endian uint16.
            "filter_days": int.from_bytes(data[28:30], "little"),
            "season": SEASONS.get(data[51]),
            # Embedded software version, e.g. 0x64 + 0x02 -> "6.4.002".
            "software_version": f"{data[20] >> 4}.{data[20] & 0x0F}.{data[49]:03d}",
            "serial": f"{int.from_bytes(data[5:9], 'little'):08X}",
            "box": BOXES.get(data[19]),
            # High nibble = electronic version, low nibble = board software
            # version (0x11 -> the app shows "1" and "1").
            "electronic_version": data[21] >> 4,
            "mechanical_version": data[50],
            "volume": int.from_bytes(data[22:24], "little"),
            "surface": data[17] * 2,
            "preheat_type": PREHEAT_TYPES.get(data[24]),
            "bypass_open": data[25] == 0x01,
            "fixed_flow": data[45] == 0x01,
            "time_slots": data[46] == 0x01,
            "turbo_heater": data[52] == 0x01,
            "gtc": data[15] == 0x01,
            # Self-test bits ([10], 0x1f = all 5 OK) and per-test details
            # (probe / preheat / engine / IAQ) from the Diagnostic screen.
            "self_test": data[10],
            "self_test_details": data[11:15].hex(),
            "action_in_progress": data[9] == 0x01,
        }

    if frame_type == 0x03 and len(data) >= 9:
        # Sonde interne "Probe N°1" (ex. sortie résistance), déclenchée par
        # l'écriture du registre 0x07. The frame holds up to 5 probes of 5
        # bytes from offset 5: [location, temperature (signed), ?, humidity, ?].
        probes = []
        for offset in range(5, min(len(data) - 3, 30), 5):
            probes.append(
                {
                    "location": data[offset],
                    "temperature": _signed(data[offset + 1]),
                    "humidity": data[offset + 3],
                }
            )
        return {"type": "probe", "temperature": data[6], "humidity": data[8], "probes": probes}

    if frame_type == 0x02 and len(data) >= 14:
        # Sonde télécommande / pièce ventilée (ex. "Bathroom 1"), déclenchée
        # par l'écriture du registre 0x06. The frame lists up to 10 sensors of
        # 10 bytes from offset 5 (layout from the app's readSensorsData).
        return {
            "type": "remote",
            "temperature": data[11],
            "humidity": data[13],
            "sensors": _parse_sensors(data),
        }

    if frame_type == 0x05 and len(data) >= 6:
        # TimeSlotState, sent back after writing register 0x1d or a
        # ConfigTimeSlot frame: [5] = enabled, then 7 days x 5 slots x
        # [start hour, speed, temp], start 0xff = empty slot.
        days = []
        for day in range(TIME_SLOT_DAYS):
            slots = []
            for slot in range(TIME_SLOTS_PER_DAY):
                offset = 6 + (day * TIME_SLOTS_PER_DAY + slot) * 3
                if offset + 2 >= len(data) or data[offset] == EMPTY_SLOT_START:
                    continue
                slots.append(
                    {"start": data[offset], "speed": data[offset + 1], "temp": data[offset + 2]}
                )
            days.append(slots)
        return {"type": "time_slots", "enabled": data[5] == 0x01, "days": days}

    if frame_type == 0x18 and len(data) >= 23:
        # ByPassState, answer to register 0x14 (app's readByPassData).
        return {
            "type": "bypass_state",
            "position": data[5],
            "bypass_type": data[6],
            "temperature": data[8],
            "id": f"{int.from_bytes(data[17:21], 'little'):08X}",
            "forced": data[21],
            "requested_position": data[22],
        }

    if frame_type == 0x16 and len(data) >= 10:
        # ErpState (GTC / Modbus settings), answer to register 0x12.
        return {
            "type": "gtc",
            "mode": data[5],
            "address": data[6],
            "baudrate": data[7],
            "parity": data[8],
            "stop_bit": data[9],
        }

    return None


def _signed(value: int) -> int:
    """Temperatures >= 128 are negative in the app (value - 255)."""
    return value - 0xFF if value >= 0x80 else value


def _parse_sensors(data: bytes) -> list[dict]:
    """Decodes the 10 sensor slots of a SensorsState (0x02) frame."""
    sensors = []
    for offset in range(5, min(len(data) - 9, 105), 10):
        sensor_type = SENSOR_TYPES.get(data[offset + 5], "unknown")
        if sensor_type == "absent" or data[offset : offset + 4] == b"\x00\x00\x00\x00":
            continue
        sensor = {
            "slot": (offset - 5) // 10,
            "id": f"{int.from_bytes(data[offset:offset + 4], 'little'):08X}",
            "room": ROOMS.get(data[offset + 4], "unknown"),
            "kind": sensor_type,
        }
        if sensor_type == "nexelec_co2":
            sensor["co2"] = int.from_bytes(data[offset + 6 : offset + 8], "little")
        else:
            sensor["temperature"] = _signed(data[offset + 6])
        sensor["humidity"] = data[offset + 8]
        sensor["data_c"] = data[offset + 9]
        sensors.append(sensor)
    return sensors
