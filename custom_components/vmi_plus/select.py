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

from .const import REG_SPEED, SPEED_OPTIONS
from .device import VmiPlusDevice
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = entry.runtime_data
    async_add_entities([VmiPlusSpeedSelect(device, entry)])


class VmiPlusSpeedSelect(VmiPlusEntity, SelectEntity):
    _attr_name = "Vitesse"
    _attr_icon = "mdi:fan"
    _attr_options = list(SPEED_OPTIONS)

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_speed"
        self._attr_current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        # Entité write-only : sans ceci, `available` ne serait réévalué et
        # poussé à HA qu'à la prochaine action utilisateur, et resterait
        # bloqué sur son état au démarrage si la connexion BLE fluctue
        # entre-temps (voir le callback régulier ajouté dans device.py).
        self.async_on_remove(self._device.add_update_listener(self.async_write_ha_state))

    async def async_select_option(self, option: str) -> None:
        await self._device.write_register(REG_SPEED, SPEED_OPTIONS[option])
        self._attr_current_option = option
        self.async_write_ha_state()
