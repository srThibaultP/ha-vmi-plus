#!/usr/bin/env python3
"""
Client BLE en ligne de commande pour les centrales VMI+ (Ventilairsec), famille VMCI.

Protocole reverse-engineered par capture BLE réelle — voir PROTOCOL.md pour les détails.
Utilise `bleak` (pip install bleak), fonctionne sur Linux/macOS/Windows.

Usage:
    python3 vmi_ble.py scan
    python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF speed 1|2|3
    python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF boost on|off
    python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF bypass on|off
    python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF raw --reg 0x18 --val 0x02
    python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF listen    # affiche les notifications brutes
    python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF monitor   # affiche température/humidité décodées
"""
import argparse
import asyncio
import sys

from bleak import BleakClient, BleakScanner

SERVICE_CONTROL_UUID = "0003cbbb-0000-1000-8000-00805f9b0131"
CHAR_CONTROL_UUID = "0003cbb1-0000-1000-8000-00805f9b0131"
SERVICE_TELEMETRY_UUID = "0003cab5-0000-1000-8000-00805f9b0131"
CHAR_TELEMETRY_UUID = "0003caa2-0000-1000-8000-00805f9b0131"

REG_SPEED = 0x18
REG_BOOST = 0x19
REG_BYPASS = 0x2F

# Registres de lecture : l'écriture déclenche une notification de télémétrie,
# elle ne modifie aucun état de la centrale (voir PROTOCOL.md).
REG_POLL_STATUS = 0x03  # -> notification type 0x01
REG_POLL_REMOTE = 0x06  # -> notification type 0x02 (sonde télécommande/pièce)
REG_POLL_PROBE = 0x07  # -> notification type 0x03 (sonde interne)

SPEED_VALUES = {1: 0x00, 2: 0x01, 3: 0x02}


def checksum(data: bytes) -> int:
    crc = 0
    for byte in data:
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


def parse_notification(data: bytes) -> dict | None:
    """Décode une notification de télémétrie (voir PROTOCOL.md, section Télémétrie)."""
    if len(data) < 3 or data[0] != 0xA5 or data[1] != 0xB6:
        return None
    frame_type = data[2]
    if frame_type == 0x03 and len(data) >= 9:
        return {"type": "probe", "temperature": data[6], "humidity": data[8]}
    if frame_type == 0x02 and len(data) >= 14:
        return {"type": "remote", "temperature": data[11], "humidity": data[13]}
    return None


async def cmd_scan(_args):
    print("Scan BLE (8s)...")
    devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
    for device, adv in devices.values():
        uuids = adv.service_uuids or []
        marker = "  <-- VMI+ ?" if SERVICE_CONTROL_UUID in [u.lower() for u in uuids] else ""
        print(f"{device.address}  {device.name!r:20s} rssi={adv.rssi}{marker}")


async def _write(address: str, register: int, value: int):
    frame = build_frame(register, value)
    print(f"-> trame: {frame.hex()}")
    async with BleakClient(address) as client:
        await client.write_gatt_char(CHAR_CONTROL_UUID, frame, response=True)
    print("OK")


async def cmd_speed(args):
    await _write(args.address, REG_SPEED, SPEED_VALUES[args.level])


async def cmd_boost(args):
    await _write(args.address, REG_BOOST, 0x01 if args.state == "on" else 0x00)


async def cmd_bypass(args):
    await _write(args.address, REG_BYPASS, 0x01 if args.state == "on" else 0x00)


async def cmd_raw(args):
    reg = int(args.reg, 0)
    val = int(args.val, 0)
    await _write(args.address, reg, val)


async def cmd_listen(args):
    def handler(_char, data: bytearray):
        print(f"[notify] {data.hex()}")

    async with BleakClient(args.address) as client:
        await client.start_notify(CHAR_TELEMETRY_UUID, handler)
        print("Écoute des notifications (Ctrl+C pour arrêter)...")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        await client.stop_notify(CHAR_TELEMETRY_UUID)


async def cmd_monitor(args):
    """Poll les registres de lecture en boucle et affiche température/humidité décodées."""

    def handler(_char, data: bytearray):
        parsed = parse_notification(bytes(data))
        if parsed is None:
            return
        label = "Sonde interne" if parsed["type"] == "probe" else "Sonde pièce"
        print(f"{label:15s} {parsed['temperature']:3d}°C  {parsed['humidity']:3d}%")

    async with BleakClient(args.address) as client:
        await client.start_notify(CHAR_TELEMETRY_UUID, handler)
        print("Polling toutes les 10s (Ctrl+C pour arrêter)...")
        try:
            while True:
                for register in (REG_POLL_STATUS, REG_POLL_PROBE, REG_POLL_REMOTE):
                    frame = build_frame(register, 0x00)
                    await client.write_gatt_char(CHAR_CONTROL_UUID, frame, response=True)
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            pass
        await client.stop_notify(CHAR_TELEMETRY_UUID)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--address", help="Adresse MAC (ou UUID sur macOS) de la centrale")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan").set_defaults(func=cmd_scan)

    p = sub.add_parser("speed")
    p.add_argument("level", type=int, choices=[1, 2, 3])
    p.set_defaults(func=cmd_speed)

    p = sub.add_parser("boost")
    p.add_argument("state", choices=["on", "off"])
    p.set_defaults(func=cmd_boost)

    p = sub.add_parser("bypass")
    p.add_argument("state", choices=["on", "off"])
    p.set_defaults(func=cmd_bypass)

    p = sub.add_parser("raw")
    p.add_argument("--reg", required=True, help="ex: 0x18")
    p.add_argument("--val", required=True, help="ex: 0x02")
    p.set_defaults(func=cmd_raw)

    p = sub.add_parser("listen")
    p.set_defaults(func=cmd_listen)

    p = sub.add_parser("monitor")
    p.set_defaults(func=cmd_monitor)

    args = parser.parse_args()
    if args.command != "scan" and not args.address:
        parser.error("--address est requis pour cette commande (utilise `scan` pour le trouver)")

    asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
