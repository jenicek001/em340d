"""A simulated RS-485 bus for ModbusBus tests (#12): slaves with registers, the EM340's behaviour seen on
2026-10-12 (a request inside the turnaround gets no answer), injected faults, and a detector for two
transactions that overlap.

    sim = SimBus(turnaround_s=0.02)
    sim.slave(1, {0x0400: 3180, ...})
    bus = ModbusBus("/dev/sim", turnaround_s=0.02, instrument_factory=sim.instrument)
"""
import threading
import time

import minimalmodbus
import serial


class SimBus:
    def __init__(self, turnaround_s=0.02, transaction_s=0.002, clock=time.monotonic):
        self.turnaround_s, self.transaction_s, self.clock = turnaround_s, transaction_s, clock
        self.registers = {}                  # slave -> {address: value}
        self.faults = []                     # queued: "no_answer", "invalid", "port_lost", "illegal"
        self.port_ok = True
        self.opened = 0
        self.log = []                        # (slave, op, address, count, start, end, outcome)
        self.overlaps = 0
        self.turnaround_violations = 0
        self._busy = threading.Lock()
        self._last_end = None

    def slave(self, address, registers):
        self.registers[address] = dict(registers)

    def instrument(self, port, slave):
        """The factory ModbusBus calls: one 'instrument' per slave address."""
        if not self.port_ok:
            raise serial.SerialException(f"could not open port {port}")
        self.opened += 1
        return SimInstrument(self, slave)

    def _transaction(self, slave, op, address, count, fn):
        if not self._busy.acquire(blocking=False):
            self.overlaps += 1
            raise AssertionError("two Modbus transactions overlap on the bus")
        start = self.clock()
        outcome = "ok"
        try:
            if not self.port_ok:
                outcome = "port_lost"
                raise serial.SerialException("device reports readiness to read but returned no data")
            if self._last_end is not None and start - self._last_end < self.turnaround_s:
                self.turnaround_violations += 1
                outcome = "turnaround"
                raise minimalmodbus.NoResponseError("No communication with the instrument (no answer)")
            if self.faults:
                fault = self.faults.pop(0)
                outcome = fault
                if fault == "no_answer":
                    raise minimalmodbus.NoResponseError("No communication with the instrument (no answer)")
                if fault == "invalid":
                    raise minimalmodbus.InvalidResponseError("CRC error")
                if fault == "illegal":
                    raise minimalmodbus.IllegalRequestError("Slave reported illegal data address")
                if fault == "port_lost":
                    self.port_ok = False
                    raise serial.SerialException("device disconnected")
            time.sleep(self.transaction_s)
            return fn(self.registers.setdefault(slave, {}))
        finally:
            end = self.clock()
            self._last_end = end
            self.log.append((slave, op, address, count, start, end, outcome))
            self._busy.release()


class SimInstrument:
    def __init__(self, sim, slave):
        self.sim, self.slave = sim, slave
        self.serial = self

    def close(self):
        pass

    def read_registers(self, registeraddress, number_of_registers, functioncode=3):
        return self.sim._transaction(self.slave, "read", registeraddress, number_of_registers,
                                     lambda regs: [regs.get(registeraddress + i, 0) for i in range(number_of_registers)])

    def read_register(self, registeraddress, number_of_decimals=0, functioncode=3, signed=False):
        return self.sim._transaction(self.slave, "read", registeraddress, 1, lambda regs: regs.get(registeraddress, 0))

    def write_register(self, registeraddress, value, number_of_decimals=0, functioncode=6, signed=False):
        def write(regs):
            regs[registeraddress] = value
        return self.sim._transaction(self.slave, "write", registeraddress, 1, write)
