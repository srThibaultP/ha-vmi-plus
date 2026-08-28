"""Switches Boost (0x19), Bypass (0x2f), Holiday (0x1a) et Mode nuit (0x0b) de la centrale VMI+."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import REG_BOOST, REG_BYPASS, REG_HOLIDAY, REG_NIGHT_BOOST_TOGGLE
from .device import VmiPlusDevice
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = entry.runtime_data
    async_add_entities(
        [
            VmiPlusSwitch(device, entry, "boost", "Boost", REG_BOOST, "boost"),
            VmiPlusSwitch(device, entry, "bypass", "Bypass", REG_BYPASS, "bypass"),
            VmiPlusSwitch(device, entry, "holiday", "Holiday", REG_HOLIDAY, "holiday"),
            VmiPlusNightBoostSwitch(device, entry),
            VmiPlusConnectionSwitch(device, entry),
        ]
    )


class VmiPlusSwitch(VmiPlusEntity, SwitchEntity):
    def __init__(
        self,
        device: VmiPlusDevice,
        entry: ConfigEntry,
        key: str,
        name: str,
        register: int,
        telemetry_field: str,
    ) -> None:
        super().__init__(device, entry)
        self._register = register
        self._telemetry_field = telemetry_field
        self._attr_name = name
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{key}"
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))

    def _on_update(self) -> None:
        # État confirmé par lecture réelle (trame statut, voir
        # protocol.py/PROTOCOL.md) : remplace toute valeur optimiste dès que
        # la centrale la republie (poll périodique ou après notre propre
        # écriture), y compris si l'état a changé depuis l'app officielle ou
        # la télécommande physique. Sert aussi de callback de disponibilité
        # (voir device.py) pour une entité par ailleurs write-only.
        data = self._device.telemetry.get("status")
        if data is not None and self._telemetry_field in data:
            self._attr_is_on = data[self._telemetry_field]
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.write_register(self._register, 0x01)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.write_register(self._register, 0x00)
        self._attr_is_on = False
        self.async_write_ha_state()


class VmiPlusNightBoostSwitch(VmiPlusEntity, SwitchEntity):
    """Mode nuit (Night ventilation boost, écran Special modes).

    Contrairement aux autres switches, le registre 0x0b ne prend pas de
    valeur explicite : chaque écriture bascule l'état courant plutôt que de
    l'imposer (voir REG_NIGHT_BOOST_TOGGLE et PROTOCOL.md). Cette entité ne
    déclenche donc une écriture que si le dernier état connu (télémétrie,
    rafraîchie au plus toutes les 10s) diffère de l'état demandé — dans de
    rares cas, un état périmé pourrait faire basculer dans le mauvais sens si
    l'état a changé entretemps ailleurs (app officielle, télécommande
    physique) ; se corrige de lui-même au poll suivant.
    """

    _attr_name = "Mode nuit"
    _attr_icon = "mdi:weather-night"

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_night_boost"
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))

    def _on_update(self) -> None:
        data = self._device.telemetry.get("status")
        if data is not None and "night_boost" in data:
            self._attr_is_on = data["night_boost"]
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        if not self._attr_is_on:
            await self._device.write_register(REG_NIGHT_BOOST_TOGGLE, 0x00)
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._attr_is_on:
            await self._device.write_register(REG_NIGHT_BOOST_TOGGLE, 0x00)
            self._attr_is_on = False
            self.async_write_ha_state()


class VmiPlusConnectionSwitch(VmiPlusEntity, SwitchEntity):
    """Active/désactive la connexion BLE à la centrale.

    La centrale n'accepte qu'une seule connexion GATT à la fois : désactiver ce switch
    déconnecte Home Assistant et libère la centrale (ex. pour repasser la main à l'app
    officielle VMI+ sans avoir à supprimer l'intégration).
    """

    _attr_name = "Connexion Bluetooth"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_is_on = True

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_connection_enabled"

    # `available` hérité de VmiPlusEntity (toujours True) convient déjà : ce
    # switch doit rester actionnable même quand la centrale est injoignable,
    # c'est justement lui qui permet de forcer une nouvelle tentative de
    # connexion.

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_enabled(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_enabled(False)
        self._attr_is_on = False
        self.async_write_ha_state()
