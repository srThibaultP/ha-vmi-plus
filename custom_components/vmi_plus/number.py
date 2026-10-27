"""Temperature settings of the VMI+ unit (app screen "Simplified configuration")."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from vmi_plus_ble import Status, VmiPlusClient
from vmi_plus_ble.const import (
    PREHEAT_TARGET_MAX,
    PREHEAT_TARGET_MIN,
    SUMMER_LIMIT_MAX,
    SUMMER_LIMIT_MIN,
)

from .coordinator import VmiPlusConfigEntry, VmiPlusCoordinator
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VmiPlusNumberEntityDescription(NumberEntityDescription):
    """Temperature setting read from the status frame."""

    value_fn: Callable[[Status], int]
    set_fn: Callable[[VmiPlusClient, int], Coroutine[Any, Any, None]]


NUMBERS: tuple[VmiPlusNumberEntityDescription, ...] = (
    # Incoming air is not heated above this temperature in summer.
    VmiPlusNumberEntityDescription(
        key="summer_limit",
        translation_key="summer_limit",
        native_min_value=SUMMER_LIMIT_MIN,
        native_max_value=SUMMER_LIMIT_MAX,
        value_fn=lambda status: status.summer_limit,
        set_fn=lambda client, value: client.set_summer_limit(value),
    ),
    # Incoming air is preheated to this temperature in winter. The unit reports
    # 0 when preheating is off, shown as unknown since it is out of range.
    VmiPlusNumberEntityDescription(
        key="preheat_target",
        translation_key="preheat_target",
        native_min_value=PREHEAT_TARGET_MIN,
        native_max_value=PREHEAT_TARGET_MAX,
        value_fn=lambda status: status.preheat_target,
        set_fn=lambda client, value: client.set_preheat_target(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VmiPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Adds the temperature settings."""
    coordinator = entry.runtime_data
    async_add_entities(VmiPlusNumber(coordinator, description) for description in NUMBERS)


class VmiPlusNumber(VmiPlusEntity, NumberEntity):
    """Temperature setting."""

    entity_description: VmiPlusNumberEntityDescription
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: VmiPlusCoordinator, description: VmiPlusNumberEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | None:
        """Setting read from the unit."""
        status = self.coordinator.data.status
        if status is None:
            return None
        value = self.entity_description.value_fn(status)
        return value if value >= self.native_min_value else None

    async def async_set_native_value(self, value: float) -> None:
        """Changes the setting."""
        await self.coordinator.async_command(
            self.entity_description.set_fn(self.coordinator.client, int(value))
        )
