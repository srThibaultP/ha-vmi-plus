"""Entité fan : vitesse de ventilation (registre 0x18) de la centrale VMI+."""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LEVEL_TO_PERCENT, REG_SPEED, SPEED_COUNT, SPEED_VALUES
from .device import VmiPlusDevice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VmiPlusFan(device, entry)])


class VmiPlusFan(FanEntity):
    """La centrale VMCI ventile en continu : pas d'état 'off', seulement 3 vitesses."""

    _attr_has_entity_name = True
    _attr_name = "Ventilation"
    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_speed_count = SPEED_COUNT
    _attr_is_on = True

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_fan"
        self._attr_percentage: int | None = None

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            return
        level = min(
            (lvl for lvl, pct in LEVEL_TO_PERCENT.items() if pct >= percentage),
            default=3,
        )
        await self._device.write_register(REG_SPEED, SPEED_VALUES[level])
        self._attr_percentage = LEVEL_TO_PERCENT[level]
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self.async_set_percentage(percentage or LEVEL_TO_PERCENT[1])
