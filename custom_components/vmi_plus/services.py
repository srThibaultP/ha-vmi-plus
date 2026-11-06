"""Actions of the VMI+ integration."""

from __future__ import annotations

from typing import Any

import probatio
from homeassistant.components.switch.const import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
from vmi_plus_ble.const import (
    NO_SLOT_TEMPERATURE,
    PREHEAT_OFF,
    PREHEAT_TARGET_MAX,
    PREHEAT_TARGET_MIN,
    TIME_SLOTS_PER_DAY,
)

from .const import (
    ATTR_DAY,
    ATTR_SLOTS,
    ATTR_SPEED,
    ATTR_START,
    ATTR_TEMPERATURE,
    DOMAIN,
    SERVICE_SET_DAY_SCHEDULE,
)
from .select import SPEEDS

SET_DAY_SCHEDULE_SCHEMA: dict[str | probatio.Marker, Any] = {
    probatio.Required(ATTR_DAY): probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=7)),
    probatio.Optional(ATTR_SLOTS, default=[]): probatio.All(
        probatio.EnsureList(),
        probatio.Length(max=TIME_SLOTS_PER_DAY),
        [
            {
                probatio.Required(ATTR_START): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=23)
                ),
                probatio.Required(ATTR_SPEED): probatio.In(list(SPEEDS)),
                probatio.Optional(ATTR_TEMPERATURE, default=NO_SLOT_TEMPERATURE): probatio.Any(
                    probatio.All(
                        probatio.Coerce(int),
                        probatio.Range(min=PREHEAT_TARGET_MIN, max=PREHEAT_TARGET_MAX),
                    ),
                    probatio.In([PREHEAT_OFF, NO_SLOT_TEMPERATURE]),
                ),
            }
        ],
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Registers the actions, once for the whole integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_DAY_SCHEDULE,
        entity_domain=SWITCH_DOMAIN,
        schema=SET_DAY_SCHEDULE_SCHEMA,
        func="async_set_day_schedule",
    )
