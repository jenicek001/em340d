"""Energy totals at 1 Wh resolution and quarter-hour snapshots (issue #6).

The EM340's "kWh (+) TOT" / "kWh (-) TOT" at 0x0034 / 0x004E have a weight of kWh x 10, a resolution of
0.1 kWh. Meters made from 2018-10-01 also have 3-decimal totalizers (protocol v2 rev. 17, section 2.5,
Table 2.5-1), read here through the ModbusBus as one block of 12 registers so both parts of each value come
from the same moment:

    0x0400 kWh (+) TOT, integer part   INT32  INT(kWh) x 1
    0x0402 kWh (+) TOT, decimal part   INT32  DEC(kWh) x 1000  (MSW always 0)
    0x0408 kWh (-) TOT, integer part   INT32
    0x040A kWh (-) TOT, decimal part   INT32

Czech billing integrates energy over 15-minute intervals. QuarterHourSnapshots fires at every boundary of
900 s from the epoch (hh:00, :15, :30, :45 in UTC and in Czech local time alike), so the energy of each
interval is the difference of two snapshots. The boundary is only as good as the host clock: the host must
keep NTP (clock_synchronized() checks the kernel's view).
"""
import ctypes
import ctypes.util
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import minimalmodbus

from logger import log
from modbus_bus import NORMAL

FINE_START = 0x0400
FINE_COUNT = 12
COARSE_IMPORT = 0x0034
COARSE_EXPORT = 0x004E
COARSE_WEIGHT = 0.1
FINE_RESOLUTION = 0.001
AGREEMENT_KWH = 0.1 + 1e-6          # the coarse registers truncate to 0.1 kWh
PERIOD_S = 900
MAX_LATE_S = 60.0                   # a snapshot read later than this no longer belongs to its boundary


def int32(lo: int, hi: int) -> int:
    """Two registers, least significant word first (as the other EM340 INT32 values)."""
    value = lo + (hi << 16)
    return value - 0x100000000 if value & 0x80000000 else value


def compose_kwh(int_lo: int, int_hi: int, dec_lo: int, dec_hi: int) -> float:
    return round(int32(int_lo, int_hi) + int32(dec_lo, dec_hi) / 1000.0, 3)


def parse_fine_block(regs) -> Tuple[float, float]:
    """(import, export) kWh from the 12 registers at 0x0400."""
    if regs is None or len(regs) != FINE_COUNT:
        raise ValueError(f"expected {FINE_COUNT} registers at 0x{FINE_START:04X}, got {0 if regs is None else len(regs)}")
    return compose_kwh(*regs[0:4]), compose_kwh(*regs[8:12])


class EnergyReader:
    """The import and export totals at the best resolution the meter has, read through the ModbusBus (#12),
    which keeps the meter's turnaround and retries. The 3-decimal totalizers are checked once against the
    0.1 kWh registers. Only the meter itself can say they are missing (a slave exception: illegal address)
    or a disagreement can disqualify them; then the 0.1 kWh registers are used, with resolution_kwh 0.1. A
    timeout or an unavailable bus decides nothing: the next read checks again."""

    def __init__(self, bus, slave: int):
        self.bus, self.slave = bus, slave
        self.fine: Optional[bool] = None

    def _read(self, address: int, count: int, priority: int):
        return self.bus.read_registers(self.slave, address, count, priority=priority)

    def _coarse(self, priority: int) -> Tuple[float, float]:
        imp = int32(*self._read(COARSE_IMPORT, 2, priority)) * COARSE_WEIGHT
        exp = int32(*self._read(COARSE_EXPORT, 2, priority)) * COARSE_WEIGHT
        return round(imp, 1), round(exp, 1)

    def _check_fine(self, priority: int):
        try:
            fine = parse_fine_block(self._read(FINE_START, FINE_COUNT, priority))
        except (minimalmodbus.SlaveReportedException, ValueError) as err:
            log.warning(f"3-decimal energy totalizers (0x0400) not available ({err}); using 0x0034/0x004E, 0.1 kWh")
            self.fine = False
            return
        coarse = self._coarse(priority)
        if all(abs(f - c) <= AGREEMENT_KWH for f, c in zip(fine, coarse)):
            log.info(f"Energy at 1 Wh resolution from 0x0400/0x0408: import {fine[0]:.3f} kWh, export {fine[1]:.3f} kWh "
                     f"(0.1 kWh registers {coarse[0]:.1f} / {coarse[1]:.1f})")
            self.fine = True
        else:
            log.warning(f"3-decimal totalizers {fine} disagree with the 0.1 kWh registers {coarse}; using 0.1 kWh")
            self.fine = False

    def read(self, priority: int = NORMAL) -> Tuple[float, float, float]:
        """(import kWh, export kWh, resolution kWh). Raises what the bus raises (IOError, TimeoutError)."""
        if self.fine is None:
            self._check_fine(priority)
        if self.fine:
            imp, exp = parse_fine_block(self._read(FINE_START, FINE_COUNT, priority))
            return imp, exp, FINE_RESOLUTION
        imp, exp = self._coarse(priority)
        return imp, exp, COARSE_WEIGHT


