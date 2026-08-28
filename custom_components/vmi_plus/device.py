"""Wrapper BLE pour une centrale VMI+, partagé entre les entités select/switch/sensor."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import (
    CHAR_CONTROL_UUID,
    CHAR_TELEMETRY_UUID,
    POLL_INTERVAL_SECONDS,
    POLL_REG_PROBE,
    POLL_REG_REMOTE,
    POLL_REG_STATUS,
)
from .protocol import build_frame, parse_notification

_LOGGER = logging.getLogger(__name__)


class VmiPlusDevice:
    """Gère une connexion GATT persistante (reconnexion à la demande) vers la centrale,
    l'écoute des notifications de télémétrie, et le polling périodique qui les déclenche."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self.enabled = True
        # Dernières valeurs connues par sonde ("probe" = sonde interne, "remote" =
        # sonde télécommande/pièce), mises à jour au fil des notifications reçues.
        self.telemetry: dict[str, dict] = {}
        self._client: BleakClientWithServiceCache | None = None
        self._lock = asyncio.Lock()
        self._update_callbacks: list[Callable[[], None]] = []
        self._poll_task: asyncio.Task | None = None
        self._notifying = False
        self._was_available = True

    def add_update_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Enregistre un callback appelé à chaque nouvelle donnée de télémétrie.
        Retourne une fonction pour se désinscrire."""
        self._update_callbacks.append(callback)
        return lambda: self._update_callbacks.remove(callback)

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def async_verify_connection(self, timeout: float = 15) -> None:
        """Tente une connexion BLE réelle et lève une exception explicite en cas
        d'échec — utilisé par le config flow (test-before-configure) et par la
        configuration initiale de l'intégration (test-before-setup).

        `establish_connection` retente en interne sans limite de temps propre ;
        sans ce timeout explicite, `async_setup_entry` peut rester bloqué en
        "Initializing" indéfiniment si la centrale est injoignable au démarrage
        (ex. déjà connectée à l'app officielle), au lieu d'échouer proprement et
        de laisser Home Assistant gérer les nouvelles tentatives."""
        async with asyncio.timeout(timeout):
            await self._ensure_connected()

    async def set_enabled(self, enabled: bool) -> None:
        """Active/désactive la connexion BLE. Utile pour libérer la centrale (une seule
        connexion GATT possible à la fois) au profit de l'app officielle par exemple."""
        self.enabled = enabled
        if not enabled:
            await self.disconnect()

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        if not self.enabled:
            raise RuntimeError(
                "Connexion Bluetooth désactivée pour cette centrale VMI+ "
                "(voir l'entité switch dédiée)"
            )

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
        self._notifying = False
        return self._client

    async def write_register(self, register: int, value: int) -> None:
        """Écrit une valeur dans un registre de la centrale (voir PROTOCOL.md)."""
        frame = build_frame(register, value)
        async with self._lock:
            client = await self._ensure_connected()
            await client.write_gatt_char(CHAR_CONTROL_UUID, frame, response=True)

    def _notify_listeners(self) -> None:
        for callback in list(self._update_callbacks):
            callback()

    def _handle_notification(self, _char, data: bytearray) -> None:
        parsed = parse_notification(bytes(data))
        if parsed is None:
            return
        self.telemetry[parsed["type"]] = parsed
        self._notify_listeners()

    async def _poll_once(self) -> None:
        """Déclenche les trois notifications de télémétrie (voir PROTOCOL.md)."""
        async with self._lock:
            client = await self._ensure_connected()
            if not self._notifying:
                await client.start_notify(CHAR_TELEMETRY_UUID, self._handle_notification)
                self._notifying = True
            for register in (POLL_REG_STATUS, POLL_REG_PROBE, POLL_REG_REMOTE):
                frame = build_frame(register, 0x00)
                await client.write_gatt_char(CHAR_CONTROL_UUID, frame, response=True)

    async def _poll_loop(self) -> None:
        while True:
            try:
                if self.enabled:
                    await self._poll_once()
                if self.is_connected and not self._was_available:
                    _LOGGER.info("Centrale VMI+ %s de nouveau joignable", self.address)
                    self._was_available = True
            except Exception:  # noqa: BLE001 - ne doit jamais tuer la tâche de fond
                _LOGGER.debug("Échec du polling télémétrie VMI+ %s", self.address, exc_info=True)
                if self._was_available:
                    _LOGGER.warning(
                        "Centrale VMI+ %s injoignable, nouvelle tentative en arrière-plan",
                        self.address,
                    )
                    self._was_available = False
            # Notifie même sans nouvelle télémétrie (donc même en cas d'échec) :
            # inoffensif (ré-écrit le même état), mais laisse un point d'ancrage
            # si une entité a un jour besoin de réagir à un cycle de poll raté.
            self._notify_listeners()
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    def start_polling(self) -> None:
        """Démarre la tâche de fond qui interroge périodiquement la télémétrie."""
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = self.hass.loop.create_task(self._poll_loop())

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
        self._notifying = False

    async def async_shutdown(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None
        await self.disconnect()
