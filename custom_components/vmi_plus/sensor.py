"""Sensors of the VMI+ unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfArea,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from vmi_plus_ble import VmiPlusState
from vmi_plus_ble.const import PREHEAT_TYPES, SEASONS

from .coordinator import VmiPlusConfigEntry, VmiPlusCoordinator
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VmiPlusSensorEntityDescription(SensorEntityDescription):
    """Sensor computed from the decoded frames; None when not read yet."""

    value_fn: Callable[[VmiPlusState], StateType]


def _status[T](getter: Callable[..., T]) -> Callable[[VmiPlusState], T | None]:
    return lambda state: getter(state.status) if state.status else None


def _probe(state: VmiPlusState, field: str) -> int | None:
    probe = state.probes.main if state.probes else None
    return getattr(probe, field) if probe else None


def _remote(state: VmiPlusState, field: str) -> int | None:
    remote = state.sensors.remote_control if state.sensors else None
    return getattr(remote, field) if remote else None


def _air_quality(state: VmiPlusState, field: str) -> int | None:
    sensor = state.sensors.air_quality if state.sensors else None
    return getattr(sensor, field) if sensor else None


SENSORS: tuple[VmiPlusSensorEntityDescription, ...] = (
    VmiPlusSensorEntityDescription(
        key="remote_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: _remote(state, "temperature"),
    ),
    VmiPlusSensorEntityDescription(
        key="remote_humidity",
        translation_key="room_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: _remote(state, "humidity"),
    ),
    VmiPlusSensorEntityDescription(
        key="probe_temperature",
        translation_key="probe_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: _probe(state, "temperature"),
    ),
    VmiPlusSensorEntityDescription(
        key="probe_humidity",
        translation_key="probe_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: _probe(state, "humidity"),
    ),
    VmiPlusSensorEntityDescription(
        key="status_filter_days",
        translation_key="filter_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=_status(lambda status: status.filter_days),
    ),
    VmiPlusSensorEntityDescription(
        key="status_air_flow",
        translation_key="air_flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_status(lambda status: status.air_flow),
    ),
    VmiPlusSensorEntityDescription(
        key="status_season",
        translation_key="season",
        device_class=SensorDeviceClass.ENUM,
        options=list(SEASONS.values()),
        value_fn=_status(lambda status: status.season),
    ),
    VmiPlusSensorEntityDescription(
        key="status_operating_days",
        translation_key="operating_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_status(lambda status: status.operating_days),
    ),
    VmiPlusSensorEntityDescription(
        key="status_software_version",
        translation_key="software_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_status(lambda status: status.software_version),
    ),
    VmiPlusSensorEntityDescription(
        key="status_volume",
        translation_key="volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_status(lambda status: status.volume),
    ),
    VmiPlusSensorEntityDescription(
        key="status_surface",
        translation_key="surface",
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_status(lambda status: status.surface),
    ),
    VmiPlusSensorEntityDescription(
        key="status_preheat_type",
        translation_key="preheat_type",
        device_class=SensorDeviceClass.ENUM,
        options=list(PREHEAT_TYPES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_status(lambda status: status.preheat_type),
    ),
    VmiPlusSensorEntityDescription(
        key="bypass_state_position",
        translation_key="bypass_position",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.bypass.position if state.bypass else None,
    ),
    VmiPlusSensorEntityDescription(
        key="bypass_state_temperature",
        translation_key="bypass_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.bypass.temperature if state.bypass else None,
    ),
    VmiPlusSensorEntityDescription(
        key="sensors",
        translation_key="paired_sensors",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: len(state.sensors.sensors) if state.sensors else None,
    ),
)

# Sensors created only when the matching wireless device is paired to the unit.
AIR_QUALITY_SENSORS: tuple[VmiPlusSensorEntityDescription, ...] = (
    VmiPlusSensorEntityDescription(
        key="air_quality_voc",
        translation_key="air_quality_voc",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: _air_quality(state, "voc"),
    ),
    VmiPlusSensorEntityDescription(
        key="air_quality_temperature",
        translation_key="air_quality_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: _air_quality(state, "temperature"),
    ),
    VmiPlusSensorEntityDescription(
        key="air_quality_humidity",
        translation_key="air_quality_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: _air_quality(state, "humidity"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VmiPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Adds the sensors."""
    coordinator = entry.runtime_data
    descriptions = list(SENSORS)
    # The air-quality (VOC) sensor is optional: add its entities only for a unit
    # that actually has one paired, so other units are not cluttered with them.
    if coordinator.data.sensors and coordinator.data.sensors.air_quality:
        descriptions.extend(AIR_QUALITY_SENSORS)
    async_add_entities(VmiPlusSensor(coordinator, description) for description in descriptions)


class VmiPlusSensor(VmiPlusEntity, SensorEntity):
    """Sensor backed by a decoded frame."""

    entity_description: VmiPlusSensorEntityDescription

    def __init__(
        self, coordinator: VmiPlusCoordinator, description: VmiPlusSensorEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Value read from the unit."""
        return self.entity_description.value_fn(self.coordinator.data)
