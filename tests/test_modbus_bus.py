"""ModbusBus (#12): the only owner of the serial port. Run against tests/modbus_sim.py - no serial port."""
import threading
import time

import minimalmodbus
import pytest

from modbus_bus import HIGH, NORMAL, BusUnavailable, ModbusBus
from tests.modbus_sim import SimBus

T = 0.02                                     # turnaround in the tests


@pytest.fixture
def sim():
    s = SimBus(turnaround_s=T)
    s.slave(1, {0x0400: 3180, 0x0401: 0, 0x0402: 812, 0x0403: 0, 0x1103: 1})
    s.slave(2, {0x0000: 7})
    return s


@pytest.fixture
def bus(sim):
    b = ModbusBus("/dev/sim", turnaround_s=T, instrument_factory=sim.instrument, reopen_backoff=(0.05, 0.2))
    b.start()
    yield b
    b.stop()


def test_reads_and_writes_reach_the_right_slave(bus, sim):
    assert bus.read_registers(1, 0x0400, 4) == [3180, 0, 812, 0]
    assert bus.read_register(2, 0x0000) == 7
    bus.write_register(1, 0x1103, 0)
    assert sim.registers[1][0x1103] == 0


def test_back_to_back_requests_always_respect_the_turnaround(bus, sim):
    for _ in range(10):
        bus.read_registers(1, 0x0400, 4)
    assert sim.turnaround_violations == 0
    gaps = [b[4] - a[5] for a, b in zip(sim.log, sim.log[1:])]
    assert min(gaps) >= T


def test_callers_on_many_threads_never_overlap_and_all_get_answers(bus, sim):
    results, errors = [], []

    def caller(slave, address):
        try:
            for _ in range(15):
                results.append(bus.read_registers(slave, address, 1))
        except Exception as exc:                # noqa: BLE001
            errors.append(exc)
    threads = [threading.Thread(target=caller, args=a) for a in ((1, 0x0400), (1, 0x0402), (2, 0x0000))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert not errors and len(results) == 45
    assert sim.overlaps == 0 and sim.turnaround_violations == 0


def test_a_high_priority_request_overtakes_queued_normal_ones(bus, sim):
    gate, started = threading.Event(), threading.Event()
    order = []

    def blocker(inst):
        started.set()
        gate.wait(1)
        order.append("blocker")
    bus.submit(blocker, slave=1, priority=NORMAL)
    assert started.wait(1)                                                  # the blocker is in flight
    futures = [bus.submit(lambda inst, i=i: order.append(f"poll{i}"), slave=1) for i in range(5)]
    snap = bus.submit(lambda inst: order.append("snapshot"), slave=1, priority=HIGH)
    gate.set()
    snap.result(2)
    for f in futures:
        f.result(2)
    assert order[0] == "blocker" and order[1] == "snapshot"


def test_a_read_without_answer_is_retried_once_after_the_turnaround(bus, sim):
    sim.faults = ["no_answer"]
    assert bus.read_registers(1, 0x0400, 1) == [3180]
    assert bus.stats()["retries"] == 1 and bus.stats()["no_answer"] == 1
    assert sim.turnaround_violations == 0


def test_an_invalid_answer_is_retried_once(bus, sim):
    sim.faults = ["invalid"]
    assert bus.read_register(1, 0x0402) == 812
    assert bus.stats()["invalid"] == 1


def test_two_failures_in_a_row_reach_the_caller(bus, sim):
    sim.faults = ["no_answer", "no_answer"]
    with pytest.raises(minimalmodbus.NoResponseError):
        bus.read_registers(1, 0x0400, 1)


def test_a_write_is_never_retried(bus, sim):
    sim.faults = ["no_answer"]
    with pytest.raises(minimalmodbus.NoResponseError):
        bus.write_register(1, 0x1103, 0)
    assert [e for e in sim.log if e[1] == "write"].__len__() == 1


def test_a_slave_exception_is_returned_at_once(bus, sim):
    sim.faults = ["illegal"]
    with pytest.raises(minimalmodbus.IllegalRequestError):
        bus.read_registers(1, 0x9999, 1)
    assert bus.stats()["retries"] == 0 and bus.stats()["slave_errors"] == 1


def test_a_lost_port_is_reopened_with_backoff_and_requests_fail_fast_meanwhile(bus, sim):
    sim.faults = ["port_lost"]
    with pytest.raises(BusUnavailable):
        bus.read_registers(1, 0x0400, 1)
    with pytest.raises(BusUnavailable):                          # still down: fast, no waiting on the port
        t0 = time.monotonic()
        bus.read_registers(1, 0x0400, 1)
    assert time.monotonic() - t0 < 0.5
    sim.port_ok = True
    time.sleep(0.25)                                             # past the backoff
    assert bus.read_registers(1, 0x0400, 1) == [3180]
    assert bus.stats()["reopens"] >= 1 and bus.stats()["port_errors"] >= 1


def test_the_caller_can_give_up_waiting(bus, sim):
    gate = threading.Event()
    bus.submit(lambda inst: gate.wait(1), slave=1)
    with pytest.raises(TimeoutError):
        bus.read_registers(1, 0x0400, 1, timeout=0.05)
    gate.set()


def test_stats_and_the_age_of_the_last_success(bus, sim):
    assert bus.last_success_age() is None
    bus.read_registers(1, 0x0400, 1)
    s = bus.stats()
    assert s["requests"] == 1 and s["ok"] == 1 and s["queue"] == 0
    assert bus.last_success_age() < 1.0


def test_stop_refuses_new_requests(sim):
    b = ModbusBus("/dev/sim", turnaround_s=T, instrument_factory=sim.instrument)
    b.start()
    b.stop()
    with pytest.raises(BusUnavailable):
        b.read_registers(1, 0x0400, 1)
