"""Fixtures of the VMI+ tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vmi_plus_ble import SERVICE_CONTROL_UUID, VmiPlusState, parse_frame

from custom_components.vmi_plus.const import DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"

# Frames read from a real unit (serial number and sensor id replaced).
STATUS = bytes.fromhex(
    "a5b601063778563412001fffffffff00012832026411c80001003c04000000"
    "0009000112140518b11d160b00000000c20102010200013400100b0000c7"
)
SENSORS = bytes.fromhex(
    "a5b602067aefbeadde030314004c00ff000000000000000000ff000000000000000000"
    "ff000000000000000000ff000000000000000000ff000000000000000000ff00000000"
    "0000000000ff000000000000000000ff000000000000000000ff000000000000000000"
    "ff0000000000000000000000000000000000000000009d"
)
PROBES = bytes([0xA5, 0xB6, 0x03, 0x06, 0x05, 0x01, 28, 0, 56, 0])
BYPASS = bytes.fromhex("a5b61806126400001c1000ff00000000000000000000649b")


def make_state() -> VmiPlusState:
    """State as read from the real unit."""
    state = VmiPlusState()
    for frame in (STATUS, SENSORS, PROBES, BYPASS):
        decoded = parse_frame(frame)
        assert decoded is not None
        state.update(decoded)
    return state


def make_service_info(address: str = ADDRESS, name: str = "Urban") -> BluetoothServiceInfoBleak:
    """Advertisement of a unit."""
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[SERVICE_CONTROL_UUID],
        source="local",
        device=BLEDevice(address, name, None),
        advertisement=None,
        connectable=True,
        time=0,
        tx_power=None,
    )


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations: None, enable_bluetooth: None) -> None:
    """Loads custom integrations with a mocked Bluetooth stack."""


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """VmiPlusClient answering like the real unit."""
    client = MagicMock()
    client.address = ADDRESS
    client.is_connected = True
    client.state = make_state()
    client.update = AsyncMock(return_value=client.state)
    for method in (
        "disconnect",
        "set_speed",
        "set_boost",
        "set_preheat",
        "set_holiday",
        "set_night_boost",
        "set_fixed_flow",
        "set_time_slots",
        "set_day_schedule",
        "set_summer_limit",
        "set_preheat_target",
        "locate",
        "declare_new_filter",
    ):
        setattr(client, method, AsyncMock())
    with (
        patch("custom_components.vmi_plus.VmiPlusClient", return_value=client),
        patch("custom_components.vmi_plus.config_flow.VmiPlusClient", return_value=client),
    ):
        yield client


@pytest.fixture
def mock_ble_device() -> Generator[MagicMock]:
    """The unit is in range."""
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=BLEDevice(ADDRESS, "Urban", None),
    ) as mock:
        yield mock


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Config entry of the unit."""
    return MockConfigEntry(
        domain=DOMAIN, title="VisionAir", unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_device: MagicMock,
) -> MockConfigEntry:
    """Sets up the integration with every entity enabled."""
    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new=True,
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
    return mock_entry


def call_args(mock: AsyncMock) -> list[tuple[Any, ...]]:
    """Positional arguments of each call."""
    return [call.args for call in mock.call_args_list]
