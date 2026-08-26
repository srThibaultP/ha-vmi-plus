"""Sélecteur de vitesse de ventilation (registre 0x18) de la centrale VMI+.

Une entité `select` plutôt que `fan` : la centrale ventile en continu et ne peut pas
être éteinte, alors que le domaine `fan` de Home Assistant impose toujours une position
"Off" (pourcentage 0) dans son interface.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REG_SPEED, SPEED_OPTIONS
from .device import VmiPlusDevice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VmiPlusSpeedSelect(device, entry)])


class VmiPlusSpeedSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Vitesse"
    _attr_icon = "mdi:fan"
    _attr_options = list(SPEED_OPTIONS)

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_speed"
        self._attr_current_option: str | None = None

    async def async_select_option(self, option: str) -> None:
        await self._device.write_register(REG_SPEED, SPEED_OPTIONS[option])
        self._attr_current_option = option
        self.async_write_ha_state()
