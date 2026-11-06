"""Buttons: locate the unit and declare a new filter.

The filter buttons restart the filter counter, like Maintenance -> Filter
change in the app: only press them after fitting a new filter.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from vmi_plus_ble import VmiPlusClient

from .coordinator import VmiPlusConfigEntry, VmiPlusCoordinator
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VmiPlusButtonEntityDescription(ButtonEntityDescription):
    """Button sending one client command."""

    press_fn: Callable[[VmiPlusClient], Coroutine[Any, Any, None]]


BUTTONS: tuple[VmiPlusButtonEntityDescription, ...] = (
    VmiPlusButtonEntityDescription(
        key="locate",
        translation_key="locate",
        entity_registry_enabled_default=False,
        press_fn=lambda client: client.locate(),
    ),
    VmiPlusButtonEntityDescription(
        key="new_filter_6",
        translation_key="new_filter_6",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.declare_new_filter(6),
    ),
    VmiPlusButtonEntityDescription(
        key="new_filter_12",
        translation_key="new_filter_12",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.declare_new_filter(12),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VmiPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Adds the buttons."""
    coordinator = entry.runtime_data
    async_add_entities(VmiPlusButton(coordinator, description) for description in BUTTONS)


class VmiPlusButton(VmiPlusEntity, ButtonEntity):
    """Button sending a command to the unit."""

    entity_description: VmiPlusButtonEntityDescription

    def __init__(
        self, coordinator: VmiPlusCoordinator, description: VmiPlusButtonEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Sends the command."""
        await self.coordinator.async_command(
            self.entity_description.press_fn(self.coordinator.client)
        )
