"""Buttons: locate the unit (LED blink) and declare a new filter.

The filter buttons send the app's "NewFilter" command (register 0x05) with the
lifespan in months, exactly like Maintenance -> Filter change in the app: the
filter counter restarts. Only press them after fitting a new filter.
"""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import FILTER_LIFESPANS, REG_LOCATE, REG_NEW_FILTER
from .device import VmiPlusDevice
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = entry.runtime_data
    entities: list[ButtonEntity] = [
        VmiPlusButton(device, entry, "locate", "Localiser (LED)", "mdi:led-on", REG_LOCATE, 0x00)
    ]
    entities += [
        VmiPlusButton(
            device, entry, f"new_filter_{months}", f"Filtre changé ({months} mois)",
            "mdi:air-filter", REG_NEW_FILTER, months,
        )
        for months in FILTER_LIFESPANS
    ]
    async_add_entities(entities)


class VmiPlusButton(VmiPlusEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        device: VmiPlusDevice,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
        register: int,
        value: int,
    ) -> None:
        super().__init__(device, entry)
        self._register = register
        self._value = value
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{key}"

    async def async_press(self) -> None:
        await self._device.write_register(self._register, self._value)
