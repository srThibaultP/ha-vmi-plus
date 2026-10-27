"""Binary sensors read from the status frame."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from vmi_plus_ble import Status

from .coordinator import VmiPlusConfigEntry, VmiPlusCoordinator
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VmiPlusBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor computed from the status frame."""

    is_on_fn: Callable[[Status], bool]


BINARY_SENSORS: tuple[VmiPlusBinarySensorEntityDescription, ...] = (
    VmiPlusBinarySensorEntityDescription(
        key="bypass_open",
        translation_key="bypass",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=lambda status: status.bypass_open,
    ),
    VmiPlusBinarySensorEntityDescription(
        key="self_test",
        translation_key="self_test",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda status: not status.self_test_ok,
    ),
    VmiPlusBinarySensorEntityDescription(
        key="turbo_heater",
        translation_key="turbo_heater",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda status: status.turbo_heater,
    ),
    VmiPlusBinarySensorEntityDescription(
        key="gtc",
        translation_key="gtc",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda status: status.gtc,
    ),
    VmiPlusBinarySensorEntityDescription(
        key="action_in_progress",
        translation_key="action_in_progress",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda status: status.action_in_progress,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VmiPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Adds the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        VmiPlusBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class VmiPlusBinarySensor(VmiPlusEntity, BinarySensorEntity):
    """Binary sensor backed by the status frame."""

    entity_description: VmiPlusBinarySensorEntityDescription

    def __init__(
        self, coordinator: VmiPlusCoordinator, description: VmiPlusBinarySensorEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """State read from the unit."""
        status = self.coordinator.data.status
        return self.entity_description.is_on_fn(status) if status else None
