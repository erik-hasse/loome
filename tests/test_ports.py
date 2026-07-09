from __future__ import annotations

import pytest

from loome.model import Component, Connector, GroundSymbol, Pin
from loome.ports import ARINC429, GPIO, HSDB, RS232, DifferentialPair, Thermocouple


class _ARINCDevice(Component):
    class J1(Connector):
        tx = ARINC429(1, 2, "out", name="TX")
        rx = ARINC429(3, 4, "in", name="RX")


class _HSDBDevice(Component):
    class J1(Connector):
        hsdb = HSDB(1, 2, 3, 4, name="HSDB")


class _DifferentialPairDevice(Component):
    class J1(Connector):
        pair = DifferentialPair(1, 2, name="RS-485/422 1")


class _SerialDevice(Component):
    class J1(Connector):
        serial = RS232(1, 2, 3, name="SER")


class _GPIOReader(Component):
    class J1(Connector):
        gp = GPIO(1, 2, 3, name="GP")


class _GPIOSensor(Component):
    output = GPIO("R", "W", "B", name="Out")


class _ThermocoupleDevice(Component):
    class J1(Connector):
        tc = Thermocouple(1, 2, name="EGT", gauge=20)


def test_arinc429_direction_mismatch_raises_immediately():
    a = _ARINCDevice()
    b = _ARINCDevice()
    with pytest.raises(ValueError, match="both are 'out'"):
        a.J1.tx >> b.J1.tx


def test_arinc429_direction_mismatch_in_raises_immediately():
    a = _ARINCDevice()
    b = _ARINCDevice()
    with pytest.raises(ValueError, match="both are 'in'"):
        a.J1.rx >> b.J1.rx


def test_arinc429_valid_connection_succeeds():
    a = _ARINCDevice()
    b = _ARINCDevice()
    a.J1.tx >> b.J1.rx  # should not raise


def test_differential_pair_connects_a_to_a_and_b_to_b():
    a = _DifferentialPairDevice("A")
    b = _DifferentialPairDevice("B")

    a.J1.pair >> b.J1.pair

    assert a.J1.pair.a._connections[0].end_b is b.J1.pair.a
    assert a.J1.pair.b._connections[0].end_b is b.J1.pair.b
    assert [pin._connections[0].port_order for pin in a.J1.pair._inner_pins()] == [0, 1]


def test_differential_pair_uses_one_shield_group_for_both_wires():
    a = _DifferentialPairDevice("A")
    b = _DifferentialPairDevice("B")

    a.J1.pair >> b.J1.pair

    local_group = a.J1.pair._sg
    remote_group = b.J1.pair._sg
    assert local_group.pins == a.J1.pair._inner_pins()
    assert remote_group.pins == b.J1.pair._inner_pins()
    assert all(pin.shield_group is local_group for pin in a.J1.pair._inner_pins())
    assert all(pin.shield_group is remote_group for pin in b.J1.pair._inner_pins())
    assert all(seg.end_a_shield_group is local_group for pin in local_group.pins for seg in pin._connections)


def test_hsdb_cross_connects_both_differential_pairs():
    a = _HSDBDevice("A")
    b = _HSDBDevice("B")

    a.J1.hsdb >> b.J1.hsdb

    assert a.J1.hsdb.tx_a._connections[0].end_b is b.J1.hsdb.rx_a
    assert a.J1.hsdb.tx_b._connections[0].end_b is b.J1.hsdb.rx_b
    assert a.J1.hsdb.rx_a._connections[0].end_b is b.J1.hsdb.tx_a
    assert a.J1.hsdb.rx_b._connections[0].end_b is b.J1.hsdb.tx_b
    assert [pin._connections[0].port_order for pin in a.J1.hsdb._inner_pins()] == [0, 1, 2, 3]


def test_hsdb_uses_one_shield_group_for_all_four_wires():
    a = _HSDBDevice("A")
    b = _HSDBDevice("B")

    a.J1.hsdb >> b.J1.hsdb

    local_group = a.J1.hsdb._sg
    remote_group = b.J1.hsdb._sg
    assert local_group.pins == a.J1.hsdb._inner_pins()
    assert remote_group.pins == b.J1.hsdb._inner_pins()
    assert all(pin.shield_group is local_group for pin in a.J1.hsdb._inner_pins())
    assert all(pin.shield_group is remote_group for pin in b.J1.hsdb._inner_pins())
    assert all(seg.end_a_shield_group is local_group for pin in local_group.pins for seg in pin._connections)


