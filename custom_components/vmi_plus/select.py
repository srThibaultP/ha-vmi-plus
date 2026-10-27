"""Ventilation speed of the VMI+ unit.

A select rather than a fan: the unit always ventilates and cannot be turned off.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from vmi_plus_ble import Speed

from .coordinator import VmiPlusConfigEntry, VmiPlusCoordinator
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1

SPEEDS = {"low": Speed.LOW, "medium": Speed.MEDIUM, "high": Speed.HIGH}
_OPTIONS = {speed: option for option, speed in SPEEDS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VmiPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Adds the speed select."""
    async_add_entities([VmiPlusSpeedSelect(entry.runtime_data)])


class VmiPlusSpeedSelect(VmiPlusEntity, SelectEntity):
    """Speed: low / medium / high."""

    _attr_translation_key = "speed"
    _attr_options = list(SPEEDS)

    def __init__(self, coordinator: VmiPlusCoordinator) -> None:
        super().__init__(coordinator, "speed")

    @property
    def current_option(self) -> str | None:
        """Speed read from the unit."""
        status = self.coordinator.data.status
        if status is None or status.speed is None:
            return None
        return _OPTIONS[status.speed]

    async def async_select_option(self, option: str) -> None:
        """Changes the speed."""
        await self.coordinator.async_command(self.coordinator.client.set_speed(SPEEDS[option]))
