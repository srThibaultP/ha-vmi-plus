"""Sensors température/humidité des deux sondes de la centrale VMI+.

Alimentés par le canal de télémétrie (notifications BLE), déclenché par un
polling périodique — voir device.py et PROTOCOL.md.
"""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import VmiPlusDevice
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = entry.runtime_data
    async_add_entities(
        [
            VmiPlusSensor(device, entry, "probe", "temperature", "Température sonde interne",
                           SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
            VmiPlusSensor(device, entry, "probe", "humidity", "Humidité sonde interne",
                           SensorDeviceClass.HUMIDITY, PERCENTAGE),
            VmiPlusSensor(device, entry, "remote", "temperature", "Température pièce",
                           SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
            VmiPlusSensor(device, entry, "remote", "humidity", "Humidité pièce",
                           SensorDeviceClass.HUMIDITY, PERCENTAGE),
        ]
    )
    device.start_polling()


class VmiPlusSensor(VmiPlusEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        device: VmiPlusDevice,
        entry: ConfigEntry,
        telemetry_type: str,
        field: str,
        name: str,
        device_class: SensorDeviceClass,
        unit: str,
    ) -> None:
        super().__init__(device, entry)
        self._telemetry_type = telemetry_type
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{telemetry_type}_{field}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))
        self._on_update()

    def _on_update(self) -> None:
        data = self._device.telemetry.get(self._telemetry_type)
        if data is not None and self._field in data:
            self._attr_native_value = data[self._field]
            self.async_write_ha_state()
