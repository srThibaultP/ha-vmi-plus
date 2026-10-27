"""Base entity of the VMI+ integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import VmiPlusCoordinator


class VmiPlusEntity(CoordinatorEntity[VmiPlusCoordinator]):
    """Entity of the single device created for a unit."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VmiPlusCoordinator, key: str) -> None:
        super().__init__(coordinator)
        address = coordinator.client.address
        # Unique IDs are "<address>_<key>", kept identical to earlier versions.
        self._attr_unique_id = f"{address}_{key}"
        status = coordinator.data.status
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(CONNECTION_BLUETOOTH, address)},
            name=coordinator.config_entry.title,
            manufacturer=MANUFACTURER,
            model=status.box if status else None,
            serial_number=status.serial if status else None,
            sw_version=status.software_version if status else None,
            hw_version=(
                f"{status.electronic_version}.{status.mechanical_version}" if status else None
            ),
        )
