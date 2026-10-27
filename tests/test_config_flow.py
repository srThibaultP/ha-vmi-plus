"""Config flow tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vmi_plus_ble import VmiPlusConnectionError

from custom_components.vmi_plus.const import DOMAIN

from .conftest import ADDRESS, make_service_info

DISCOVERED = "custom_components.vmi_plus.config_flow.async_discovered_service_info"


async def test_bluetooth_discovery(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A discovered unit is set up after confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Urban"
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS
    mock_client.disconnect.assert_awaited()


async def test_bluetooth_discovery_cannot_connect(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """The user can retry when the unit is busy."""
    mock_client.update.side_effect = VmiPlusConnectionError("busy")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """A configured unit is not offered again."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The user picks a unit in range; units of other brands are not listed."""
    other = make_service_info("11:22:33:44:55:66", "Other")
    other.service_uuids = []
    with patch(DISCOVERED, return_value=[make_service_info(), other]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        schema = result["data_schema"].schema[CONF_ADDRESS]
        assert list(schema.container) == [ADDRESS]

        mock_client.update.side_effect = VmiPlusConnectionError("busy")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
        assert result["errors"] == {"base": "cannot_connect"}

        mock_client.update.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Nothing to offer: the flow stops."""
    with patch(DISCOVERED, return_value=[]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """A unit set up meanwhile (e.g. by discovery) aborts the flow."""
    with patch(DISCOVERED, return_value=[make_service_info()]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        mock_entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: ADDRESS}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
