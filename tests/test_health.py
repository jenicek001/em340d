"""#12 step 4: the container is healthy only while the meter answers."""
import health
from modbus_bus import ModbusBus
from tests.modbus_sim import SimBus


def bus_with(sim_ok=True):
    sim = SimBus(turnaround_s=0.01)
    sim.slave(1, {0: 1})
    bus = ModbusBus("/dev/sim", turnaround_s=0.01, instrument_factory=sim.instrument)
    bus.start()
    if sim_ok:
        bus.read_register(1, 0)
    return bus


def test_healthy_when_the_meter_answered_recently(tmp_path):
    bus = bus_with()
    health.write(tmp_path / "h", bus, now=1000.0)
    ok, reason = health.check(tmp_path / "h", now=1010.0)
    bus.stop()
    assert ok and reason.startswith("ok")


def test_unhealthy_before_the_first_answer(tmp_path):
    bus = bus_with(sim_ok=False)
    health.write(tmp_path / "h", bus, now=1000.0)
    bus.stop()
    assert health.check(tmp_path / "h", now=1001.0) == (False, "the meter has not answered since the start")


def test_unhealthy_when_the_main_loop_stopped_writing(tmp_path):
    bus = bus_with()
    health.write(tmp_path / "h", bus, now=1000.0)
    bus.stop()
    ok, reason = health.check(tmp_path / "h", now=1100.0)
    assert not ok and "main loop" in reason


def test_unhealthy_when_the_meter_stopped_answering(tmp_path):
    import json
    (tmp_path / "h").write_text(json.dumps({"ts": 1000.0, "last_success_age_s": 75.0, "port_open": False}))
    ok, reason = health.check(tmp_path / "h", now=1001.0)
    assert not ok and "75 s ago" in reason


def test_no_file_is_unhealthy(tmp_path):
    assert health.check(tmp_path / "none")[0] is False
