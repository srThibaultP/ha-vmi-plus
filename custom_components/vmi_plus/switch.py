"""Switches Boost (0x19) et Bypass (0x2f) de la centrale VMI+."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
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
            VmiPlusConnectionSwitch(device, entry),
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


class VmiPlusConnectionSwitch(SwitchEntity):
    """Active/désactive la connexion BLE à la centrale.

    La centrale n'accepte qu'une seule connexion GATT à la fois : désactiver ce switch
    déconnecte Home Assistant et libère la centrale (ex. pour repasser la main à l'app
    officielle VMI+ sans avoir à supprimer l'intégration).
    """

    _attr_has_entity_name = True
    _attr_name = "Connexion Bluetooth"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_is_on = True

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        self._device = device
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_connection_enabled"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_enabled(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_enabled(False)
        self._attr_is_on = False
        self.async_write_ha_state()
