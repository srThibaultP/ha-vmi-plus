"""Config flow VMI+ : découverte Bluetooth automatique ou saisie manuelle de l'adresse."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, SERVICE_CONTROL_UUID


class VmiPlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flux de configuration pour une centrale VMI+."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ):
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovered[discovery_info.address] = discovery_info.name or discovery_info.address
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            address, name = next(iter(self._discovered.items()))
            return self.async_create_entry(title=name, data={CONF_ADDRESS: address})
        return self.async_show_form(step_id="confirm")

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"VMI+ {address}", data={CONF_ADDRESS: address})

        current = self._async_current_ids()
        for info in async_discovered_service_info(self.hass):
            if info.address in current:
                continue
            if SERVICE_CONTROL_UUID in (info.service_uuids or []):
                self._discovered[info.address] = info.name or info.address

        if self._discovered:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(self._discovered)}),
            )

        # Repli : aucune centrale auto-détectée, saisie manuelle de l'adresse MAC.
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
        )
