"""#17 interim fix: the configuration service writes into the EM340's own registers, so a wrong or accidental
write changes what the billing meter counts. The register map follows the EM340 protocol (CP v2 rev 17), writes
are off unless em340d's own environment enables them, and the metering-relevant parameters need the meter's
serial number repeated in the payload (owner 2026-10-19)."""
import json
import unittest.mock as mock

import pytest

from modbus_bus import ModbusBus
from tests.modbus_sim import SimBus

SERIAL = "036245X"


def manager(write_enabled=True):
    sim = SimBus(turnaround_s=0.01)
    sim.slave(1, {0x1000: 0, 0x1002: 0, 0x1100: 0, 0x1101: 0, 0x1102: 0, 0x1103: 1, 0x1104: 0, 0x1200: 0, 0x1201: 1})
    bus = ModbusBus("/dev/sim", turnaround_s=0.01, instrument_factory=sim.instrument)
    bus.start()
    with mock.patch("paho.mqtt.client.Client"):
        from em340_config_manager import EM340ConfigManager
        cm = EM340ConfigManager({"topic": "em340", "device_id": SERIAL, "write_enabled": write_enabled}, bus, 1)
    cm.config_mqtt_client = mock.MagicMock()
    return sim, bus, cm


@pytest.fixture
def em():
    sim, bus, cm = manager()
    yield sim, bus, cm
    bus.stop()


def statuses(cm):
    out = []
    for c in cm.config_mqtt_client.publish.call_args_list:
        if c.args[0].endswith("/status"):
            out.append(json.loads(c.args[1]))
    return out


def writes(sim):
    return [e for e in sim.log if e[1] == "write"]


def test_the_register_map_is_the_em340s():
    from em340_config_manager import EM340ConfigManager as M
    regs = M.CONFIG_REGISTERS
    assert not any(p.startswith(("pt_", "ct_")) for p in regs)         # the EM340 has no CT/VT ratio
    assert regs["display_mode"]["address"] == 0x1100                   # was 0x1101, on top of tariff enabling
    assert regs["tariff_enabling"]["address"] == 0x1101
    addresses = [r["address"] for r in regs.values()]
    assert len(addresses) == len(set(addresses))
    assert not ({0x1200, 0x1201} & set(addresses)) or all(
        r["description"].lower().startswith("tariff") for r in regs.values() if r["address"] in (0x1200, 0x1201))
    for name in ("measuring_system", "measurement_mode", "password"):
        assert regs[name]["critical"] is True
    for r in regs.values():                                            # every writable one has its range
        if r.get("writable"):
            assert r.get("min_value") is not None and r.get("max_value") is not None


def test_writes_are_off_unless_em340d_enables_them():
    sim, bus, cm = manager(write_enabled=False)
    try:
        cm.handle_parameter_set("display_mode", "1")
        assert writes(sim) == [] and "writes disabled" in statuses(cm)[-1]["status"]
    finally:
        bus.stop()


def test_writes_are_off_by_default_from_the_environment(monkeypatch):
    monkeypatch.delenv("CONFIG_WRITE_ENABLED", raising=False)
    from em340_config_manager import write_enabled_from_env
    assert write_enabled_from_env() is False
    monkeypatch.setenv("CONFIG_WRITE_ENABLED", "true")
    assert write_enabled_from_env() is True


def test_a_critical_parameter_needs_the_serial_number_in_the_payload(em):
    sim, bus, cm = em
    for payload in ("0", '{"value": 0}', '{"value": 0, "serial": "123456X"}'):
        cm.handle_parameter_set("measurement_mode", payload)
        assert sim.registers[1][0x1103] == 1 and "serial" in statuses(cm)[-1]["status"]
    cm.handle_parameter_set("measurement_mode", json.dumps({"value": 0, "serial": SERIAL}))
    assert sim.registers[1][0x1103] == 0 and statuses(cm)[-1]["status"] == "success"


def test_a_non_critical_parameter_takes_a_plain_value(em):
    sim, bus, cm = em
    cm.handle_parameter_set("display_mode", "1")
    assert sim.registers[1][0x1100] == 1 and sim.registers[1][0x1101] == 0   # tariff enabling untouched
    cm.handle_parameter_set("home_page_selection", '{"value": 3}')
    assert sim.registers[1][0x1102] == 3


def test_out_of_range_is_refused_without_writing(em):
    sim, bus, cm = em
    cm.handle_parameter_set("display_mode", "7")
    assert writes(sim) == [] and "above maximum" in statuses(cm)[-1]["status"]


def test_batch_set_is_routed_and_checks_each_parameter(em):
    sim, bus, cm = em
    msg = mock.MagicMock(topic="em340/036245X/config/batch/set",
                         payload=json.dumps({"display_mode": 1, "measurement_mode": 0}).encode())
    cm.on_config_mqtt_message(None, None, msg)
    assert sim.registers[1][0x1100] == 1                                # applied
    assert sim.registers[1][0x1103] == 1                                # critical, no serial: refused
    msg.payload = json.dumps({"measurement_mode": 0, "serial": SERIAL}).encode()
    cm.on_config_mqtt_message(None, None, msg)
    assert sim.registers[1][0x1103] == 0


def test_restore_writes_critical_parameters_only_with_the_serial(em):
    sim, bus, cm = em
    backup = {"display_mode": {"value": 1}, "measurement_mode": {"value": 0}, "_metadata": {"device_id": SERIAL}}
    cm.handle_restore(json.dumps(backup))
    assert sim.registers[1][0x1100] == 1 and sim.registers[1][0x1103] == 1
    cm.handle_restore(json.dumps({**backup, "serial": SERIAL}))
    assert sim.registers[1][0x1103] == 0


def test_factory_reset_is_gone(em):
    sim, bus, cm = em
    msg = mock.MagicMock(topic="em340/036245X/config/reset", payload=b"")
    cm.on_config_mqtt_message(None, None, msg)
    assert writes(sim) == []                                            # it would have set measurement mode A
