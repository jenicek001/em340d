"""Self-recovery from a silent bus (owner 2026-11-22).

2026-11-19 the meter stopped answering behind a working adapter for hours, and only a reboot brought it back: the
USB-RS485 adapter had hung, which reopening its port does not cure. While the meter is offline because nothing answers
(`no_answer`), or because the adapter's port fails while its device file is still there (`adapter`), em340d:

1. after REOPEN_AFTER_S reopens the port (a port left in a bad state);
2. after USB_RESET_AFTER_S resets the adapter on the USB bus, the same as re-plugging it (a hung adapter), and again
   every USB_RESET_EVERY_S while the meter stays silent: a dead meter, or a cut RS485 cable, is not cured by it, and
   an hourly reset costs nothing.

A missing adapter (unplugged), garbled answers or a meter refusing a request are not cured this way and are left to
a hand. When the meter answers again, `recovered_by` names the step that cured it (None: it came back by itself), so
afterwards a hung adapter is told from a meter that was off. These are em340d's own mechanics, the same everywhere.
"""
import time
from typing import Callable, Optional

from logger import log

REOPEN_AFTER_S = 60.0              # silent this long: reopen the port
USB_RESET_AFTER_S = 180.0          # still silent: reset the adapter on the USB bus
USB_RESET_EVERY_S = 3600.0         # and again at most this often while it stays silent
CURABLE = ("no_answer", "adapter")


class Recovery:
    def __init__(self, reopen: Callable[[], None], usb_reset: Callable[[], None],
                 clock: Callable[[], float] = time.monotonic):
        self._reopen, self._usb_reset, self.clock = reopen, usb_reset, clock
        self.recovered_by: Optional[str] = None    # the step that cured the last outage
        self.counts = {"reopen": 0, "usb_reset": 0, "usb_reset_failed": 0}
        self._clear()

    def _clear(self):
        self.since: Optional[float] = None
        self.last_action: Optional[str] = None
        self._reopened = False
        self._last_reset: Optional[float] = None

    def update(self, fault: Optional[str], port_exists: bool) -> Optional[str]:
        """Called after every poll with the meter's fault (None: online). Returns the step taken now, if any."""
        if fault is None:
            if self.since is not None:
                self.recovered_by = self.last_action if self.last_action in ("reopen", "usb_reset") else None
                if self.recovered_by:
                    log.info(f'Meter answers again after the {self.recovered_by}: '
                             f'{"the adapter had hung" if self.recovered_by == "usb_reset" else "the port was stuck"}')
            self._clear()
            return None
        if fault not in CURABLE or not port_exists:
            self._clear()
            return None
        now = self.clock()
        if self.since is None:
            self.since, self.recovered_by = now, None
        silent = now - self.since
        if not self._reopened and silent >= REOPEN_AFTER_S:
            self._reopened = True
            log.warning(f'Meter silent for {silent:.0f} s ({fault}): reopening the serial port')
            return self._did('reopen', self._reopen)
        if silent >= USB_RESET_AFTER_S and (self._last_reset is None or now - self._last_reset >= USB_RESET_EVERY_S):
            self._last_reset = now
            log.warning(f'Meter silent for {silent:.0f} s ({fault}): resetting the USB-RS485 adapter')
            return self._did('usb_reset', self._usb_reset)
        return None

    def _did(self, step, fn) -> str:
        try:
            fn()
        except Exception as err:                       # noqa: BLE001 - not privileged, no such device: try later
            log.error(f'{step} failed: {err}')
            step = f'{step}_failed' if step == 'usb_reset' else step
        self.counts[step] = self.counts.get(step, 0) + 1
        self.last_action = step
        return step
