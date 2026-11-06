"""The VMI+ (Ventilairsec) integration."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from vmi_plus_ble import VmiPlusClient

from .const import DOMAIN
from .coordinator import VmiPlusConfigEntry, VmiPlusCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Registers the integration's actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VmiPlusConfigEntry) -> bool:
    """Sets up a unit from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"address": address},
        )

    coordinator = VmiPlusCoordinator(hass, entry, VmiPlusClient(ble_device))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            coordinator.async_update_ble_device,
            bluetooth.BluetoothCallbackMatcher(address=address, connectable=True),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    # Earlier versions had a "Bluetooth connection" switch; disabling the
    # config entry now frees the unit for the official app.
    registry = er.async_get(hass)
    if old := registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{address}_connection_enabled"
    ):
        registry.async_remove(old)
    # Before v0.8.0 the preheat switch was keyed "bypass"; the entity ID is kept.
    if preheat := registry.async_get_entity_id(Platform.SWITCH, DOMAIN, f"{address}_bypass"):
        registry.async_update_entity(preheat, new_unique_id=f"{address}_preheat")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VmiPlusConfigEntry) -> bool:
    """Unloads a config entry and frees the unit."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
