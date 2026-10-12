"""ModbusBus: the only owner of the serial port (#12).

Every Modbus request - the poll, the quarter-hour snapshot, the configuration service - goes through one
ModbusBus. It guarantees what each caller used to have to remember itself:

- **one transaction at a time:** a single worker thread takes requests from a priority queue; callers on any
  thread wait on a future, with a timeout;
- **the slave's turnaround:** `turnaround_s` (DELAY_MS) between the end of one transaction, answered or not,
  and the next request - a request sent sooner gets no answer from the EM340 (2026-10-12);
- **priority:** HIGH (the quarter-hour snapshot) overtakes queued NORMAL requests and waits for at most the
  one transaction in flight;
- **retries by kind:** a read with no answer or an invalid answer (CRC, framing) is retried once, after the
  turnaround; an exception the slave reports is returned at once; a write or a custom request is never
  retried;
- **port failure:** a SerialException or OSError closes the port; it is reopened - the port only - with a
  backoff (2 s doubling to 60 s), and requests fail fast with BusUnavailable meanwhile;
- **stats and health:** counters and the age of the last success.

    bus = ModbusBus("/dev/ttyUSB0", turnaround_s=0.05)
    bus.start()
    regs = bus.read_registers(1, 0x0400, 12, priority=HIGH)
"""
import itertools
import queue
import threading
import time
from concurrent.futures import Future
from typing import Any, Callable, Dict, Optional

import minimalmodbus
import serial

from logger import log

HIGH = 0
NORMAL = 10


class BusUnavailable(IOError):
    """The port is closed (after a failure, until the next reopen attempt) or the bus is stopped."""


def serial_instrument_factory(baudrate=9600, bytesize=8, parity=serial.PARITY_NONE, stopbits=1, timeout_s=0.5):
    """minimalmodbus instruments in RTU mode; instruments on one port share its serial object."""
    def create(port: str, slave: int):
        inst = minimalmodbus.Instrument(port, slave)
        inst.serial.baudrate = baudrate
        inst.serial.bytesize = bytesize
        inst.serial.parity = parity
        inst.serial.stopbits = stopbits
        inst.serial.timeout = timeout_s
        inst.mode = minimalmodbus.MODE_RTU
        inst.close_port_after_each_call = False
        inst.clear_buffers_before_each_transaction = True
        return inst
    return create


class _Request:
    __slots__ = ("fn", "slave", "kind", "future")

    def __init__(self, fn, slave, kind):
        self.fn, self.slave, self.kind, self.future = fn, slave, kind, Future()


