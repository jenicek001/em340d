"""Issue #6 in the daemon: the quarter-hour snapshot is published retained on em340/<serial>/interval, the
regular message carries the 1 Wh totals, and the loop wakes at the boundary. Hardware is mocked."""
import json
import unittest.mock as mock
from datetime import datetime
from zoneinfo import ZoneInfo

from tests.test_em340_init import _make_em340
from tests.test_energy import Meter

PRAGUE = ZoneInfo("Europe/Prague")


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=PRAGUE).timestamp()


def daemon(now):
    with mock.patch("energy.wall_clock", return_value=now), mock.patch("em340.wall_clock", return_value=now):
        d = _make_em340()
    meter = Meter()
    d.em340 = meter
    d.mqtt_client = mock.MagicMock()
    d.mqtt_client.publish.return_value.rc = 0
    return d, meter


def test_the_snapshot_is_published_once_retained_at_the_boundary():
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
    assert datetime.fromisoformat(p["interval_end"]).timestamp() == at("2026-10-12 14:15:00")   # in the host's zone


def test_the_regular_message_carries_the_1_wh_totals():
    d, _ = daemon(at("2026-10-12 14:14:50"))
    data = {"total_energy_import": 3180.8, "total_energy_export": 15619.2}
    d._add_fine_totals(data)
    assert data == {"total_energy_import": 3180.812, "total_energy_export": 15619.204}


def test_a_failed_read_keeps_the_coarse_values():
    d, meter = daemon(at("2026-10-12 14:14:50"))
    d.energy.fine = True
    meter.read_registers = mock.Mock(side_effect=IOError("timeout"))
    data = {"total_energy_import": 3180.8}
    d._add_fine_totals(data)
    assert data == {"total_energy_import": 3180.8}


def test_the_loop_sleeps_to_the_boundary_when_it_is_nearer_than_the_poll():
    d, _ = daemon(at("2026-10-12 14:14:50"))
    with mock.patch("em340.wall_clock", return_value=at("2026-10-12 14:14:57")), mock.patch("em340.time.sleep") as sleep:
        d._sleep_until_next_cycle()
    assert abs(sleep.call_args.args[0] - 3.01) < 1e-6
    with mock.patch("em340.wall_clock", return_value=at("2026-10-12 14:01:00")), mock.patch("em340.time.sleep") as sleep:
        d._sleep_until_next_cycle()
    assert sleep.call_args.args[0] == 10.0
