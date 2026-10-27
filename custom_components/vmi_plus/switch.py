"""Switches of the VMI+ unit: boost, preheat, holiday, night boost, fixed flow, time slots."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from vmi_plus_ble import Status, TimeSlot, VmiPlusClient

from .const import ATTR_SPEED, ATTR_START, ATTR_TEMPERATURE
from .coordinator import VmiPlusConfigEntry, VmiPlusCoordinator
from .entity import VmiPlusEntity
from .select import SPEEDS

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VmiPlusSwitchEntityDescription(SwitchEntityDescription):
    """Switch read from the status frame and written with one client call."""

    is_on_fn: Callable[[Status], bool]
    set_fn: Callable[[VmiPlusClient, bool], Coroutine[Any, Any, object]]


SWITCHES: tuple[VmiPlusSwitchEntityDescription, ...] = (
    VmiPlusSwitchEntityDescription(
        key="boost",
        translation_key="boost",
        is_on_fn=lambda status: status.boost,
        set_fn=lambda client, on: client.set_boost(on),
    ),
    VmiPlusSwitchEntityDescription(
        key="preheat",
        translation_key="preheat",
        is_on_fn=lambda status: status.preheat,
        set_fn=lambda client, on: client.set_preheat(on),
    ),
    VmiPlusSwitchEntityDescription(
        key="holiday",
        translation_key="holiday",
        is_on_fn=lambda status: status.holiday,
        set_fn=lambda client, on: client.set_holiday(on),
    ),
    VmiPlusSwitchEntityDescription(
        key="night_boost",
        translation_key="night_boost",
        is_on_fn=lambda status: status.night_boost,
        set_fn=lambda client, on: client.set_night_boost(on),
    ),
    VmiPlusSwitchEntityDescription(
        key="fixed_flow",
        translation_key="fixed_flow",
        is_on_fn=lambda status: status.fixed_flow,
        set_fn=lambda client, on: client.set_fixed_flow(on),
    ),
    VmiPlusSwitchEntityDescription(
        key="time_slots",
        translation_key="time_slots",
        is_on_fn=lambda status: status.time_slots,
        set_fn=lambda client, on: client.set_time_slots(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VmiPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Adds the switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        VmiPlusTimeSlotsSwitch(coordinator, description)
        if description.key == "time_slots"
        else VmiPlusSwitch(coordinator, description)
        for description in SWITCHES
    )


class VmiPlusSwitch(VmiPlusEntity, SwitchEntity):
    """Switch backed by the status frame."""

    entity_description: VmiPlusSwitchEntityDescription

    def __init__(
        self, coordinator: VmiPlusCoordinator, description: VmiPlusSwitchEntityDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Unavailable until the status has been read."""
        return super().available and self.coordinator.data.status is not None

    @property
    def is_on(self) -> bool | None:
        """State read from the unit."""
        status = self.coordinator.data.status
        return self.entity_description.is_on_fn(status) if status else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turns the function on."""
        await self.coordinator.async_command(
            self.entity_description.set_fn(self.coordinator.client, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turns the function off."""
        await self.coordinator.async_command(
            self.entity_description.set_fn(self.coordinator.client, False)
        )


class VmiPlusTimeSlotsSwitch(VmiPlusSwitch):
    """Weekly programme on/off; target of the set_day_schedule action.

    Turning it on applies the programme at once.
    """

    async def async_set_day_schedule(self, day: int, slots: list[dict[str, Any]]) -> None:
        """Programs one day (1 = Monday) with up to 5 slots."""
        await self.coordinator.async_command(
            self.coordinator.client.set_day_schedule(
                day,
                [
                    TimeSlot(slot[ATTR_START], SPEEDS[slot[ATTR_SPEED]], slot[ATTR_TEMPERATURE])
                    for slot in slots
                ],
            )
        )
