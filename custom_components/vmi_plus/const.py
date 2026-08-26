"""Constantes pour l'intégration VMI+ (Ventilairsec)."""

DOMAIN = "vmi_plus"
MANUFACTURER = "Ventilairsec"
MODEL = "VMCI"

# UUID vérifiés par capture BLE réelle contre une centrale VMCI "Urban".
# Voir PROTOCOL.md à la racine du dépôt pour le détail de la rétro-ingénierie.
SERVICE_CONTROL_UUID = "0003cbbb-0000-1000-8000-00805f9b0131"
CHAR_CONTROL_UUID = "0003cbb1-0000-1000-8000-00805f9b0131"
SERVICE_TELEMETRY_UUID = "0003cab5-0000-1000-8000-00805f9b0131"
CHAR_TELEMETRY_UUID = "0003caa2-0000-1000-8000-00805f9b0131"

REG_SPEED = 0x18
REG_BOOST = 0x19
REG_BYPASS = 0x2F
# Holiday mode (écran Special modes). OFF (0x00) confirmé par capture BLE
# réelle ; ON (0x01) déduit par cohérence avec REG_BOOST/REG_BYPASS (même
# convention 0/1 partout ailleurs dans ce protocole) — voir PROTOCOL.md.
REG_HOLIDAY = 0x1A

# L'app officielle ne nomme les 3 vitesses que "mode 1/2/3" (débit théorique en
# m3/h configuré par l'installateur, propre à chaque centrale) — aucun nom
# universel côté Ventilairsec. On utilise Faible/Moyenne/Forte, plus parlant
# dans Home Assistant, tout en évitant "Boost" (déjà pris par switch.*_boost).
SPEED_OPTIONS = {"Faible": 0x00, "Moyenne": 0x01, "Forte": 0x02}

# Registres de lecture : l'écriture ne fait que déclencher une notification de
# télémétrie (types 0x01/0x02/0x03, voir protocol.py et PROTOCOL.md), elle ne
# modifie aucun état de la centrale.
POLL_REG_STATUS = 0x03  # -> notification type 0x01 (vitesse/boost/bypass/RPM)
POLL_REG_REMOTE = 0x06  # -> notification type 0x02 (sonde télécommande/pièce)
POLL_REG_PROBE = 0x07  # -> notification type 0x03 (sonde interne "Probe N°1")
POLL_INTERVAL_SECONDS = 10
