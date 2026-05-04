from __future__ import annotations

from loome._internal.endpoints import endpoint_label, is_local_segment, segment_fingerprint
from loome._internal.shields import segment_shield_for_endpoint, segments_for_shield
from loome.model import Component, Connector, GroundSymbol, Pin, Shield
from loome.ports import RS232


class _Box(Component):
    class J1(Connector):
        pwr = Pin(1, "Power")
        gnd = Pin(2, "Ground")


class _Serial(Component):
    class J1(Connector):
        serial = RS232(1, 2, 3, name="SER")


def test_endpoint_labels_and_fingerprints_are_shared_primitives():
    a = _Box("A")
    gnd = GroundSymbol("GND")
    seg = a.J1.gnd.connect(gnd)

    assert endpoint_label(a.J1.gnd) == "A.J1.Ground"
    assert endpoint_label(gnd) == "GND"
    assert segment_fingerprint(seg) == "A[J1.2] <-> GroundSymbol[GND]"

    seg.end_a, seg.end_b = seg.end_b, seg.end_a
    assert segment_fingerprint(seg) == "A[J1.2] <-> GroundSymbol[GND]"


def test_local_segment_detection_covers_layout_only_wires():
    a = _Box("A")
    a.J1.gnd.local_ground()

    [seg] = a.J1.gnd._connections
    assert is_local_segment(seg)


def test_port_segments_store_endpoint_side_shields():
    a = _Serial("A")
    b = _Serial("B")

    a.J1.serial.connect(b.J1.serial)

    seg = a.J1.serial.tx._connections[0]
    assert seg.end_a_shield_group is a.J1.serial._sg
    assert seg.end_b_shield_group is b.J1.serial._sg
    assert segment_shield_for_endpoint(seg, a.J1.serial.tx) is a.J1.serial._sg
    assert segment_shield_for_endpoint(seg, b.J1.serial.rx) is b.J1.serial._sg


def test_port_shield_membership_reports_one_physical_cable_owner():
    a = _Serial("A")
    b = _Serial("B")

    a.J1.serial.connect(b.J1.serial)

    local_members = segments_for_shield(a.J1.serial._sg, a.J1.serial.tx._connections + a.J1.serial.rx._connections)
    remote_members = segments_for_shield(b.J1.serial._sg, a.J1.serial.tx._connections + a.J1.serial.rx._connections)

    assert len(local_members) == 2
    assert remote_members == []


def test_connection_level_shield_overrides_endpoint_side_port_shields():
    a = _Serial("A")
    b = _Serial("B")

    with Shield() as shield:
        seg = a.J1.serial.tx.connect(b.J1.serial.rx)

    assert seg.end_a_shield_group is a.J1.serial._sg
    assert seg.end_b_shield_group is b.J1.serial._sg
    assert segment_shield_for_endpoint(seg, a.J1.serial.tx) is shield.group
    assert segment_shield_for_endpoint(seg, b.J1.serial.rx) is shield.group
    assert segments_for_shield(shield.group, [seg]) == [seg]


def test_port_descriptor_rebind_updates_existing_segment_endpoint_shields():
    a = _Serial("A")
    b = _Serial("B")

    seg = a.J1.serial_tx.connect(b.J1.serial_rx)
    initial_a_sg = seg.end_a_shield_group
    initial_b_sg = seg.end_b_shield_group
    a_port = a.J1.serial
    b_port = b.J1.serial

    assert initial_a_sg is not a_port._sg
    assert initial_b_sg is not b_port._sg
    assert seg.end_a_shield_group is a_port._sg
    assert seg.end_b_shield_group is b_port._sg
    assert segment_shield_for_endpoint(seg, a_port.tx) is a_port._sg
    assert segment_shield_for_endpoint(seg, b_port.rx) is b_port._sg
