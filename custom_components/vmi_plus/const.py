"""Constantes pour l'intégration VMI+ (Ventilairsec)."""

DOMAIN = "vmi_plus"

# UUID vérifiés par capture BLE réelle contre une centrale VMCI "Urban".
# Voir PROTOCOL.md à la racine du dépôt pour le détail de la rétro-ingénierie.
SERVICE_CONTROL_UUID = "0003cbbb-0000-1000-8000-00805f9b0131"
CHAR_CONTROL_UUID = "0003cbb1-0000-1000-8000-00805f9b0131"
SERVICE_TELEMETRY_UUID = "0003cab5-0000-1000-8000-00805f9b0131"
CHAR_TELEMETRY_UUID = "0003caa2-0000-1000-8000-00805f9b0131"

REG_SPEED = 0x18
REG_BOOST = 0x19
REG_BYPASS = 0x2F

SPEED_OPTIONS = {"Vitesse 1": 0x00, "Vitesse 2": 0x01, "Vitesse 3": 0x02}

# Registres de lecture : l'écriture ne fait que déclencher une notification de
# télémétrie (types 0x01/0x02/0x03, voir protocol.py et PROTOCOL.md), elle ne
# modifie aucun état de la centrale.
POLL_REG_STATUS = 0x03  # -> notification type 0x01 (vitesse/boost/bypass/RPM)
POLL_REG_REMOTE = 0x06  # -> notification type 0x02 (sonde télécommande/pièce)
POLL_REG_PROBE = 0x07  # -> notification type 0x03 (sonde interne "Probe N°1")
POLL_INTERVAL_SECONDS = 10
