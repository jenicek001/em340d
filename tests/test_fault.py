"""Why the meter is offline: the USB-RS485 adapter, or the meter behind it (owner 2026-11-20).

Two failures look the same from MQTT today - no readings - and need different hands: an adapter that is unplugged or
whose port failed (re-plug, check the USB cable or the computer), or an adapter that works while nothing answers on
the RS485 bus (the meter's power, its address, the RS485 cable, or an adapter that hangs). em340d now says which, on
the retained <topic>/fault next to <topic>/status, in its log and in its health file. A simulated bus, no serial port."""
import json

import pytest

import em340
from status import FAULTS, diagnose
from tests.test_em340_snapshots import at, daemon  # noqa: F401 - the fixture


def test_diagnosis_from_the_errors_of_one_poll():
    assert diagnose(got_readings=True, errors=["no_answer"], port_exists=True) is None
    assert diagnose(got_readings=False, errors=["adapter"], port_exists=False) == "adapter"
    assert diagnose(got_readings=False, errors=["no_answer", "no_answer"], port_exists=True) == "no_answer"
    assert diagnose(got_readings=False, errors=["invalid", "no_answer"], port_exists=True) == "invalid"
    assert diagnose(got_readings=False, errors=["meter_error"], port_exists=True) == "meter_error"


def test_no_answer_while_the_device_file_is_gone_is_the_adapter():
    """A vanished adapter can also show as a read that just times out: the device file decides."""
    assert diagnose(got_readings=False, errors=["no_answer"], port_exists=False) == "adapter"


def test_every_fault_has_a_plain_explanation():
    assert set(FAULTS) == {"adapter", "no_answer", "invalid", "meter_error"}
    assert all(isinstance(v, str) and v for v in FAULTS.values())


def _published(d, suffix):
    return [c.args[1] for c in d.mqtt_client.publish.call_args_list if c.args[0] == f"{d.topic}/{suffix}"]


def _cycles(d, n):
    blocks = em340.build_blocks(d.sensors)
    for _ in range(n):
        d._publish_status(d.poll_once(blocks))


def test_an_unplugged_adapter_is_reported_as_the_adapter(daemon):  # noqa: F811
    d, sim = daemon(at("2026-10-12 14:14:50"))
    d._port_exists = lambda: False
    _cycles(d, 1)
    sim.faults = ["port_lost"]                                       # unplugged: the port fails, the file is gone
    _cycles(d, 3)
    assert _published(d, "status")[-1] == "offline"
    fault = json.loads(_published(d, "fault")[-1])
    assert fault["fault"] == "adapter" and fault["port"] == d.device


def test_a_silent_meter_behind_a_working_adapter_is_reported_as_no_answer(daemon):  # noqa: F811
    d, sim = daemon(at("2026-10-12 14:14:50"))
    d._port_exists = lambda: True
    _cycles(d, 1)
    sim.meter_silent = True
    _cycles(d, 3)
    assert _published(d, "status")[-1] == "offline"
    assert json.loads(_published(d, "fault")[-1])["fault"] == "no_answer"


def test_the_fault_clears_when_the_meter_answers_again(daemon):  # noqa: F811
    d, sim = daemon(at("2026-10-12 14:14:50"))
    d._port_exists = lambda: True
    sim.meter_silent = True
    _cycles(d, 3)
    sim.meter_silent = False
    _cycles(d, 1)
    assert _published(d, "status")[-1] == "online"
    assert json.loads(_published(d, "fault")[-1])["fault"] is None


def test_a_replugged_adapter_with_a_silent_meter_changes_the_fault(daemon):  # noqa: F811
    """Offline throughout, but the reason moves from the adapter to the meter: published again."""
    d, sim = daemon(at("2026-10-12 14:14:50"))
    d._port_exists = lambda: False
    sim.faults = ["port_lost"]
    _cycles(d, 3)
    assert json.loads(_published(d, "fault")[-1])["fault"] == "adapter"
    d._port_exists = lambda: True
    sim.port_ok, sim.meter_silent = True, True
    import time
    time.sleep(2.1)                                                  # past the bus's reopen backoff
    _cycles(d, 3)
    assert json.loads(_published(d, "fault")[-1])["fault"] == "no_answer"
