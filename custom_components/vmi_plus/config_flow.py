"""Config flow VMI+ : découverte Bluetooth automatique ou saisie manuelle de l'adresse."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, SERVICE_CONTROL_UUID
from .device import VmiPlusDevice

_LOGGER = logging.getLogger(__name__)


class VmiPlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flux de configuration pour une centrale VMI+."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}

    async def _async_test_connection(self, address: str) -> bool:
        """Vérifie que la centrale est bien joignable avant de créer l'entrée
        (règle "test-before-configure") — évite de créer une config entry qui
        échouerait immédiatement au démarrage pour une adresse invalide."""
        device = VmiPlusDevice(self.hass, address)
        try:
            await device.async_verify_connection()
        except Exception:  # noqa: BLE001 - toute erreur = adresse/centrale injoignable
            _LOGGER.debug("Test de connexion échoué pour %s", address, exc_info=True)
            return False
        finally:
            await device.disconnect()
        return True

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
            if not await self._async_test_connection(address):
                return self.async_abort(reason="cannot_connect")
            return self.async_create_entry(title=name, data={CONF_ADDRESS: address})
        return self.async_show_form(step_id="confirm")

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if await self._async_test_connection(address):
                return self.async_create_entry(
                    title=f"VMI+ {address}", data={CONF_ADDRESS: address}
                )
            errors["base"] = "cannot_connect"

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
                errors=errors,
            )

        # Repli : aucune centrale auto-détectée, saisie manuelle de l'adresse MAC.
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )
