"""Self-recovery from a silent bus (owner 2026-11-22).

2026-11-19 the meter stopped answering behind a working adapter for hours, and a reboot of the computer brought it
back: the adapter had hung, which reopening its port does not cure. When the meter is offline with nothing answering
(or the adapter's port failing while it is still there), em340d first reopens the port, then resets the adapter on
the USB bus, the same as re-plugging it, at most once an hour while it stays silent. Which step brought the meter back
is published, so a hung adapter is told from a dead meter afterwards. A simulated bus and sysfs, no USB."""
import json
import os

import pytest

import em340
import usb_reset
from modbus_bus import ModbusBus
from recovery import REOPEN_AFTER_S, USB_RESET_AFTER_S, USB_RESET_EVERY_S, Recovery
from tests.modbus_sim import SimBus
from tests.test_em340_snapshots import at, daemon  # noqa: F401 - the fixture


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def recovery():
    done = []
    clock = Clock()
    r = Recovery(reopen=lambda: done.append("reopen"), usb_reset=lambda: done.append("usb_reset"), clock=clock)
    return r, done, clock


def test_a_silent_bus_is_reopened_then_the_adapter_reset_then_reset_hourly():
    r, done, clock = recovery()
    assert r.update("no_answer", port_exists=True) is None
    clock.t += REOPEN_AFTER_S - 1
    assert r.update("no_answer", True) is None
    clock.t += 1
    assert r.update("no_answer", True) == "reopen"
    clock.t += 1
    assert r.update("no_answer", True) is None                         # reopened once
    clock.t = 1000.0 + USB_RESET_AFTER_S
    assert r.update("no_answer", True) == "usb_reset"
    clock.t += USB_RESET_EVERY_S - 1
    assert r.update("no_answer", True) is None
    clock.t += 1
    assert r.update("no_answer", True) == "usb_reset"
    assert done == ["reopen", "usb_reset", "usb_reset"]


def test_a_failing_port_that_is_still_there_is_reset_too_but_not_a_missing_one():
    r, done, clock = recovery()
    r.update("adapter", True)
    clock.t += USB_RESET_AFTER_S
    assert r.update("adapter", True) == "reopen"
    assert r.update("adapter", True) == "usb_reset"
    r2, done2, clock2 = recovery()
    r2.update("adapter", False)                                        # unplugged: nothing to reset, a hand is needed
    clock2.t += 10 * USB_RESET_AFTER_S
    assert r2.update("adapter", False) is None and done2 == []


def test_garbled_answers_or_a_refusing_meter_are_not_cured_by_a_reset():
    r, done, clock = recovery()
    for fault in ("invalid", "meter_error"):
        r.update(fault, True)
        clock.t += 10 * USB_RESET_AFTER_S
        assert r.update(fault, True) is None
    assert done == []


def test_the_meter_answering_again_names_the_step_that_cured_it_and_starts_over():
    r, done, clock = recovery()
    r.update("no_answer", True)
    clock.t += USB_RESET_AFTER_S
    r.update("no_answer", True)
    r.update("no_answer", True)
    assert r.update(None, True) is None and r.recovered_by == "usb_reset"
    clock.t += 1
    r.update("no_answer", True)                                        # a new outage: the clock starts again
    clock.t += REOPEN_AFTER_S - 1
    assert r.update("no_answer", True) is None


def test_recovered_by_nothing_when_it_came_back_by_itself():
    r, _, clock = recovery()
    r.update("no_answer", True)
    clock.t += 5
    r.update(None, True)
    assert r.recovered_by is None


def test_a_failed_reset_is_logged_and_tried_again_an_hour_later():
    clock = Clock()

    def boom():
        raise PermissionError("not privileged")
    r = Recovery(reopen=lambda: None, usb_reset=boom, clock=clock)
    r.update("no_answer", True)
    clock.t += USB_RESET_AFTER_S
    r.update("no_answer", True)
    assert r.update("no_answer", True) == "usb_reset_failed"
    clock.t += 60
    assert r.update("no_answer", True) is None


# --- the USB device behind a serial port -------------------------------------------------------------------------

