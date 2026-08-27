"""Tests du module protocole (checksum, construction/décodage de trames).

`protocol.py` n'a aucune dépendance à Home Assistant : chargé directement par
chemin de fichier (plutôt qu'importé via `custom_components.vmi_plus`) pour ne
pas nécessiter d'installer `homeassistant` juste pour ces tests.
Lancer avec : python3 -m unittest discover -s tests
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_PROTOCOL_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "vmi_plus"
    / "protocol.py"
)
_spec = importlib.util.spec_from_file_location("vmi_plus_protocol", _PROTOCOL_PATH)
protocol = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = protocol
_spec.loader.exec_module(protocol)


class BuildFrameTests(unittest.TestCase):
    """Trames de commande vérifiées par capture BLE réelle (voir PROTOCOL.md)."""

    def test_speed_frames(self) -> None:
        self.assertEqual(protocol.build_frame(0x18, 0x00).hex(), "a5b610060518000000000b")
        self.assertEqual(protocol.build_frame(0x18, 0x01).hex(), "a5b610060518000000010a")
        self.assertEqual(protocol.build_frame(0x18, 0x02).hex(), "a5b6100605180000000209")

    def test_boost_frames(self) -> None:
        self.assertEqual(protocol.build_frame(0x19, 0x01).hex(), "a5b610060519000000010b")
        self.assertEqual(protocol.build_frame(0x19, 0x00).hex(), "a5b610060519000000000a")

    def test_bypass_frames(self) -> None:
        self.assertEqual(protocol.build_frame(0x2F, 0x01).hex(), "a5b61006052f000000013d")
        self.assertEqual(protocol.build_frame(0x2F, 0x00).hex(), "a5b61006052f000000003c")

    def test_frame_length_and_header(self) -> None:
        frame = protocol.build_frame(0x1A, 0x00)
        self.assertEqual(len(frame), 11)
        self.assertEqual(frame[:5], bytes([0xA5, 0xB6, 0x10, 0x06, 0x05]))
        self.assertEqual(frame[5], 0x1A)
        self.assertEqual(frame[6:9], b"\x00\x00\x00")


class ParseNotificationTests(unittest.TestCase):
    def test_rejects_short_or_unmagic_frames(self) -> None:
        self.assertIsNone(protocol.parse_notification(b""))
        self.assertIsNone(protocol.parse_notification(b"\xa5\xb6"))
        self.assertIsNone(protocol.parse_notification(bytes([0x00, 0x00, 0x01] + [0] * 40)))

    def test_unknown_type_returns_none(self) -> None:
        frame = bytes([0xA5, 0xB6, 0x99]) + bytes(40)
        self.assertIsNone(protocol.parse_notification(frame))

    def test_status_frame_night_boost(self) -> None:
        # Offset [33] = 0x00 -> mode nuit activé (logique inversée, voir PROTOCOL.md)
        frame_on = bytearray([0xA5, 0xB6, 0x01] + [0] * 40)
        frame_on[33] = 0x00
        parsed = protocol.parse_notification(bytes(frame_on))
        self.assertEqual(parsed, {"type": "status", "night_boost": True})

        frame_off = bytearray([0xA5, 0xB6, 0x01] + [0] * 40)
        frame_off[33] = 0x01
        parsed = protocol.parse_notification(bytes(frame_off))
        self.assertEqual(parsed, {"type": "status", "night_boost": False})

    def test_status_frame_too_short_returns_none(self) -> None:
        frame = bytes([0xA5, 0xB6, 0x01] + [0] * 30)  # < 34 octets
        self.assertIsNone(protocol.parse_notification(frame))

    def test_probe_frame_temperature_humidity(self) -> None:
        frame = bytearray([0xA5, 0xB6, 0x03] + [0] * 10)
        frame[6] = 28
        frame[8] = 56
        parsed = protocol.parse_notification(bytes(frame))
        self.assertEqual(parsed, {"type": "probe", "temperature": 28, "humidity": 56})

    def test_remote_frame_temperature_humidity(self) -> None:
        frame = bytearray([0xA5, 0xB6, 0x02] + [0] * 15)
        frame[11] = 24
        frame[13] = 74
        parsed = protocol.parse_notification(bytes(frame))
        self.assertEqual(parsed, {"type": "remote", "temperature": 24, "humidity": 74})


if __name__ == "__main__":
    unittest.main()
