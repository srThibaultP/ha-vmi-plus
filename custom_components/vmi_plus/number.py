"""Temperature settings of the VMI+ unit (app screen "Simplified configuration").

- Summer limit (register 0x17, status offset 38): incoming air flow is limited
  as much as possible when the outdoor temperature is above this value.
- Preheat target (register 0x1c, status offset 35): the blown air is preheated
  to this temperature. 0 means "no preheating"; writing a temperature turns
  preheating back on (same as the app).

All values confirmed by changing them in the app and reading the status frame,
see PROTOCOL.md.
"""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    PREHEAT_TARGET_MAX,
    PREHEAT_TARGET_MIN,
    REG_PREHEAT_TARGET,
    REG_SUMMER_LIMIT,
    SUMMER_LIMIT_MAX,
    SUMMER_LIMIT_MIN,
)
from .device import VmiPlusDevice
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = entry.runtime_data
    async_add_entities(
        [
            VmiPlusTemperatureNumber(
                device, entry, "summer_limit", "Limite température été", "mdi:sun-thermometer",
                REG_SUMMER_LIMIT, SUMMER_LIMIT_MIN, SUMMER_LIMIT_MAX,
            ),
            VmiPlusTemperatureNumber(
                device, entry, "preheat_target", "Température de préchauffage", "mdi:heat-wave",
                REG_PREHEAT_TARGET, PREHEAT_TARGET_MIN, PREHEAT_TARGET_MAX,
            ),
        ]
    )


class VmiPlusTemperatureNumber(VmiPlusEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        device: VmiPlusDevice,
        entry: ConfigEntry,
        field: str,
        name: str,
        icon: str,
        register: int,
        min_value: int,
        max_value: int,
    ) -> None:
        super().__init__(device, entry)
        self._field = field
        self._register = register
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{field}"
        self._attr_native_value: float | None = None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))

    def _on_update(self) -> None:
        data = self._device.telemetry.get("status")
        if data is not None and self._field in data:
            # 0 (preheating off) is outside the settable range: show it as unknown.
            value = data[self._field]
            self._attr_native_value = value if value >= self._attr_native_min_value else None
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        await self._device.write_register(self._register, int(value))
        self._attr_native_value = int(value)
        self.async_write_ha_state()
