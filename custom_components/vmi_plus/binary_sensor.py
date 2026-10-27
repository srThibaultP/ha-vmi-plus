"""Binary sensors read from the status frame: heat-exchanger bypass and self-test."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import VmiPlusDevice
from .entity import VmiPlusEntity

PARALLEL_UPDATES = 0

# Status offset 10: one bit per self-test, 0x1f = all OK (Diagnostic screen).
SELF_TEST_ALL_OK = 0x1F


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    device: VmiPlusDevice = entry.runtime_data
    async_add_entities([VmiPlusBypassBinarySensor(device, entry), VmiPlusSelfTestBinarySensor(device, entry)])


class _StatusBinarySensor(VmiPlusEntity, BinarySensorEntity):
    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry, key: str) -> None:
        super().__init__(device, entry)
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{key}"
        self._attr_is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._device.add_update_listener(self._on_update))

    def _on_update(self) -> None:
        data = self._device.telemetry.get("status")
        if data is not None:
            self._update_from_status(data)
        self.async_write_ha_state()

    def _update_from_status(self, data: dict) -> None:
        raise NotImplementedError


class VmiPlusBypassBinarySensor(_StatusBinarySensor):
    """Heat-exchanger bypass state (status offset 25, app key "bypass")."""

    _attr_name = "Bypass échangeur"
    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_icon = "mdi:valve"

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry, "bypass_open")

    def _update_from_status(self, data: dict) -> None:
        self._attr_is_on = data["bypass_open"]
        bypass = self._device.telemetry.get("bypass_state")
        if bypass is not None:
            self._attr_extra_state_attributes = {
                key: bypass[key]
                for key in ("position", "requested_position", "temperature", "forced", "bypass_type")
            }


class VmiPlusSelfTestBinarySensor(_StatusBinarySensor):
    """Problem when any self-test of the Diagnostic screen fails."""

    _attr_name = "Autotest"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: VmiPlusDevice, entry: ConfigEntry) -> None:
        super().__init__(device, entry, "self_test")

    def _update_from_status(self, data: dict) -> None:
        self._attr_is_on = data["self_test"] != SELF_TEST_ALL_OK
        self._attr_extra_state_attributes = {
            "bits": f"{data['self_test']:05b}",
            "details": data["self_test_details"],
        }
