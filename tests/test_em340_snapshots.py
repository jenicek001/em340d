"""Issue #6 in the daemon, on the ModbusBus (#12): the quarter-hour snapshot is published retained on
em340/<serial>/interval, the regular message carries the 1 Wh totals, the poll reads every block, and the loop
wakes at the boundary. A simulated bus, no serial port."""
import json
import unittest.mock as mock
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import em340
from energy import EnergyReader
from modbus_bus import ModbusBus
from tests.modbus_sim import SimBus
from tests.test_em340_init import _make_em340
from tests.test_energy import em340_registers

PRAGUE = ZoneInfo("Europe/Prague")


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=PRAGUE).timestamp()


@pytest.fixture
def daemon():
    made = []

    def make(now):
        with mock.patch("energy.wall_clock", return_value=now), mock.patch("em340.wall_clock", return_value=now):
            d = _make_em340()
        d.bus.stop()
        sim = SimBus(turnaround_s=0.01)
        sim.slave(1, {**em340_registers(), 0x0000: 2301, 0x0001: 0})      # voltage L1 = 230.1 V
        d.bus = ModbusBus("/dev/sim", turnaround_s=0.01, instrument_factory=sim.instrument)
        d.bus.start()
        d.energy = EnergyReader(d.bus, 1)
        d.mqtt_client = mock.MagicMock()
        d.mqtt_client.publish.return_value.rc = 0
        made.append(d)
        return d, sim
    yield make
    for d in made:
        d.bus.stop()


def test_the_snapshot_is_published_once_retained_at_the_boundary(daemon):
    d, _ = daemon(at("2026-10-12 14:14:50"))
    with mock.patch("em340.wall_clock", return_value=at("2026-10-12 14:14:59")):
        d._publish_due_snapshot()
    d.mqtt_client.publish.assert_not_called()
    with mock.patch("em340.wall_clock", return_value=at("2026-10-12 14:15:00.100")):
        d._publish_due_snapshot()
        d._publish_due_snapshot()
    assert d.mqtt_client.publish.call_count == 1
    (topic, payload), kwargs = d.mqtt_client.publish.call_args
    assert topic == "em340/TEST123A/interval" and kwargs == {"qos": 1, "retain": True}
    p = json.loads(payload)
    assert p["import_kwh_total"] == 3180.812 and p["resolution_kwh"] == 0.001 and p["read_delay_ms"] == 100
    assert datetime.fromisoformat(p["interval_end"]).timestamp() == at("2026-10-12 14:15:00")


def test_the_poll_after_a_snapshot_keeps_the_meters_turnaround(daemon):
    # 2026-10-12 11:45 on the real EM340: the first block right after the snapshot got "no answer" and a reconnect
    d, sim = daemon(at("2026-10-12 14:14:50"))
    with mock.patch("em340.wall_clock", return_value=at("2026-10-12 14:15:00.100")):
        d._publish_due_snapshot()
    data = d.poll_once(em340.build_blocks(d.sensors))
    assert data == {"voltage_l1": pytest.approx(230.1)}
    assert sim.turnaround_violations == 0 and sim.overlaps == 0


def test_the_regular_message_carries_the_1_wh_totals(daemon):
    d, _ = daemon(at("2026-10-12 14:14:50"))
    data = {"total_energy_import": 3180.8, "total_energy_export": 15619.2}
    d._add_fine_totals(data)
    assert data == {"total_energy_import": 3180.812, "total_energy_export": 15619.204}


def test_a_failed_read_keeps_the_coarse_values(daemon):
    d, sim = daemon(at("2026-10-12 14:14:50"))
    d.energy.fine = True
    sim.faults = ["no_answer", "no_answer"]
    data = {"total_energy_import": 3180.8}
    d._add_fine_totals(data)
    assert data == {"total_energy_import": 3180.8}


def test_a_block_that_fails_is_left_out_and_the_poll_goes_on(daemon):
    d, sim = daemon(at("2026-10-12 14:14:50"))
    sim.faults = ["no_answer", "no_answer"]
    assert d.poll_once(em340.build_blocks(d.sensors)) == {}
    assert d.poll_once(em340.build_blocks(d.sensors)) == {"voltage_l1": pytest.approx(230.1)}


def test_a_lost_port_stops_the_poll_pass_without_a_reconnect_of_mqtt(daemon):
    d, sim = daemon(at("2026-10-12 14:14:50"))
    client = d.mqtt_client
    sim.faults = ["port_lost"]
    assert d.poll_once(em340.build_blocks(d.sensors)) == {}
    assert d.mqtt_client is client                                         # #11: MQTT untouched


def test_the_loop_sleeps_to_the_boundary_when_it_is_nearer_than_the_poll(daemon):
    d, _ = daemon(at("2026-10-12 14:14:50"))
    with mock.patch("em340.wall_clock", return_value=at("2026-10-12 14:14:57")), mock.patch("em340.time.sleep") as sleep:
        d._sleep_until_next_cycle()
    assert abs(sleep.call_args.args[0] - 3.01) < 1e-6
    with mock.patch("em340.wall_clock", return_value=at("2026-10-12 14:01:00")), mock.patch("em340.time.sleep") as sleep:
        d._sleep_until_next_cycle()
    assert sleep.call_args.args[0] == 10.0


@pytest.mark.parametrize("vt, words, value", [
    ("INT16", [0xFFFF], -1), ("UINT16", [0xFFFF], 65535), ("INT32", [0xFFFE, 0xFFFF], -2),
    ("UINT32", [0x0001, 0x0001], 65537), ("INT64", [0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF], -1),
])
def test_values_are_decoded_least_significant_word_first(vt, words, value):
    assert em340.decode_value({"name": "x", "value_type": vt, "multiply": 1}, words) == value


def test_blocks_are_built_like_before():
    from config_loader import load_sensors
    import os
    sensors = load_sensors(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "sensors.yaml"))
    from tests.test_blocks import _build_blocks
    assert [[s["id"] for s in b] for b in em340.build_blocks(sensors)] == \
        [[s["id"] for s in b] for b in _build_blocks(sensors)]
