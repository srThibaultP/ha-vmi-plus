"""Constants of the VMI+ integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "vmi_plus"
MANUFACTURER = "Ventilairsec"

# The unit pushes nothing on its own: its state is read every 10 seconds so that
# changes made with the remote control or the official app show up quickly.
UPDATE_INTERVAL = timedelta(seconds=10)
# The bypass state changes slowly: read it once a minute.
BYPASS_EVERY = 6

SERVICE_SET_DAY_SCHEDULE = "set_day_schedule"
ATTR_DAY = "day"
ATTR_SLOTS = "slots"
ATTR_START = "start"
ATTR_SPEED = "speed"
ATTR_TEMPERATURE = "temperature"