def test_port_builder_modifiers_apply_to_every_created_segment():
    a = _SerialDevice("A")
    b = _SerialDevice("B")

    (a.J1.serial >> b.J1.serial).gauge(20).color("BL").system("COM")

    segments = {
        id(seg): seg for pin in (a.J1.serial.tx, a.J1.serial.rx, a.J1.serial.gnd) for seg in pin._connections
    }.values()
    assert len(segments) == 3
    assert {seg.gauge for seg in segments} == {20}
    assert {seg.color for seg in segments} == {"BL"}
    assert {seg.system for seg in segments} == {"COM"}


def test_port_builder_ground_false_removes_ground_segment_before_other_modifiers():
    a = _SerialDevice("A")
    b = _SerialDevice("B")

    (a.J1.serial >> b.J1.serial).ground(False).gauge(20)

    assert a.J1.serial.gnd is not None
    assert b.J1.serial.gnd is not None
    assert a.J1.serial.gnd._connections == []
    assert b.J1.serial.gnd._connections == []
    segments = {id(seg): seg for pin in (a.J1.serial.tx, a.J1.serial.rx) for seg in pin._connections}.values()
    assert len(segments) == 2
    assert {seg.gauge for seg in segments} == {20}


def test_port_descriptor_injects_inner_pins_and_binds_instance_access():
    dev = _SerialDevice("A")

    assert isinstance(_SerialDevice.J1.serial_tx, Pin)
    assert isinstance(_SerialDevice.J1.serial_rx, Pin)
    assert isinstance(_SerialDevice.J1.serial_gnd, Pin)
    assert dev.J1.serial.tx is dev.J1.serial_tx
    assert dev.J1.serial.rx is dev.J1.serial_rx
    assert dev.J1.serial.gnd is dev.J1.serial_gnd
    assert dev.J1.serial.tx._component is dev
    assert dev.J1.serial.tx._connector is dev.J1


def test_rs232_connect_cross_wires_tx_rx_and_orders_ground_last():
    a = _SerialDevice("A")
    b = _SerialDevice("B")

    a.J1.serial.connect(b.J1.serial)

    tx_seg = a.J1.serial.tx._connections[0]
    rx_seg = a.J1.serial.rx._connections[0]
    gnd_seg = a.J1.serial.gnd._connections[0]
    assert tx_seg.end_a is a.J1.serial.tx
    assert tx_seg.end_b is b.J1.serial.rx
    assert tx_seg.port_order == 0
    assert rx_seg.end_a is a.J1.serial.rx
    assert rx_seg.end_b is b.J1.serial.tx
    assert rx_seg.port_order == 1
    assert gnd_seg.end_a is a.J1.serial.gnd
    assert gnd_seg.end_b is b.J1.serial.gnd
    assert gnd_seg.port_order == 2


def test_gpio_connect_matches_pins_by_role():
    reader = _GPIOReader("Reader")
    sensor = _GPIOSensor("Sensor")

    reader.J1.gp.connect(sensor.output)

    assert reader.J1.gp.positive._connections[0].end_b is sensor.output.positive
    assert reader.J1.gp.signal._connections[0].end_b is sensor.output.signal
    assert reader.J1.gp.ground._connections[0].end_b is sensor.output.ground


def test_thermocouple_defaults_to_twenty_gauge_yellow_and_red_pair():
    a = _ThermocoupleDevice("A")
    b = _ThermocoupleDevice("B")

    a.J1.tc >> b.J1.tc

    high_seg = a.J1.tc._high._connections[0]
    low_seg = a.J1.tc._low._connections[0]
    assert (high_seg.gauge, high_seg.color, high_seg.end_b) == (20, "Y", b.J1.tc._high)
    assert (low_seg.gauge, low_seg.color, low_seg.end_b) == (20, "R", b.J1.tc._low)


def test_port_builder_drain_modifiers_update_local_and_remote_shield_groups():
    a = _SerialDevice("A")
    b = _SerialDevice("B")
    local_gnd = GroundSymbol("LOCAL")
    remote_gnd = GroundSymbol("REMOTE")

    (a.J1.serial >> b.J1.serial).drain(local_gnd).drain_remote(remote_gnd)

    assert a.J1.serial._sg.drain is local_gnd
    assert b.J1.serial._sg.drain_remote is local_gnd
    assert a.J1.serial._sg.drain_remote is remote_gnd
    assert b.J1.serial._sg.drain is remote_gnd


def test_port_builder_notes_currently_annotates_only_primary_segment():
    a = _SerialDevice("A")
    b = _SerialDevice("B")

    (a.J1.serial >> b.J1.serial).notes("Configured")

    assert a.J1.serial.rx._connections[0].notes == "Configured"
    assert a.J1.serial.tx._connections[0].notes == ""
    assert a.J1.serial.gnd._connections[0].notes == ""
