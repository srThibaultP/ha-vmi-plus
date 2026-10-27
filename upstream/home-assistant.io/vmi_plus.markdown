---
title: VMI+ (Ventilairsec)
description: Instructions on how to integrate Ventilairsec VMI+ ventilation units into Home Assistant.
ha_category:
  - Binary sensor
  - Button
  - Number
  - Select
  - Sensor
  - Switch
ha_release: "2026.12"
ha_iot_class: Local Polling
ha_config_flow: true
ha_codeowners:
  - '@srThibaultP'
ha_domain: vmi_plus
ha_bluetooth: true
ha_platforms:
  - binary_sensor
  - button
  - diagnostics
  - number
  - select
  - sensor
  - switch
ha_integration_type: device
ha_quality_scale: bronze
---

The **VMI+ (Ventilairsec)** {% term integration %} controls Ventilairsec **VMI+ / VMCI** positive
input ventilation units over Bluetooth, locally, without the vendor's cloud. It offers what the
official VMI+ app offers a private customer: speed, boost, preheating, special modes, weekly
programme, temperature settings, probes and maintenance information.

## Supported devices

- Ventilairsec **Urban** (tested).
- Other VMI+ units driven by the VMI+ app (Purevent, PRO, Cube) use the same protocol and should
  work, but have not been tested.

Units driven by the extract-ventilation (VMC) products of the brand are not supported.

## Prerequisites

- A Bluetooth adapter or an [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)
  in range of the unit (the unit is usually in the attic: a proxy close to it works best).
- The official VMI+ app must not be connected: the unit accepts **one connection at a time**.

{% include integrations/config_flow.md %}

The unit is discovered automatically. Otherwise, add the integration and pick the unit in the list.

{% configuration_basic %}
Unit:
  description: The VMI+ unit to set up, among the units in range of your Bluetooth adapters and proxies.
{% endconfiguration_basic %}

## Supported functionality

### Controls

- **Speed** (select): low, medium or high. The unit always ventilates and cannot be turned off.
- **Boost** (switch): 30 minutes at maximum speed.
- **Preheat** (switch): the preheat button of the app's home screen.
- **Holiday mode**, **Night boost**, **Fixed air flow (radon)** (switches): the app's special modes.
- **Time slots** (switch): turns the weekly programme on or off. Turning it on applies the programme at once.
- **Preheat target** (number, 12–18 °C) and **Summer supply air limit** (number, 22–35 °C).
- **Locate** (button): blinks the unit's LED.
- **New filter (6 months)** / **New filter (12 months)** (buttons): declare a filter change. They restart the filter counter, so only press them after fitting a new filter.

### Sensors

- Room temperature and humidity (from the remote control), internal probe temperature and humidity.
- Filter life (days left), theoretical air flow, season.
- Heat exchanger bypass (open or closed) and its position.
- Diagnostics: self-test result, operating days, software version, paired sensors, volume to
  ventilate, surface, preheat type, turbo heat, building management, bypass temperature, action in progress. Some are disabled by default.

### Actions

#### Action `vmi_plus.set_day_schedule`

Programs one day of the weekly programme. Target the **Time slots** switch of the unit.

| Data attribute | Optional | Description |
| -------------- | -------- | ----------- |
| `day` | no | Day to program, `1` = Monday … `7` = Sunday. |
| `slots` | yes | Up to 5 slots, each with `start` (hour, 0–23), `speed` (`low`, `medium` or `high`) and an optional `temperature` (preheat target, 12–18 °C, `0` = no preheating). No slot clears the day. |

```yaml
action: vmi_plus.set_day_schedule
target:
  entity_id: switch.urban_time_slots
data:
  day: 1
  slots:
    - start: 7
      speed: medium
    - start: 22
      speed: low
```

## Data updates

The unit sends nothing on its own: the integration reads it every 10 seconds (the bypass state once
a minute) over a Bluetooth connection that stays open. Changes made with the remote control or the
official app show up at the next read.

## Examples

### Boost during a shower

```yaml
automation:
  - alias: "Ventilation boost during a shower"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.bathroom_humidity
        above: 80
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.urban_boost
```

### Use cases

- Choose the speed from the indoor and outdoor humidity or temperature.
- Get a notification when the filter life gets close to 0 days.
- Turn holiday mode on from an "away" scene.

## Known limitations

- **One connection at a time**: while Home Assistant is connected, the official VMI+ app cannot
  connect, and the other way round.
- Installer settings (volume, surface, filter lifespan, bypass, building management), firmware
  updates, history export and after-sales functions are not available.
- The filter-change command has been decoded from the app but not yet confirmed on a unit.

## Troubleshooting

### The unit is not discovered or becomes unavailable

- Close the official VMI+ app: the unit stops advertising while a client is connected.
- Move a Bluetooth proxy closer to the unit.

### Using the official app

To use the official app, disable the integration (**Settings** > **Devices & services** >
**VMI+** > three dots > **Disable**), then enable it again afterwards.

## Removing the integration

This integration follows standard integration removal. Nothing is stored on the unit.

{% include integrations/remove_device_service.md %}
