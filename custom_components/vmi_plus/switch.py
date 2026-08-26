"""Switches Boost (0x19) et Bypass (0x2f) de la centrale VMI+."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REG_BOOST, REG_BYPASS
from .device import VmiPlusDevice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            VmiPlusSwitch(device, entry, "boost", "Boost", REG_BOOST),
            VmiPlusSwitch(device, entry, "bypass", "Bypass", REG_BYPASS),
        ]
    )


class VmiPlusSwitch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self, device: VmiPlusDevice, entry: ConfigEntry, key: str, name: str, register: int
    ) -> None:
        self._device = device
        self._register = register
        self._attr_name = name
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{key}"
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.write_register(self._register, 0x01)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.write_register(self._register, 0x00)
        self._attr_is_on = False
        self.async_write_ha_state()
