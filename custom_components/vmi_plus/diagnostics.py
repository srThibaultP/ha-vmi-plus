"""Diagnostics of the VMI+ integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .coordinator import VmiPlusConfigEntry

TO_REDACT = {CONF_ADDRESS, "serial", "id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VmiPlusConfigEntry
) -> dict[str, Any]:
    """Returns the config entry and the last decoded frames."""
    coordinator = entry.runtime_data
    state = coordinator.data
    frames = {
        name: asdict(value) if (value := getattr(state, name)) is not None else None
        for name in ("status", "probes", "sensors", "time_slots", "bypass", "gtc")
    }
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "connected": coordinator.client.is_connected,
        "frames": async_redact_data(frames, TO_REDACT),
    }
