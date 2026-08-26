"""Construction des trames de commande du protocole VMI+.

Voir PROTOCOL.md pour la rétro-ingénierie complète (capture BLE réelle,
vérifiée trame par trame contre une centrale VMCI physique).
"""


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


def build_frame(register: int, value: int) -> bytes:
    """Construit une trame de commande registre/valeur de 11 octets."""
    data = bytes([0xA5, 0xB6, 0x10, 0x06, 0x05, register, 0, 0, 0, value])
    return data + bytes([checksum(data)])
