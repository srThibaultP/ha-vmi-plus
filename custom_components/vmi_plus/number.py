"""Summer supply-air temperature limit (register 0x17) of the VMI+ unit.

App screen "Simplified configuration -> During the summer": the unit limits
incoming air flow as much as possible when the outdoor temperature is above
this value. Read back from the status frame (offset 38), see PROTOCOL.md.
"""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import REG_SUMMER_LIMIT, SUMMER_LIMIT_MAX, SUMMER_LIMIT_MIN
from .device import VmiPlusDevice
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = entry.runtime_data
    async_add_entities([VmiPlusSummerLimitNumber(device, entry)])


class VmiPlusSummerLimitNumber(VmiPlusEntity, NumberEntity):
    _attr_name = "Limite température été"
    _attr_icon = "mdi:sun-thermometer"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = SUMMER_LIMIT_MIN
    _attr_native_max_value = SUMMER_LIMIT_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_summer_limit"
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))

    def _on_update(self) -> None:
        data = self._device.telemetry.get("status")
        if data is not None and "summer_limit" in data:
            self._attr_native_value = data["summer_limit"]
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        await self._device.write_register(REG_SUMMER_LIMIT, int(value))
        self._attr_native_value = int(value)
        self.async_write_ha_state()
