"""The meter's own online/offline status and its Home Assistant MQTT discovery (SmartHomeDesign-EMS REQ-081).

`<topic>/status` is retained: `online` while the meter answers, `offline` after FAILS_BEFORE_OFFLINE polls in a row
without a single reading, and `offline` as em340d's MQTT last will. The discovery message announces the meter's total
active power with that availability topic, so a monitor that reads discovery finds it with nothing to configure."""
import json
from typing import List, Optional, Tuple

FAILS_BEFORE_OFFLINE = 3            # polls in a row without a reading (30 s at the default 10 s interval)
ONLINE, OFFLINE = "online", "offline"


class StatusTracker:
    def __init__(self):
        self.current: Optional[str] = None
        self._fails = 0

    def update(self, got_readings: bool) -> Optional[str]:
        """The status to publish now, or None when it has not changed."""
        if got_readings:
            self._fails = 0
            new = ONLINE
        else:
            self._fails += 1
            new = OFFLINE if self._fails >= FAILS_BEFORE_OFFLINE else self.current
        if new is None or new == self.current:
            return None
        self.current = new
        return new


def discovery_messages(prefix: str, state_topic: str, status_topic: str, serial: str) -> List[Tuple[str, str]]:
    """(topic, payload) to publish retained; none when the prefix is empty (discovery off)."""
    if not prefix:
        return []
    uid = f"em340_{serial}"
    cfg = {"name": "Active power", "uniq_id": f"{uid}_active_power_sys", "stat_t": state_topic,
           "val_tpl": "{{ value_json.active_power_sys }}", "unit_of_meas": "W", "dev_cla": "power",
           "stat_cla": "measurement", "avty_t": status_topic, "pl_avail": ONLINE, "pl_not_avail": OFFLINE,
           "dev": {"ids": [uid], "name": f"EM340 {serial}", "mf": "Carlo Gavazzi", "mdl": "EM340"}}
    return [(f"{prefix}/sensor/{uid}/active_power_sys/config", json.dumps(cfg))]


# Why the meter is offline (owner 2026-11-20): the adapter, or what is behind it. Most specific first.
FAULTS = {
    "adapter": "the USB-RS485 adapter is missing or its serial port failed (unplugged, USB cable, USB power, driver)",
    "invalid": "answers arrive garbled (CRC, framing): RS485 wiring, polarity, termination, baud rate, interference",
    "meter_error": "the meter answers but refuses the request (Modbus exception): address map, firmware",
    "no_answer": "the adapter works but nothing answers on the RS485 bus: the meter's power or address, the RS485 "
                 "cable, or an adapter that hangs",
}
_ORDER = ("adapter", "invalid", "meter_error", "no_answer")


def diagnose(got_readings: bool, errors, port_exists: bool) -> Optional[str]:
    """The fault of one poll: None when it read anything. A read that only timed out while the device file is gone
    is the adapter too (an unplugged adapter does not always raise a port error first)."""
    if got_readings:
        return None
    if not port_exists:
        return "adapter"
    found = set(errors or ())
    return next((f for f in _ORDER if f in found), "no_answer")
