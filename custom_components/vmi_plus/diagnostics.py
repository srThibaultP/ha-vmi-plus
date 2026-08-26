"""Diagnostics pour l'intégration VMI+ (règle "diagnostics" de l'Integration
Quality Scale) — utile pour joindre un état complet à un rapport de bug sans
avoir à fouiller les logs Home Assistant."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .device import VmiPlusDevice

TO_REDACT = {CONF_ADDRESS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    device: VmiPlusDevice = entry.runtime_data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "enabled": device.enabled,
        "connected": device.is_connected,
        # Dernières valeurs de télémétrie reçues (température/humidité/mode nuit) —
        # aucune donnée personnelle, pas besoin de rédaction.
        "telemetry": device.telemetry,
    }
