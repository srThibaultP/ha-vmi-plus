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
from homeassistant.const import (
    CONF_ADDRESS,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import VmiPlusDevice
from .protocol import SEASONS
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
            VmiPlusSensor(device, entry, "status", "operating_days", "Jours de fonctionnement",
                           SensorDeviceClass.DURATION, UnitOfTime.DAYS,
                           SensorStateClass.TOTAL_INCREASING, EntityCategory.DIAGNOSTIC),
            VmiPlusSensor(device, entry, "status", "air_flow", "Débit théorique",
                           SensorDeviceClass.VOLUME_FLOW_RATE,
                           UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR),
            VmiPlusSensor(device, entry, "status", "filter_days", "Autonomie filtre",
                           SensorDeviceClass.DURATION, UnitOfTime.DAYS),
            VmiPlusSensor(device, entry, "status", "season", "Saison",
                           SensorDeviceClass.ENUM, None, None, None, list(SEASONS.values())),
            VmiPlusSensor(device, entry, "status", "software_version", "Version logicielle",
                           None, None, None, EntityCategory.DIAGNOSTIC),
            VmiPlusSensor(device, entry, "bypass_state", "position", "Position bypass",
                           None, PERCENTAGE, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
            VmiPlusSensorsListSensor(device, entry),
        ]
    )
    device.start_polling()


class VmiPlusSensor(VmiPlusEntity, SensorEntity):
    def __init__(
        self,
        device: VmiPlusDevice,
        entry: ConfigEntry,
        telemetry_type: str,
        field: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
        entity_category: EntityCategory | None = None,
        options: list[str] | None = None,
    ) -> None:
        super().__init__(device, entry)
        self._telemetry_type = telemetry_type
        self._field = field
        self._attr_name = name
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{telemetry_type}_{field}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._attr_options = options

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))
        self._on_update()

    def _on_update(self) -> None:
        data = self._device.telemetry.get(self._telemetry_type)
        if data is not None and self._field in data:
            self._attr_native_value = data[self._field]
            self.async_write_ha_state()


class VmiPlusSensorsListSensor(VmiPlusEntity, SensorEntity):
    """Number of wireless sensors paired with the unit ("Sensor management").

    The attributes list each sensor (id, room, kind and readings) as decoded
    from the SensorsState frame (0x02), see PROTOCOL.md.
    """

    _attr_name = "Capteurs associés"
    _attr_icon = "mdi:access-point-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_sensors"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))
        self._on_update()

    def _on_update(self) -> None:
        data = self._device.telemetry.get("remote")
        if data is not None and "sensors" in data:
            self._attr_native_value = len(data["sensors"])
            self._attr_extra_state_attributes = {"sensors": data["sensors"]}
            self.async_write_ha_state()
