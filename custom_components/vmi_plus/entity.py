"""Classe de base partagée par toutes les entités de l'intégration VMI+.

Centralise le regroupement sous un `Device` Home Assistant (voir la règle
"devices" de l'Integration Quality Scale : sans ça, les entités restent
détachées et ne peuvent pas être assignées à une pièce) ainsi que la
disponibilité, dérivée de l'état de connexion BLE réel.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .device import VmiPlusDevice


class VmiPlusEntity(Entity):
    """Entité de base : device_info commun + disponibilité liée à la connexion BLE."""

    _attr_has_entity_name = True

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        self._device = device
        address = entry.data[CONF_ADDRESS]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Indisponible si la connexion Bluetooth est désactivée ou coupée.

        Les valeurs restent affichées (dernière valeur connue), simplement
        grisées, plutôt que remises à zéro — comportement standard Home
        Assistant pour une perte de connexion temporaire.
        """
        return self._device.enabled and self._device.is_connected
