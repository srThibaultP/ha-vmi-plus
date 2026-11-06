"""Setup, unload, availability and diagnostics."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from vmi_plus_ble import VmiPlusConnectionError

from custom_components.vmi_plus.const import DOMAIN

from .conftest import ADDRESS, make_service_info


async def test_setup_and_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """The unit is freed when the entry is unloaded."""
    assert setup_integration.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    mock_client.disconnect.assert_awaited()


async def test_device_not_in_range(hass: HomeAssistant, mock_entry: MockConfigEntry) -> None:
    """Setup is retried while no adapter sees the unit."""
    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address", return_value=None
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_first_read_fails(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Setup is retried while the unit is busy."""
    mock_client.update.side_effect = VmiPlusConnectionError("busy")
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unavailable_then_back(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities follow the connection to the unit."""
    assert hass.states.get("sensor.urban_room_temperature").state == "20"

    mock_client.update.side_effect = VmiPlusConnectionError("busy")
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.urban_room_temperature").state == STATE_UNAVAILABLE

    mock_client.update.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.urban_room_temperature").state == "20"
    # The bypass state is read on the first poll, then once a minute.
    assert [call.kwargs["bypass"] for call in mock_client.update.call_args_list] == [
        True,
        False,
        False,
    ]


async def test_migration_from_earlier_versions(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Entities of earlier versions are cleaned up or migrated."""
    mock_entry.add_to_hass(hass)
    old = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{ADDRESS}_connection_enabled", config_entry=mock_entry
    )
    preheat = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{ADDRESS}_bypass",
        config_entry=mock_entry,
        suggested_object_id="urban_bypass",
    )
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    assert entity_registry.async_get(old.entity_id) is None
    migrated = entity_registry.async_get(preheat.entity_id)
    assert migrated is not None
    assert migrated.unique_id == f"{ADDRESS}_preheat"


async def test_ble_device_follows_adapter(
    hass: HomeAssistant, setup_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A new advertisement updates the device used for the next connection."""
    info = make_service_info()
    setup_integration.runtime_data.async_update_ble_device(info, BluetoothChange.ADVERTISEMENT)
    mock_client.set_ble_device.assert_called_once_with(info.device)


async def test_device_info(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Name, model, serial number and versions come from the status frame."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, ADDRESS), setup_integration.entry_id
    )
    assert device is not None
    assert device.name == "Urban"
    assert (device.manufacturer, device.model, device.serial_number) == (
        "Ventilairsec",
        "Urban",
        "12345678",
    )
    assert (device.sw_version, device.hw_version) == ("6.4.002", "1.1")


async def test_diagnostics(
    hass: HomeAssistant, hass_client: object, setup_integration: MockConfigEntry
) -> None:
    """Identifiers are redacted."""
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, setup_integration)
    assert diagnostics["entry_data"] == {"address": "**REDACTED**"}
    assert diagnostics["connected"] is True
    assert diagnostics["frames"]["status"]["serial"] == "**REDACTED**"
    assert diagnostics["frames"]["sensors"]["sensors"][0]["id"] == "**REDACTED**"
    assert diagnostics["frames"]["status"]["operating_days"] == 1084
    assert diagnostics["frames"]["gtc"] is None