class ModbusBus:
    def __init__(self, port: str, *, turnaround_s: float = 0.05, instrument_factory: Optional[Callable] = None,
                 reopen_backoff=(2.0, 60.0), default_timeout_s: float = 10.0, clock: Callable[[], float] = time.monotonic):
        self.port, self.turnaround_s, self.clock = port, turnaround_s, clock
        self._factory = instrument_factory or serial_instrument_factory()
        self._backoff_min, self._backoff_max = reopen_backoff
        self._backoff = self._backoff_min
        self.default_timeout_s = default_timeout_s
        self._queue: "queue.PriorityQueue" = queue.PriorityQueue()
        self._seq = itertools.count()
        self._instruments: Dict[int, Any] = {}
        self._port_down_until: Optional[float] = None
        self._last_end: Optional[float] = None
        self._last_ok: Optional[float] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stats = dict(requests=0, ok=0, retries=0, no_answer=0, invalid=0, slave_errors=0, port_errors=0,
                           reopens=0)

    # --- lifecycle ---------------------------------------------------------------------------------------

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._worker, name="modbus-bus", daemon=True)
        self._thread.start()
        log.info(f"Modbus bus on {self.port}: turnaround {self.turnaround_s * 1000:.0f} ms")

    def stop(self, timeout_s: float = 5.0):
        """Finish the transaction in flight, fail the queued ones, close the port."""
        self._running = False
        self._queue.put((-1, -1, None))
        if self._thread is not None:
            self._thread.join(timeout_s)
        while True:
            try:
                _, _, req = self._queue.get_nowait()
            except queue.Empty:
                break
            if req is not None and req.future.set_running_or_notify_cancel():
                req.future.set_exception(BusUnavailable("the Modbus bus is stopped"))
        self._close_port()

    # --- requests ----------------------------------------------------------------------------------------

    def submit(self, fn: Callable, slave: int, priority: int = NORMAL, kind: str = "custom") -> Future:
        """Queue fn(instrument) for `slave`; kind "read" is retried once on a transient error."""
        if not self._running:
            raise BusUnavailable("the Modbus bus is stopped")
        req = _Request(fn, slave, kind)
        self._stats["requests"] += 1
        self._queue.put((priority, next(self._seq), req))
        return req.future

    def read_registers(self, slave: int, address: int, count: int, functioncode: int = 3,
                       priority: int = NORMAL, timeout: Optional[float] = None):
        return self._wait(self.submit(lambda inst: inst.read_registers(address, number_of_registers=count,
                                                                       functioncode=functioncode),
                                      slave, priority, "read"), timeout)

    def read_register(self, slave: int, address: int, functioncode: int = 3, priority: int = NORMAL,
                      timeout: Optional[float] = None):
        return self._wait(self.submit(lambda inst: inst.read_register(address, functioncode=functioncode),
                                      slave, priority, "read"), timeout)

    def write_register(self, slave: int, address: int, value: int, functioncode: int = 6,
                       priority: int = NORMAL, timeout: Optional[float] = None):
        return self._wait(self.submit(lambda inst: inst.write_register(address, value, functioncode=functioncode),
                                      slave, priority, "write"), timeout)

    def _wait(self, future: Future, timeout: Optional[float]):
        import concurrent.futures
        try:
            return future.result(timeout if timeout is not None else self.default_timeout_s)
        except concurrent.futures.TimeoutError:      # a separate class before Python 3.11
            future.cancel()
            raise TimeoutError("the Modbus request was not served in time") from None

    # --- health ------------------------------------------------------------------------------------------

    def stats(self) -> dict:
        return {**self._stats, "queue": self._queue.qsize(), "port_open": self._port_down_until is None}

    def last_success_age(self) -> Optional[float]:
        return None if self._last_ok is None else self.clock() - self._last_ok

    # --- the worker --------------------------------------------------------------------------------------

    def _worker(self):
        while True:
            _, _, req = self._queue.get()
            if req is None:
                return
            if not req.future.set_running_or_notify_cancel():
                continue                                  # the caller gave up while it was queued
            try:
                req.future.set_result(self._execute(req))
            except BaseException as exc:                  # noqa: BLE001 - handed to the caller
                req.future.set_exception(exc)

    def _execute(self, req: _Request):
        attempts = 2 if req.kind == "read" else 1
        for attempt in range(attempts):
            inst = self._instrument(req.slave)
            self._wait_turnaround()
            try:
                result = req.fn(inst)
            except minimalmodbus.SlaveReportedException:
                self._last_end = self.clock()
                self._stats["slave_errors"] += 1
                raise
            except minimalmodbus.MasterReportedException as exc:   # no answer, CRC, framing, local echo
                self._last_end = self.clock()
                self._stats["no_answer" if isinstance(exc, minimalmodbus.NoResponseError) else "invalid"] += 1
                if attempt + 1 < attempts:
                    self._stats["retries"] += 1
                    log.debug(f"Modbus slave {req.slave}: {exc}; retrying once")
                    continue
                raise
            except (serial.SerialException, OSError) as exc:
                self._last_end = self.clock()
                self._port_failed(exc)
                raise BusUnavailable(f"{self.port}: {exc}") from exc
            self._last_end = self._last_ok = self.clock()
            self._stats["ok"] += 1
            return result

    def _wait_turnaround(self):
        if self._last_end is not None:
            wait = self._last_end + self.turnaround_s - self.clock()
            if wait > 0:
                time.sleep(wait)

    def _instrument(self, slave: int):
        if self._port_down_until is not None:
            if self.clock() < self._port_down_until:
                raise BusUnavailable(f"{self.port} is closed after a failure; "
                                     f"next attempt in {self._port_down_until - self.clock():.1f} s")
            try:
                inst = self._factory(self.port, slave)
            except (serial.SerialException, OSError) as exc:
                self._backoff = min(self._backoff * 2, self._backoff_max)
                self._port_down_until = self.clock() + self._backoff
                raise BusUnavailable(f"{self.port} not reopened: {exc}; next attempt in {self._backoff:.0f} s") from exc
            self._port_down_until, self._backoff = None, self._backoff_min
            self._stats["reopens"] += 1
            self._instruments = {slave: inst}
            log.info(f"Modbus bus: {self.port} reopened")
            return inst
        inst = self._instruments.get(slave)
        if inst is None:
            try:
                inst = self._instruments[slave] = self._factory(self.port, slave)
            except (serial.SerialException, OSError) as exc:
                self._port_failed(exc)
                raise BusUnavailable(f"{self.port}: {exc}") from exc
        return inst

    def _port_failed(self, exc):
        self._stats["port_errors"] += 1
        self._close_port()
        self._port_down_until = self.clock() + self._backoff
        log.warning(f"Modbus bus: {self.port} failed ({exc}); reopening in {self._backoff:.0f} s")

    def _close_port(self):
        for inst in self._instruments.values():
            try:
                inst.serial.close()
            except Exception:                             # noqa: BLE001 - closing a broken port
                pass
        self._instruments = {}
