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

from .const import DOMAIN
from .device import VmiPlusDevice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = hass.data[DOMAIN][entry.entry_id]
    address = entry.data[CONF_ADDRESS]
    async_add_entities(
        [
            VmiPlusSensor(device, address, "probe", "temperature", "Température sonde interne",
                           SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
            VmiPlusSensor(device, address, "probe", "humidity", "Humidité sonde interne",
                           SensorDeviceClass.HUMIDITY, PERCENTAGE),
            VmiPlusSensor(device, address, "remote", "temperature", "Température pièce",
                           SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
            VmiPlusSensor(device, address, "remote", "humidity", "Humidité pièce",
                           SensorDeviceClass.HUMIDITY, PERCENTAGE),
        ]
    )
    device.start_polling()


class VmiPlusSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        device: VmiPlusDevice,
        address: str,
        telemetry_type: str,
        field: str,
        name: str,
        device_class: SensorDeviceClass,
        unit: str,
    ) -> None:
        self._device = device
        self._telemetry_type = telemetry_type
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{address}_{telemetry_type}_{field}"
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
