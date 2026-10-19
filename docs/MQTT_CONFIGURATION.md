# EM340 configuration over MQTT

em340d can read and change the EM340's own settings over MQTT. **A change is a Modbus write into the meter's registers.** It stays in the meter when em340d stops, and it can change what the meter measures and counts. The EM340 is often the billing reference, so writes are protected (#17):

- **Off by default.** They are enabled only in em340d's own environment, `CONFIG_WRITE_ENABLED=true`, never over MQTT. With writes off, every `set` is answered with `error: writes disabled`.
- **Critical parameters need the serial number in the payload:** the measuring system, the measurement mode and the password. The payload must repeat the meter's serial number (`DEVICE_SERIAL_NUMBER`) as a confirmation that the change is intended: `{"value": 1, "serial": "036245X"}`.
- **Every write** is checked against the range from the manual, read back from the meter, logged at WARNING, and answered on `.../status`.

Source: `docs/EM330_EM340_ET330_ET340_CP.pdf` (Series 300 Communication Protocol, v2 rev 17). The EM340 is direct-connected (input AV2) and has **no CT or VT ratio**.

## Parameters

| Parameter | Register | Values | Critical |
|---|---|---|---|
| `password` | 0x1000 | 0–9999 | yes |
| `measuring_system` | 0x1002 | 0 = 3-phase 4-wire with neutral, 1 = 3-phase 3-wire without neutral, 2 = 2-phase 3-wire | yes |
| `display_mode` | 0x1100 | 0 = Full, 1 = Easy | |
| `tariff_enabling` | 0x1101 | 0 = OFF, 1 = ON | |
| `home_page_selection` | 0x1102 | 0–19 (cannot be changed on MID models PFA/PFB) | |
| `measurement_mode` | 0x1103 | 0 = Easy connection (A), 1 = Bidirectional (B) | yes |
| `wrong_connection_help` | 0x1104 | 0 = ON, 1 = OFF | |
| `tariff_mode` | 0x1200 | 0 = via digital inputs, 1 = via serial communication | |
| `tariff_number` | 0x1201 | 1 or 2 | |

**Measurement mode B** is needed for separate import and export counters. Mode A counts every kWh as import.

## Topics

Base: `{MQTT_TOPIC}/{DEVICE_SERIAL_NUMBER}/config/`, e.g. `em340/036245X/config/`.

| Topic | Payload | Answer |
|---|---|---|
| `available` (retained) | the parameter table above as JSON, incl. `critical` | – |
| `{parameter}/get` | empty | `{parameter}/value`: `{"parameter", "value", "display_value", "timestamp"}` |
| `{parameter}/set` | a value (`1`, `"Easy"`), or `{"value": …, "serial": "…"}`; the serial is required for critical parameters | `{parameter}/status`: `{"parameter", "value", "status": "success" \| "verification_failed" \| "error: …", "timestamp"}` |
| `batch/set` | `{"display_mode": 1, "measurement_mode": 1, "serial": "036245X"}`; the serial applies to the critical parameters in the batch | one `status` per parameter and `batch/result` |
| `backup` | empty | `backup/data` (retained): every parameter read from the meter |
| `restore` | a backup, plus `"serial": "…"` if critical parameters are to be restored | `status` per parameter; critical ones without the serial are refused |
| `reset` | – | refused: the factory reset was removed (it set measurement mode A and so stopped the export counters) |

## Examples

```bash
# read
mosquitto_pub -t "em340/036245X/config/measuring_system/get" -m ""
mosquitto_sub -t "em340/036245X/config/measuring_system/value" -C 1

# a non-critical parameter: a plain value
mosquitto_pub -t "em340/036245X/config/display_mode/set" -m "1"

# a critical parameter: repeat the meter's serial number
mosquitto_pub -t "em340/036245X/config/measurement_mode/set" -m '{"value": 1, "serial": "036245X"}'

# watch the answers
mosquitto_sub -t "em340/036245X/config/+/status" -t "em340/036245X/config/error" -v
```

## Enabling writes

In em340d's environment (`.env` / docker compose), then restart em340d:

```
CONFIG_WRITE_ENABLED=true
```

Leave it `false` except while you change a setting on purpose.
