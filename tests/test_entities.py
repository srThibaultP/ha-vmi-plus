"""Entity states and commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from vmi_plus_ble import Speed, TimeSlot, VmiPlusConnectionError, VmiPlusState

from custom_components.vmi_plus.const import DOMAIN, SERVICE_SET_DAY_SCHEDULE

from .conftest import call_args


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("entity_id", "state"),
    [
        ("select.urban_speed", "medium"),
        ("switch.urban_boost", "off"),
        ("switch.urban_preheat", "on"),
        ("switch.urban_holiday_mode", "off"),
        ("switch.urban_night_boost", "on"),
        ("switch.urban_fixed_air_flow_radon", "off"),
        ("switch.urban_time_slots", "off"),
        ("number.urban_summer_supply_air_limit", "24"),
        ("number.urban_preheat_target", "18"),
        ("sensor.urban_room_temperature", "20"),
        ("sensor.urban_room_humidity", "76"),
        ("sensor.urban_internal_probe_temperature", "28"),
        ("sensor.urban_internal_probe_humidity", "56"),
        ("sensor.urban_filter_life", "0"),
        ("sensor.urban_theoretical_air_flow", "90.0"),
        ("sensor.urban_season", "intermediate"),
        ("sensor.urban_operating_days", "1084"),
        ("sensor.urban_software_version", "6.4.002"),
        ("sensor.urban_volume_to_ventilate", "200"),
        ("sensor.urban_surface", "80"),
        ("sensor.urban_preheat_type", "electric"),
        ("sensor.urban_bypass_position", "100"),
        ("sensor.urban_bypass_temperature", "28"),
        ("sensor.urban_paired_sensors", "1"),
        ("binary_sensor.urban_heat_exchanger_bypass", "off"),
        ("binary_sensor.urban_self_test", "off"),
        ("binary_sensor.urban_turbo_heat", "off"),
        ("binary_sensor.urban_building_management", "off"),
        ("binary_sensor.urban_action_in_progress", "off"),
        ("button.urban_locate", STATE_UNKNOWN),
        ("button.urban_new_filter_6_months", STATE_UNKNOWN),
        ("button.urban_new_filter_12_months", STATE_UNKNOWN),
    ],
)
async def test_states(hass: HomeAssistant, entity_id: str, state: str) -> None:
    """Every entity reflects the frames read from the unit."""
    assert (current := hass.states.get(entity_id)) is not None
    assert current.state == state


async def test_unique_ids_unchanged(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_integration: MockConfigEntry
) -> None:
    """Unique IDs stay those of earlier versions so entity IDs do not change."""
    unique_ids = {
        entry.unique_id.removeprefix("AA:BB:CC:DD:EE:FF_")
        for entry in er.async_entries_for_config_entry(entity_registry, setup_integration.entry_id)
    }
    assert {
        "speed",
        "preheat",
        "night_boost",
        "summer_limit",
        "remote_temperature",
        "probe_humidity",
        "status_filter_days",
        "bypass_state_position",
        "sensors",
        "bypass_open",
        "self_test",
        "locate",
        "new_filter_12",
    } <= unique_ids
    assert len(unique_ids) == 32


DISABLED_BY_DEFAULT = [
    "sensor.urban_software_version",
    "sensor.urban_volume_to_ventilate",
    "sensor.urban_surface",
    "sensor.urban_preheat_type",
    "sensor.urban_bypass_position",
    "sensor.urban_bypass_temperature",
    "sensor.urban_paired_sensors",
    "binary_sensor.urban_self_test",
    "binary_sensor.urban_turbo_heat",
    "binary_sensor.urban_building_management",
    "binary_sensor.urban_action_in_progress",
    "switch.urban_fixed_air_flow_radon",
    "switch.urban_time_slots",
    "button.urban_locate",
]


async def test_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Diagnostics (except operating days) and niche controls start disabled."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    disabled = {
        entry.entity_id
        for entry in er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id)
        if entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    }
    assert disabled == set(DISABLED_BY_DEFAULT)
    assert hass.states.get("sensor.urban_operating_days") is not None
    assert hass.states.get("sensor.urban_room_temperature") is not None


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("domain", "service", "entity_id", "data", "method", "args"),
    [
        ("select", SERVICE_SELECT_OPTION, "select.urban_speed", {ATTR_OPTION: "high"},
         "set_speed", (Speed.HIGH,)),
        ("switch", SERVICE_TURN_ON, "switch.urban_boost", {}, "set_boost", (True,)),
        ("switch", SERVICE_TURN_OFF, "switch.urban_preheat", {}, "set_preheat", (False,)),
        ("switch", SERVICE_TURN_ON, "switch.urban_holiday_mode", {}, "set_holiday", (True,)),
        ("switch", SERVICE_TURN_OFF, "switch.urban_night_boost", {}, "set_night_boost", (False,)),
        ("switch", SERVICE_TURN_ON, "switch.urban_fixed_air_flow_radon", {},
         "set_fixed_flow", (True,)),
        ("switch", SERVICE_TURN_ON, "switch.urban_time_slots", {}, "set_time_slots", (True,)),
        ("number", SERVICE_SET_VALUE, "number.urban_summer_supply_air_limit", {ATTR_VALUE: 26},
         "set_summer_limit", (26,)),
        ("number", SERVICE_SET_VALUE, "number.urban_preheat_target", {ATTR_VALUE: 16},
         "set_preheat_target", (16,)),
        ("button", SERVICE_PRESS, "button.urban_locate", {}, "locate", ()),
        ("button", SERVICE_PRESS, "button.urban_new_filter_6_months", {},
         "declare_new_filter", (6,)),
        ("button", SERVICE_PRESS, "button.urban_new_filter_12_months", {},
         "declare_new_filter", (12,)),
    ],
)  # fmt: skip
async def test_commands(
    hass: HomeAssistant,
    mock_client: MagicMock,
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, object],
    method: str,
    args: tuple[object, ...],
) -> None:
    """Each entity sends its command, then the state is read again."""
    reads = mock_client.update.await_count
    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )
    assert call_args(getattr(mock_client, method)) == [args]
    await hass.async_block_till_done()
    assert mock_client.update.await_count > reads


async def test_air_quality_sensor_added_when_paired(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """The VOC entities appear only for a unit with an air-quality sensor paired."""
    from .conftest import SENSORS_WITH_COV, make_state

    mock_client.state = make_state(SENSORS_WITH_COV)
    mock_client.update = AsyncMock(return_value=mock_client.state)
    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default", new=True
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("sensor.urban_air_quality_voc").state == "56"
    assert hass.states.get("sensor.urban_air_quality_humidity").state == "61"
    assert hass.states.get("sensor.urban_air_quality_temperature").state == "20"


@pytest.mark.usefixtures("setup_integration")
async def test_command_error(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """A failed write is reported to the user."""
    mock_client.set_boost.side_effect = VmiPlusConnectionError("gone")
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.urban_boost"}, blocking=True
        )
    assert err.value.translation_key == "command_failed"


@pytest.mark.usefixtures("setup_integration")
async def test_set_day_schedule(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """The action programs one day."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DAY_SCHEDULE,
        {
            ATTR_ENTITY_ID: "switch.urban_time_slots",
            "day": 1,
            "slots": [
                {"start": 7, "speed": "medium", "temperature": 16},
                {"start": 22, "speed": "low"},
            ],
        },
        blocking=True,
    )
    assert call_args(mock_client.set_day_schedule) == [
        (1, [TimeSlot(7, Speed.MEDIUM, 16), TimeSlot(22, Speed.LOW, 0xFF)])
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_set_day_schedule_rejects_bad_speed(hass: HomeAssistant) -> None:
    """Invalid slots are refused before anything is sent."""
    with pytest.raises(Exception, match="speed"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DAY_SCHEDULE,
            {
                ATTR_ENTITY_ID: "switch.urban_time_slots",
                "day": 1,
                "slots": [{"start": 7, "speed": "max"}],
            },
            blocking=True,
        )


async def test_unknown_values(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Frames not read yet, preheat off and an unknown speed give unknown states.

    Without a status frame the device falls back to the advertised name.
    """
    state = VmiPlusState()
    mock_client.update = AsyncMock(return_value=state)
    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new=True,
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
    for entity_id in (
        "select.visionair_speed",
        "number.visionair_preheat_target",
        "sensor.visionair_room_temperature",
        "sensor.visionair_internal_probe_temperature",
        "sensor.visionair_filter_life",
        "sensor.visionair_bypass_position",
        "sensor.visionair_paired_sensors",
        "binary_sensor.visionair_self_test",
    ):
        assert hass.states.get(entity_id).state == STATE_UNKNOWN, entity_id
    assert hass.states.get("switch.visionair_boost").state == "unavailable"
