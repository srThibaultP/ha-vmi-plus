"""Switches Boost (0x19), Préchauffage (0x2f), Holiday (0x1a), Mode nuit (0x0b),
Débit fixe (0x1b) et Plages horaires (0x1d) de la centrale VMI+."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    REG_BOOST,
    REG_BYPASS,
    REG_FIXED_FLOW,
    REG_HOLIDAY,
    REG_NIGHT_BOOST_TOGGLE,
    REG_TIME_SLOTS,
    SPEED_OPTIONS,
)
from .protocol import TIME_SLOTS_PER_DAY, build_time_slot_frame
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
            # Register 0x2f is the app's preheat button (heat-wave icon); status
            # offset 53 also drops to 0 when preheating is disabled from the
            # "Simplified configuration" screen, see PROTOCOL.md. Key kept as
            # "bypass" so the unique_id and entity_id don't change.
            VmiPlusSwitch(device, entry, "bypass", "Préchauffage", REG_BYPASS, "bypass"),
            VmiPlusSwitch(device, entry, "holiday", "Holiday", REG_HOLIDAY, "holiday"),
            VmiPlusNightBoostSwitch(device, entry),
            VmiPlusSwitch(device, entry, "fixed_flow", "Débit fixe (radon)", REG_FIXED_FLOW, "fixed_flow"),
            VmiPlusTimeSlotsSwitch(device, entry),
            VmiPlusConnectionSwitch(device, entry),
        ]
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_DAY_SCHEDULE,
        {
            vol.Required("day"): vol.All(vol.Coerce(int), vol.Range(min=1, max=7)),
            vol.Optional("slots", default=[]): vol.All(
                cv.ensure_list,
                vol.Length(max=TIME_SLOTS_PER_DAY),
                [
                    {
                        vol.Required("start"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                        vol.Required("speed"): vol.In(list(SPEED_OPTIONS)),
                        vol.Optional("temp", default=0xFF): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=0xFF)
                        ),
                    }
                ],
            ),
        },
        "async_set_day_schedule",
    )


SERVICE_SET_DAY_SCHEDULE = "set_day_schedule"


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


class VmiPlusTimeSlotsSwitch(VmiPlusSwitch):
    """Plages horaires on/off (register 0x1d), with the weekly schedule as attributes.

    The unit sends its schedule (TimeSlotState frame) whenever the switch is
    written or a day is programmed with the `vmi_plus.set_day_schedule`
    service. Turning it on applies the schedule right away.
    """

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry, "time_slots", "Plages horaires", REG_TIME_SLOTS, "time_slots")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data = self._device.telemetry.get("time_slots")
        if data is None:
            return None
        speeds = {value: option for option, value in SPEED_OPTIONS.items()}
        return {
            f"jour_{index + 1}": [
                {"start": slot["start"], "speed": speeds.get(slot["speed"], slot["speed"]), "temp": slot["temp"]}
                for slot in slots
            ]
            for index, slots in enumerate(data["days"])
        }

    async def async_set_day_schedule(self, day: int, slots: list[dict]) -> None:
        """Programs one day (1 = Monday) with up to 5 slots."""
        frame = build_time_slot_frame(
            day,
            [
                {"start": slot["start"], "speed": SPEED_OPTIONS[slot["speed"]], "temp": slot["temp"]}
                for slot in sorted(slots, key=lambda slot: slot["start"])
            ],
        )
        await self._device.write_frame(frame)


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
