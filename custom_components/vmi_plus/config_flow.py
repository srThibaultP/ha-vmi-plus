"""Config flow of the VMI+ integration: Bluetooth discovery only."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from vmi_plus_ble import SERVICE_CONTROL_UUID, VmiPlusClient, VmiPlusError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VmiPlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sets up a VMI+ unit found over Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def _async_can_connect(self, info: BluetoothServiceInfoBleak) -> bool:
        """Checks that the unit answers (it is busy while the official app is connected)."""
        client = VmiPlusClient(info.device)
        try:
            await client.update()
        except VmiPlusError:
            _LOGGER.debug("Cannot read %s", info.address, exc_info=True)
            return False
        finally:
            await client.disconnect()
        return True

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handles a unit found by the Bluetooth integration."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirms a discovered unit."""
        assert self._discovery is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if await self._async_can_connect(self._discovery):
                return self._async_create(self._discovery)
            errors["base"] = "cannot_connect"
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery.name},
            errors=errors,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Lets the user pick one of the units in range."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info = self._discovered[user_input[CONF_ADDRESS]]
            await self.async_set_unique_id(info.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if await self._async_can_connect(info):
                return self._async_create(info)
            errors["base"] = "cannot_connect"

        current = self._async_current_ids(include_ignore=False)
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address not in current and SERVICE_CONTROL_UUID in info.service_uuids:
                self._discovered[info.address] = info
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{info.name} ({address})"
                            for address, info in self._discovered.items()
                        }
                    )
                }
            ),
            errors=errors,
        )

    def _async_create(self, info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        return self.async_create_entry(title=info.name, data={CONF_ADDRESS: info.address})
