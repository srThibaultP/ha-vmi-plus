"""Intégration VMI+ (Ventilairsec) — pilotage BLE des centrales VMCI."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .device import VmiPlusDevice

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    device = VmiPlusDevice(hass, entry.data[CONF_ADDRESS])
    try:
        await device.async_verify_connection()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Centrale VMI+ {entry.data[CONF_ADDRESS]} injoignable en Bluetooth"
        ) from err

    entry.runtime_data = device
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def _update_device_info() -> None:
        # Model, serial number and versions come from the status frame (same
        # values as the app's "Equipment life" screen).
        status = device.telemetry.get("status")
        if status is None:
            return
        registry = dr.async_get(hass)
        device_entry = next(
            (
                candidate
                for candidate in dr.async_entries_for_config_entry(registry, entry.entry_id)
                if (DOMAIN, entry.data[CONF_ADDRESS]) in candidate.identifiers
            ),
            None,
        )
        if device_entry is None:
            return
        info = {
            "model": status["box"] or device_entry.model,
            "serial_number": status["serial"],
            "sw_version": status["software_version"],
            "hw_version": f"{status['electronic_version']}.{status['mechanical_version']}",
        }
        if any(getattr(device_entry, key) != value for key, value in info.items()):
            registry.async_update_device(device_entry.id, **info)

    entry.async_on_unload(device.add_update_listener(_update_device_info))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        device: VmiPlusDevice = entry.runtime_data
        await device.async_shutdown()
    return unload_ok
