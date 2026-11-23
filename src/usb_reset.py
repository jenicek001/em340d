"""Reset the USB device behind a serial port, the same as re-plugging it (recovery.py).

The port (`/dev/ttyUSB0`, or its `/dev/serial/by-id/...` link) is resolved through sysfs to its USB device's bus and
device number, and the kernel's USBDEVFS_RESET is issued on `/dev/bus/usb/<bus>/<dev>`. That needs the container to
see /dev and to be allowed to write USB devices: em340d's compose file runs it privileged with /dev mounted."""
import fcntl
import os
from typing import Callable, Optional

USBDEVFS_RESET = (ord('U') << 8) | 20      # _IO('U', 20)


def usb_node(port: str, sys_root: str = '/sys') -> Optional[str]:
    """/dev/bus/usb/BBB/DDD of the USB device behind `port`; None when it is not a USB port."""
    name = os.path.basename(os.path.realpath(port))
    link = os.path.join(sys_root, 'class', 'tty', name, 'device')
    if not os.path.exists(link):
        return None
    path = os.path.realpath(link)
    top = os.path.realpath(sys_root)
    while path.startswith(top) and path != top:
        busnum, devnum = os.path.join(path, 'busnum'), os.path.join(path, 'devnum')
        if os.path.exists(busnum) and os.path.exists(devnum):
            with open(busnum) as b, open(devnum) as d:
                return f'/dev/bus/usb/{int(b.read()):03d}/{int(d.read()):03d}'
        path = os.path.dirname(path)
    return None


def _ioctl(path: str, request: int) -> None:
    fd = os.open(path, os.O_WRONLY)
    try:
        fcntl.ioctl(fd, request, 0)
    finally:
        os.close(fd)


def reset(port: str, sys_root: str = '/sys', ioctl: Callable[[str, int], None] = _ioctl) -> str:
    """Reset the adapter behind `port`; its USB node. OSError when it cannot be found or reset."""
    node = usb_node(port, sys_root)
    if node is None:
        raise OSError(f'{port}: no USB device found behind it')
    ioctl(node, USBDEVFS_RESET)
    return node
