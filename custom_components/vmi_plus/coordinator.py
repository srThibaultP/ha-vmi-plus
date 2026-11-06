"""Coordinator reading the VMI+ unit over Bluetooth."""

from __future__ import annotations

import logging
from collections.abc import Awaitable

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from vmi_plus_ble import VmiPlusClient, VmiPlusError, VmiPlusState

from .const import BYPASS_EVERY, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type VmiPlusConfigEntry = ConfigEntry[VmiPlusCoordinator]


class VmiPlusCoordinator(DataUpdateCoordinator[VmiPlusState]):
    """Polls the unit and sends commands to it."""

    config_entry: VmiPlusConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: VmiPlusConfigEntry, client: VmiPlusClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.address}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self._polls = 0

    async def _async_update_data(self) -> VmiPlusState:
        bypass = self._polls % BYPASS_EVERY == 0
        self._polls += 1
        try:
            return await self.client.update(bypass=bypass)
        except VmiPlusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    @callback
    def async_update_ble_device(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        """Keeps the client on the adapter or proxy that currently sees the unit."""
        self.client.set_ble_device(service_info.device)

    async def async_command(self, command: Awaitable[object]) -> None:
        """Runs a client command, then reads the new state."""
        try:
            await command
        except VmiPlusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        """Frees the unit (it accepts a single connection) on unload."""
        await super().async_shutdown()
        await self.client.disconnect()
