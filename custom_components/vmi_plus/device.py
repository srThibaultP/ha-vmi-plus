"""Wrapper BLE pour une centrale VMI+, partagé entre les entités fan/switch."""
from __future__ import annotations

import asyncio
import logging

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import CHAR_CONTROL_UUID
from .protocol import build_frame

_LOGGER = logging.getLogger(__name__)


class VmiPlusDevice:
    """Gère une connexion GATT persistante (reconnexion à la demande) vers la centrale."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        if self._client is not None and self._client.is_connected:
            return self._client

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise RuntimeError(
                f"Centrale VMI+ {self.address} non visible par l'adaptateur Bluetooth de Home Assistant"
            )

        _LOGGER.debug("Connexion à la centrale VMI+ %s", self.address)
        self._client = await establish_connection(
            BleakClientWithServiceCache, ble_device, self.address
        )
        return self._client

    async def write_register(self, register: int, value: int) -> None:
        """Écrit une valeur dans un registre de la centrale (voir PROTOCOL.md)."""
        frame = build_frame(register, value)
        async with self._lock:
            client = await self._ensure_connected()
            await client.write_gatt_char(CHAR_CONTROL_UUID, frame, response=True)

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
