"""Binary sensor pour le statut (lu, pas écrit) du mode nuit de la centrale VMI+.

Alimenté par le même canal de télémétrie que sensor.py (notification déclenchée
par le polling périodique du registre 0x03) — voir protocol.py et PROTOCOL.md.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import VmiPlusDevice
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = entry.runtime_data
    async_add_entities([VmiPlusNightBoostSensor(device, entry)])


class VmiPlusNightBoostSensor(VmiPlusEntity, BinarySensorEntity):
    """Reflète l'état réel (lu sur l'appareil) du mode "Night ventilation boost".

    Contrairement à select.vitesse / switch.boost / switch.bypass, cette entité
    est en lecture seule : la commande d'écriture pour ce mode n'a pas encore
    été identifiée avec certitude (voir "Ce qui reste à faire" dans PROTOCOL.md).
    Pour changer ce mode, utiliser l'app VMI+ officielle (Configuration →
    Special modes) — cette entité se mettra à jour au poll suivant (10s).
    """

    _attr_name = "Mode nuit"
    _attr_icon = "mdi:weather-night"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_night_boost"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))
        self._on_update()

    def _on_update(self) -> None:
        data = self._device.telemetry.get("status")
        if data is not None and "night_boost" in data:
            self._attr_is_on = data["night_boost"]
            self.async_write_ha_state()
