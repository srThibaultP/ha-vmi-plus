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


def parse_notification(data: bytes) -> dict | None:
    """Décode une notification de télémétrie (voir PROTOCOL.md, section Télémétrie).

    Retourne un dict {"type": ..., ...champs...} pour les types reconnus
    (probe/remote), ou None pour un type non décodé ou une trame trop courte.
    """
    if len(data) < 3 or data[0] != 0xA5 or data[1] != 0xB6:
        return None

    frame_type = data[2]

    if frame_type == 0x01 and len(data) >= 34:
        # Statut général (vitesse/boost/bypass/modes spéciaux), déclenché par
        # l'écriture du registre 0x03 (ou 0x0b). Seul le drapeau "mode nuit"
        # (offset 33, logique inversée : 0x00=activé) est vérifié à ce stade
        # sur plusieurs échantillons réels ; le reste de la trame (vitesse
        # probable en offset 34, boost/bypass non localisés avec certitude)
        # reste à confirmer, voir PROTOCOL.md.
        return {"type": "status", "night_boost": data[33] == 0x00}

    if frame_type == 0x03 and len(data) >= 9:
        # Sonde interne "Probe N°1" (ex. sortie résistance), déclenchée par
        # l'écriture du registre 0x07.
        return {"type": "probe", "temperature": data[6], "humidity": data[8]}

    if frame_type == 0x02 and len(data) >= 14:
        # Sonde télécommande / pièce ventilée (ex. "Bathroom 1"), déclenchée
        # par l'écriture du registre 0x06.
        return {"type": "remote", "temperature": data[11], "humidity": data[13]}

    return None
