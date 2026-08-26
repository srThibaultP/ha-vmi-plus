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
    python3 vmi_ble.py --address AA:BB:CC:DD:EE:FF listen   # affiche les notifications brutes
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

    args = parser.parse_args()
    if args.command != "scan" and not args.address:
        parser.error("--address est requis pour cette commande (utilise `scan` pour le trouver)")

    asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