def fake_sysfs(tmp_path, tty="ttyUSB0", bus=1, dev=5):
    """/sys/class/tty/<tty>/device -> .../1-1.3/1-1.3:1.0/<tty>, the USB device (busnum, devnum) two levels up."""
    usb = tmp_path / "sys/devices/platform/usb1/1-1/1-1.3"
    port = usb / "1-1.3:1.0" / tty
    port.mkdir(parents=True)
    (usb / "busnum").write_text(f"{bus}\n")
    (usb / "devnum").write_text(f"{dev}\n")
    (tmp_path / "sys/class/tty" / tty).mkdir(parents=True)
    os.symlink(port, tmp_path / "sys/class/tty" / tty / "device")
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / tty).write_text("")
    os.makedirs(tmp_path / "dev/serial/by-id")
    os.symlink(tmp_path / "dev" / tty, tmp_path / "dev/serial/by-id/usb-1a86_USB_Serial-if00-port0")
    return tmp_path


def test_the_usb_device_node_is_found_from_the_port_by_id_or_by_name(tmp_path):
    root = fake_sysfs(tmp_path)
    by_id = str(root / "dev/serial/by-id/usb-1a86_USB_Serial-if00-port0")
    assert usb_reset.usb_node(by_id, sys_root=str(root / "sys")) == "/dev/bus/usb/001/005"
    assert usb_reset.usb_node(str(root / "dev/ttyUSB0"), sys_root=str(root / "sys")) == "/dev/bus/usb/001/005"
    assert usb_reset.usb_node(str(root / "dev/ttyS0"), sys_root=str(root / "sys")) is None     # not a USB port


def test_the_reset_is_the_kernels_usb_reset_on_that_node(tmp_path):
    root = fake_sysfs(tmp_path)
    calls = []
    node = usb_reset.reset(str(root / "dev/ttyUSB0"), sys_root=str(root / "sys"),
                           ioctl=lambda path, req: calls.append((path, req)))
    assert node == "/dev/bus/usb/001/005" and calls == [("/dev/bus/usb/001/005", usb_reset.USBDEVFS_RESET)]
    with pytest.raises(OSError):
        usb_reset.reset(str(root / "dev/ttyS0"), sys_root=str(root / "sys"), ioctl=lambda p, r: None)


# --- on the bus and in the daemon --------------------------------------------------------------------------------

def test_the_bus_runs_an_action_with_its_port_closed_between_requests():
    sim = SimBus(turnaround_s=0.01)
    sim.slave(1, {0x0000: 7})
    bus = ModbusBus("/dev/sim", turnaround_s=0.01, instrument_factory=sim.instrument, reopen_backoff=(0.05, 0.2))
    bus.start()
    try:
        assert bus.read_register(1, 0x0000) == 7
        seen = []
        bus.with_port_closed(lambda: seen.append(bus.stats()["port_open"]))
        assert seen == [False]
        assert bus.read_register(1, 0x0000) == 7                       # reopened by the next request
        assert bus.stats()["reopens"] == 1
    finally:
        bus.stop()


def _published(d, suffix):
    return [json.loads(c.args[1]) for c in d.mqtt_client.publish.call_args_list if c.args[0] == f"{d.topic}/{suffix}"]


def test_the_daemon_resets_a_hung_adapter_and_says_so(daemon):  # noqa: F811
    d, sim = daemon(at("2026-10-12 14:14:50"))
    d._port_exists = lambda: True
    clock = Clock()
    resets = []

    def reset():
        resets.append(d.device)
        sim.meter_silent = False                                       # the adapter was the culprit
    d.recovery = Recovery(reopen=d.bus.reopen, usb_reset=reset, clock=clock)
    blocks = em340.build_blocks(d.sensors)
    sim.meter_silent = True
    for _ in range(3):
        d._publish_status(d.poll_once(blocks))
    clock.t += USB_RESET_AFTER_S
    d._publish_status(d.poll_once(blocks))                             # reopen
    d._publish_status(d.poll_once(blocks))                             # USB reset
    fault = _published(d, "fault")[-1]
    assert fault["fault"] == "no_answer" and fault["recovery"] == "usb_reset" and resets == [d.device]
    d._publish_status(d.poll_once(blocks))
    fault = _published(d, "fault")[-1]
    assert fault["fault"] is None and fault["recovered_by"] == "usb_reset"
