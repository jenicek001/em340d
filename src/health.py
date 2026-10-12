#!/usr/bin/env python
"""The daemon's health (#12, step 4).

The main loop writes the ModbusBus's counters and the age of its last successful transaction to HEALTH_FILE
after every cycle. `python src/health.py` - the container's healthcheck - exits 0 only when the file is fresh
and the meter has answered within MAX_SUCCESS_AGE_S. Before, the healthcheck only checked that the Python
modules import, so a meter that stopped answering left the container "healthy".
"""
import json
import os
import sys
import time

HEALTH_FILE = os.getenv('HEALTH_FILE', '/tmp/em340d.health')
MAX_FILE_AGE_S = 60.0          # the loop writes it every POLLING_INTERVAL_S (10 s)
MAX_SUCCESS_AGE_S = 60.0       # the meter answered within this


def write(path, bus, now=None):
    """Atomically: the bus's stats, the age of its last success, the time written."""
    status = {'ts': now if now is not None else time.time(), 'last_success_age_s': bus.last_success_age(),
              **bus.stats()}
    tmp = f'{path}.tmp'
    with open(tmp, 'w') as f:
        json.dump(status, f)
    os.replace(tmp, path)


def check(path, now=None):
    """(healthy, reason)."""
    now = now if now is not None else time.time()
    try:
        with open(path) as f:
            status = json.load(f)
    except (OSError, ValueError):
        return False, 'no health file yet'
    if now - status.get('ts', 0) > MAX_FILE_AGE_S:
        return False, f'the main loop has not written its health for {now - status.get("ts", 0):.0f} s'
    age = status.get('last_success_age_s')
    if age is None:
        return False, 'the meter has not answered since the start'
    if age > MAX_SUCCESS_AGE_S:
        return False, f'the meter last answered {age:.0f} s ago (port open: {status.get("port_open")})'
    return True, f'ok: last answer {age:.1f} s ago, {status.get("ok")} ok, {status.get("retries")} retries'


if __name__ == '__main__':
    healthy, reason = check(HEALTH_FILE)
    print(reason)
    sys.exit(0 if healthy else 1)
