"""#8 and #12 step 3: the configuration service uses the ModbusBus - its commands arrive on the MQTT thread
and wait their turn instead of interleaving with the poll on the RS-485 bus."""
import threading
import unittest.mock as mock

import pytest

from modbus_bus import ModbusBus
from tests.modbus_sim import SimBus


@pytest.fixture
def setup():
    sim = SimBus(turnaround_s=0.01)
    sim.slave(1, {0x1103: 1, 0x1101: 5, 0x0000: 2301})
    bus = ModbusBus("/dev/sim", turnaround_s=0.01, instrument_factory=sim.instrument)
    bus.start()
    with mock.patch("paho.mqtt.client.Client"):
        from em340_config_manager import EM340ConfigManager
        cm = EM340ConfigManager({"topic": "em340", "device_id": "036245X"}, bus, 1)
    cm.config_mqtt_client = mock.MagicMock()
    yield sim, bus, cm
    bus.stop()


def published(cm):
    return [(c.args[0], c.args[1]) for c in cm.config_mqtt_client.publish.call_args_list]


def test_get_reads_through_the_bus(setup):
    sim, bus, cm = setup
    cm.handle_parameter_get("measurement_mode")
    assert any("measurement_mode" in t and '"value": 1' in p for t, p in published(cm))
    assert sim.log[-1][:4] == (1, "read", 0x1103, 1)


def test_set_writes_and_verifies_through_the_bus(setup):
    sim, bus, cm = setup
    cm.handle_parameter_set("measurement_mode", "0")
    assert sim.registers[1][0x1103] == 0
    assert [e[1] for e in sim.log[-2:]] == ["write", "read"]
    assert any('"success"' in p for _, p in published(cm))


def test_a_set_during_a_busy_poll_never_overlaps_it(setup):
    sim, bus, cm = setup
    stop = threading.Event()

    def poll():
        while not stop.is_set():
            bus.read_registers(1, 0x0000, 1)
    t = threading.Thread(target=poll)
    t.start()
    for v in ("0", "1", "0"):                    # (patching time.sleep would also stop the bus's own wait)
        cm.handle_parameter_set("measurement_mode", v)
    stop.set()
    t.join(5)
    assert sim.overlaps == 0 and sim.turnaround_violations == 0
    assert sim.registers[1][0x1103] == 0


def test_backup_reads_every_parameter_through_the_bus(setup):
    sim, bus, cm = setup
    cm.handle_backup()
    reads = {e[2] for e in sim.log if e[1] == "read"}
    assert {0x1103, 0x1101} <= reads and sim.turnaround_violations == 0
