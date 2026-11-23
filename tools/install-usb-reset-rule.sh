#!/bin/sh
# Install the udev rule that lets em340d reset its USB-RS485 adapter (README, Self-recovery). Run once per host.
set -e
here=$(dirname "$0")
sudo install -m 644 "$here/99-em340d-usb-reset.rules" /etc/udev/rules.d/99-em340d-usb-reset.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --action=change
sudo udevadm settle
echo "Installed. USB devices in group dialout:"
ls -l /dev/bus/usb/*/* | grep dialout || echo "  none: is the adapter's chip in the rule? (lsusb)"
