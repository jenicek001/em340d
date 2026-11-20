"""The device's own online/offline status (SmartHomeDesign-EMS REQ-081, 2026-11-20).

On 2026-11-19 the meter's Modbus reads failed for 68 minutes while em340d kept publishing {"last_seen": ...}: nothing
said the meter was gone. em340d now keeps a retained status: online while the meter answers, offline after a few polls
without a reading, and offline as its MQTT last will when em340d itself is gone. It announces the meter by Home
Assistant MQTT discovery with that status, so any monitor that reads discovery finds it without configuration."""
import json

from status import FAILS_BEFORE_OFFLINE, StatusTracker, discovery_messages


def test_online_from_the_first_poll_with_readings():
    s = StatusTracker()
    assert s.update(True) == "online"
    assert s.update(True) is None                          # published on a change only


def test_offline_only_after_several_polls_without_a_reading():
    s = StatusTracker()
    s.update(True)
    for _ in range(FAILS_BEFORE_OFFLINE - 1):
        assert s.update(False) is None                      # one lost poll is not an outage
    assert s.update(False) == "offline"
    assert s.update(False) is None
    assert s.update(True) == "online"


def test_unknown_until_the_first_verdict():
    s = StatusTracker()
    assert s.current is None
    for _ in range(FAILS_BEFORE_OFFLINE):
        s.update(False)
    assert s.current == "offline"


def test_discovery_announces_the_meter_with_its_status():
    msgs = dict(discovery_messages("homeassistant", "em340/036245X", "em340/036245X/status", "036245X"))
    cfg = json.loads(msgs["homeassistant/sensor/em340_036245X/active_power_sys/config"])
    assert cfg["stat_t"] == "em340/036245X" and cfg["avty_t"] == "em340/036245X/status"
    assert cfg["val_tpl"] == "{{ value_json.active_power_sys }}"
    assert cfg["dev"]["ids"] == ["em340_036245X"] and cfg["unit_of_meas"] == "W"
    assert cfg["pl_avail"] == "online" and cfg["pl_not_avail"] == "offline"


def test_no_prefix_no_discovery():
    assert discovery_messages("", "em340/x", "em340/x/status", "x") == []