def next_boundary(now: float, period: int = PERIOD_S) -> float:
    """The first boundary strictly after `now`."""
    return (int(now // period) + 1) * period


class QuarterHourSnapshots:
    """Which boundary a reading at `now` belongs to. Each boundary is returned at most once; one reached
    more than MAX_LATE_S late (a restart, a serial error) is skipped, and the next one is awaited."""

    def __init__(self, now: float, period: int = PERIOD_S, max_late_s: float = MAX_LATE_S):
        self.period, self.max_late_s = period, max_late_s
        self.next = next_boundary(now, period)
        self.seq = 0

    def due(self, now: float) -> Optional[float]:
        if now < self.next:
            return None
        boundary = self.next
        self.next = next_boundary(now, self.period)
        if now - boundary > self.max_late_s:
            log.warning(f"Quarter-hour snapshot for {datetime.fromtimestamp(boundary).isoformat()} skipped: "
                        f"reached {now - boundary:.0f} s late")
            return None
        self.seq += 1
        return boundary

    def seconds_to_next(self, now: float) -> float:
        return max(0.0, self.next - now)


def snapshot_payload(boundary: float, read_at: float, imp: float, exp: float, resolution: float,
                     serial: str, seq: int, tzinfo=None) -> dict:
    local = (lambda t: datetime.fromtimestamp(t, tz=tzinfo)) if tzinfo else (
        lambda t: datetime.fromtimestamp(t, tz=timezone.utc).astimezone())
    return {
        "interval_end": local(boundary).isoformat(),
        "import_kwh_total": imp,
        "export_kwh_total": exp,
        "read_at": local(read_at).isoformat(timespec="milliseconds"),
        "read_delay_ms": int(round((read_at - boundary) * 1000)),
        "resolution_kwh": resolution,
        "serial": serial,
        "seq": seq,
    }


class _Timex(ctypes.Structure):
    # struct timex (Linux): only the leading fields are used; the rest is padding
    _fields_ = [("modes", ctypes.c_uint), ("offset", ctypes.c_long), ("freq", ctypes.c_long),
                ("maxerror", ctypes.c_long), ("esterror", ctypes.c_long), ("status", ctypes.c_int),
                ("_pad", ctypes.c_byte * 256)]


TIME_ERROR = 5


def clock_synchronized() -> Optional[bool]:
    """The kernel's NTP view (adjtimex, read only; works in a container): True synchronised, False not,
    None unknown (not Linux)."""
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        tx = _Timex()
        state = libc.adjtimex(ctypes.byref(tx))
        if state < 0:
            return None
        return state != TIME_ERROR
    except (OSError, AttributeError):
        return None


def wall_clock() -> float:
    return time.time()
