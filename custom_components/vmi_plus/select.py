"""Selects of the VMI+ unit: ventilation speed, VOC sensor measurement period.

The speed is a select rather than a fan: the unit always ventilates and cannot be
turned off.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from vmi_plus_ble import Speed
from vmi_plus_ble.const import SENSOR_PERIODS

from .coordinator import VmiPlusConfigEntry, VmiPlusCoordinator
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1

SPEEDS = {"low": Speed.LOW, "medium": Speed.MEDIUM, "high": Speed.HIGH}
_OPTIONS = {speed: option for option, speed in SPEEDS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VmiPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Adds the speed select, and the VOC sensor's period when one is paired."""
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [VmiPlusSpeedSelect(coordinator)]
    sensors = coordinator.data.sensors
    if sensors and (air_quality := sensors.air_quality):
        entities.append(VmiPlusSensorPeriodSelect(coordinator, air_quality.id))
    async_add_entities(entities)


class VmiPlusSpeedSelect(VmiPlusEntity, SelectEntity):
    """Speed: low / medium / high."""

    _attr_translation_key = "speed"
    _attr_options = list(SPEEDS)

    def __init__(self, coordinator: VmiPlusCoordinator) -> None:
        super().__init__(coordinator, "speed")

    @property
    def current_option(self) -> str | None:
        """Speed read from the unit."""
        status = self.coordinator.data.status
        if status is None or status.speed is None:
            return None
        return _OPTIONS[status.speed]

    async def async_select_option(self, option: str) -> None:
        """Changes the speed."""
        await self.coordinator.async_command(self.coordinator.client.set_speed(SPEEDS[option]))


class VmiPlusSensorPeriodSelect(VmiPlusEntity, SelectEntity, RestoreEntity):
    """Measurement period of the paired VOC sensor, in minutes.

    The unit cannot report the period back, so the entity shows the last value
    set from Home Assistant (unknown until then). Changing it restarts the VOC
    measurement, which needs about five periods to settle.
    """

    _attr_translation_key = "air_quality_period"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = [str(minutes) for minutes in SENSOR_PERIODS]
    _attr_assumed_state = True

    def __init__(self, coordinator: VmiPlusCoordinator, sensor_id: str) -> None:
        super().__init__(coordinator, "air_quality_period")
        self._sensor_id = sensor_id
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        """Restores the last period set."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state in self.options:
            self._attr_current_option = last.state

    async def async_select_option(self, option: str) -> None:
        """Sends the new period to the sensor through the unit."""
        await self.coordinator.async_command(
            self.coordinator.client.set_sensor_period(self._sensor_id, int(option))
        )
        self._attr_current_option = option
        self.async_write_ha_state()
