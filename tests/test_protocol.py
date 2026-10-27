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
        frame_on = bytearray([0xA5, 0xB6, 0x01] + [0] * 60)
        frame_on[33] = 0x00
        parsed = protocol.parse_notification(bytes(frame_on))
        self.assertEqual(parsed["night_boost"], True)

        frame_off = bytearray([0xA5, 0xB6, 0x01] + [0] * 60)
        frame_off[33] = 0x01
        parsed = protocol.parse_notification(bytes(frame_off))
        self.assertEqual(parsed["night_boost"], False)

    def test_status_frame_speed_boost_bypass_holiday(self) -> None:
        # Offsets confirmés par capture BLE réelle (changement d'un seul
        # réglage à la fois, diff avant/après), voir PROTOCOL.md.
        frame = bytearray([0xA5, 0xB6, 0x01] + [0] * 60)
        frame[34] = 0x02  # vitesse "Forte"
        frame[43] = 0x01  # holiday ON
        frame[44] = 0x01  # boost ON
        frame[53] = 0x01  # bypass ON
        parsed = protocol.parse_notification(bytes(frame))
        self.assertEqual(
            parsed,
            {
                "type": "status",
                "night_boost": True,  # offset [33] laissé à 0x00 par défaut ici
                "speed": 0x02,
                "holiday": True,
                "boost": True,
                "bypass": True,
                "operating_days": 0,
                "summer_limit": 0,
            },
        )

    def test_status_frame_real_capture_operating_days(self) -> None:
        # Real frame captured 2026-10-27 (app showed "Operating days : 1084",
        # speed Moyenne, night boost on, bypass on).
        frame = bytes.fromhex(
            "a5b601063729013122001fffffffff00012832026411c80001003c04000000"
            "0009000112140518b11d160b00000000c20102010200013400100b0000c7"
        )
        parsed = protocol.parse_notification(frame)
        self.assertEqual(parsed["operating_days"], 1084)
        self.assertEqual(parsed["speed"], 0x01)
        self.assertTrue(parsed["night_boost"])
        self.assertTrue(parsed["bypass"])
        self.assertEqual(parsed["summer_limit"], 24)

    def test_summer_limit_frames(self) -> None:
        # Captured 2026-10-27: summer limit set to 26 °C, then back to 24 °C.
        self.assertEqual(protocol.build_frame(0x17, 26).hex(), "a5b6100605170000001a1e")
        self.assertEqual(protocol.build_frame(0x17, 24).hex(), "a5b610060517000000181c")

    def test_status_frame_too_short_returns_none(self) -> None:
        frame = bytes([0xA5, 0xB6, 0x01] + [0] * 40)  # < 54 octets
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
