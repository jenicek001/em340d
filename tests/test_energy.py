"""Issue #6: energy totals at 1 Wh resolution and quarter-hour snapshots - no serial port, a fake meter."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import energy

PRAGUE = ZoneInfo("Europe/Prague")


def regs32(value):
    value &= 0xFFFFFFFF
    return [value & 0xFFFF, value >> 16]


def fine_block(imp, exp):
    """The 12 registers at 0x0400 for the given kWh (kvarh in between are zeros)."""
    def part(kwh):
        i = int(kwh)
        return regs32(i) + regs32(round((kwh - i) * 1000))
    return part(imp) + [0, 0, 0, 0] + part(exp)


class Meter:
    def __init__(self, imp=3180.812, exp=15619.204, fine=True, coarse=None):
        self.imp, self.exp, self.has_fine = imp, exp, fine
        self.coarse = coarse
        self.reads = []

    def read_registers(self, address, number_of_registers):
        self.reads.append((address, number_of_registers))
        if address == energy.FINE_START:
            if not self.has_fine:
                raise IOError("no answer")
            return fine_block(self.imp, self.exp)
        coarse_imp, coarse_exp = self.coarse or (self.imp, self.exp)
        if address == energy.COARSE_IMPORT:
            return regs32(int(coarse_imp * 10))
        if address == energy.COARSE_EXPORT:
            return regs32(int(coarse_exp * 10))
        raise AssertionError(hex(address))


def test_integer_and_decimal_parts_make_1_wh_resolution():
    assert energy.compose_kwh(*regs32(3180), *regs32(812)) == 3180.812
    assert energy.compose_kwh(*regs32(70000), *regs32(5)) == 70000.005      # the integer's MSW
    assert energy.parse_fine_block(fine_block(3180.812, 15619.204)) == (3180.812, 15619.204)


def test_a_short_block_is_an_error():
    with pytest.raises(ValueError):
        energy.parse_fine_block([0] * 8)


def test_the_fine_totalizers_are_used_when_they_agree_with_the_coarse_registers():
    m = Meter()
    r = energy.EnergyReader(lambda: m)
    assert r.read() == (3180.812, 15619.204, 0.001) and r.fine is True
    m.reads.clear()
    m.imp = 3180.9
    assert r.read()[0] == 3180.9 and m.reads == [(0x0400, 12)]                # one block per read afterwards


def test_the_coarse_registers_are_used_when_the_meter_has_no_fine_totalizers():
    m = Meter(fine=False)
    r = energy.EnergyReader(lambda: m)
    assert r.read() == (3180.8, 15619.2, 0.1) and r.fine is False


def test_the_coarse_registers_are_used_when_the_two_disagree():
    m = Meter(coarse=(3100.0, 15619.2))
    r = energy.EnergyReader(lambda: m)
    assert r.read()[2] == 0.1 and r.fine is False


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=PRAGUE).timestamp()


def test_boundaries_are_every_quarter_hour_of_the_local_clock():
    assert energy.next_boundary(at("2026-10-12 14:07:31")) == at("2026-10-12 14:15:00")
    assert energy.next_boundary(at("2026-10-12 14:15:00")) == at("2026-10-12 14:30:00")


@pytest.mark.parametrize("start", ["2026-10-25 01:40:00", "2026-03-29 01:40:00"])
def test_a_dst_change_keeps_96_or_so_boundaries_900_s_apart_on_the_quarter_hour(start):
    t, seen = at(start), []
    for _ in range(12):
        t = energy.next_boundary(t)
        seen.append(t)
    assert all(b - a == 900 for a, b in zip(seen, seen[1:]))
    assert all(datetime.fromtimestamp(s, PRAGUE).minute % 15 == 0 for s in seen)


def test_each_boundary_is_due_once():
    s = energy.QuarterHourSnapshots(at("2026-10-12 14:14:50"))
    assert s.due(at("2026-10-12 14:14:59.900")) is None
    assert s.due(at("2026-10-12 14:15:00.080")) == at("2026-10-12 14:15:00")
    assert s.due(at("2026-10-12 14:15:10")) is None
    assert s.seq == 1 and s.next == at("2026-10-12 14:30:00")


def test_a_boundary_reached_too_late_is_skipped_and_never_published_twice():
    s = energy.QuarterHourSnapshots(at("2026-10-12 14:14:50"))
    assert s.due(at("2026-10-12 14:47:00")) is None                         # a gap: 14:15 is 32 min late
    assert s.next == at("2026-10-12 15:00:00")                              # 14:30 and 14:45 are not replayed
    assert s.due(at("2026-10-12 15:00:00.500")) == at("2026-10-12 15:00:00")


def test_seconds_to_next_lets_the_loop_wake_at_the_boundary():
    s = energy.QuarterHourSnapshots(at("2026-10-12 14:14:50"))
    assert s.seconds_to_next(at("2026-10-12 14:14:53")) == 7.0


def test_the_snapshot_payload():
    b = at("2026-10-11 14:15:00")
    p = energy.snapshot_payload(b, b + 0.083, 3180.812, 15619.204, 0.001, "036245X", 12345, tzinfo=PRAGUE)
    assert p == {"interval_end": "2026-10-11T14:15:00+02:00", "import_kwh_total": 3180.812,
                 "export_kwh_total": 15619.204, "read_at": "2026-10-11T14:15:00.083+02:00", "read_delay_ms": 83,
                 "resolution_kwh": 0.001, "serial": "036245X", "seq": 12345}


def test_the_clock_check_answers_without_failing():
    assert energy.clock_synchronized() in (True, False, None)
