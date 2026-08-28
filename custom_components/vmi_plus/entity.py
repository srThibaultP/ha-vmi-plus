"""Classe de base partagée par toutes les entités de l'intégration VMI+.

Centralise le regroupement sous un `Device` Home Assistant (voir la règle
"devices" de l'Integration Quality Scale : sans ça, les entités restent
détachées et ne peuvent pas être assignées à une pièce).
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .device import VmiPlusDevice


class VmiPlusEntity(Entity):
    """Entité de base : device_info commun, toujours "disponible"."""

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
        """Toujours disponible, y compris en cas de perte de connexion BLE.

        Avant, `available` reflétait `device.is_connected` : dès qu'une
        reconnexion était en cours (transitoire, ex. l'app officielle prend la
        main quelques secondes), Home Assistant passait toutes les entités à
        l'état "unavailable" — les sensors perdaient leur dernière valeur
        connue (au lieu d'être juste "figée"/grisée comme espéré) et le select
        Vitesse retombait carrément à "unknown", car son état n'est pas
        persisté par HA quand l'entité est indisponible. En restant toujours
        disponibles, les entités gardent leur dernière valeur/option connue
        jusqu'à la prochaine mise à jour réussie ; une tentative d'écriture
        (select/switch) pendant une coupure déclenche simplement une
        reconnexion à la demande (voir `_ensure_connected` dans device.py),
        avec le même risque d'échec qu'avant.
        """
        return True
