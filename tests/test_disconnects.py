from __future__ import annotations

import pytest

from loome import (
    GPIO,
    RS232,
    Bundle,
    CanBus,
    CanBusLine,
    Component,
    Connector,
    Disconnect,
    DisconnectPin,
    Fuse,
    GroundSymbol,
    Harness,
    Pin,
    Shield,
)
from loome.bom import build_bom
from loome.layout.engine import layout


class _A(Component):
    class J1(Connector):
        power = Pin(1, "Power")
        gnd = Pin(2, "Ground")


class _B(Component):
    class J1(Connector):
        power = Pin(1, "Power")
        gnd = Pin(2, "Ground")


class _DT2(Disconnect):
    power = DisconnectPin(1, "Power")
    gnd = DisconnectPin(2, "Ground")


def _two_bundle_setup():
    a = _A("A")
    b = _B("B")
    a.J1.power.connect(b.J1.power)
    a.J1.gnd.connect(b.J1.gnd)
    mate = _DT2("DC1", label="root")
    mate.power.between(a.J1.power, b.J1.power)
    mate.gnd.between(a.J1.gnd, b.J1.gnd)

    wing = Bundle("wing")
    wb_root = wing.breakout("wb_root")
    wb_a = wing.breakout("wb_a", after=wb_root, length=10)
    wb_a.attach(a.J1, leg_length=2)
    wb_root.attach(mate, leg_length=1)

    fus = Bundle("fuselage")
    fb_root = fus.breakout("fb_root")
    fb_b = fus.breakout("fb_b", after=fb_root, length=20)
    fb_b.attach(b.J1, leg_length=3)
    fb_root.attach(mate, leg_length=1)

    h = Harness("t")
    h.add(a, b, mate, wing, fus)
    wing.freeze()
    fus.freeze()
    return h, a, b, mate


def test_disconnect_segments_unchanged_in_count():
    a = _A("A")
    b = _B("B")
    a.J1.power.connect(b.J1.power)
    a.J1.gnd.connect(b.J1.gnd)
    mate = _DT2("DC1")

    h_no_disc = Harness("nd")
    h_no_disc.add(a, b)
    n_before = len(h_no_disc.segments())

    mate.power.between(a.J1.power, b.J1.power)
    mate.gnd.between(a.J1.gnd, b.J1.gnd)

    h = Harness("d")
    h.add(a, b, mate)
    assert len(h.segments()) == n_before


def test_disconnect_pin_between_finds_segment():
    a = _A("A")
    b = _B("B")
    seg = a.J1.power.connect(b.J1.power)
    mate = _DT2("DC1")
    mate.power.between(a.J1.power, b.J1.power)
    h = Harness("t")
    h.add(a, b, mate)
    h.segments()  # triggers lazy resolution
    assert mate.power._segment is seg
    assert seg.disconnect_pin is mate.power


def test_disconnect_pin_between_errors_when_segment_missing():
    a = _A("A")
    b = _B("B")
    mate = _DT2("DC1")
    mate.power.between(a.J1.power, b.J1.power)
    h = Harness("t")
    h.add(a, b, mate)
    with pytest.raises(ValueError, match="no wire segment found"):
        h.segments()


def test_disconnect_can_be_declared_before_wires():
    a = _A("A")
    b = _B("B")
    mate = _DT2("DC1")
    # Bind first, declare wire afterward.
    mate.power.between(a.J1.power, b.J1.power)
    seg = a.J1.power.connect(b.J1.power)
    h = Harness("t")
    h.add(a, b, mate)
    h.segments()
    assert seg.disconnect_pin is mate.power


def test_disconnect_between_port_allocates_one_pin_per_rail():
    class Reader(Component):
        class J1(Connector):
            gp1 = GPIO(18, 19, 20, name="GP1", shielded=False)

    class Sensor(Component):
        output = GPIO("Or", "Gr", "Bl", name="Pos", shielded=False)

    r = Reader("R")
    s = Sensor("S")
    r.J1.gp1.connect(s.output)
    mate = Disconnect("DC1")
    pins = mate.between(r.J1.gp1, s.output)
    assert len(pins) == 3
    assert [p.number for p in pins] == [1, 2, 3]
    h = Harness("t")
    h.add(r, s, mate)
    h.segments()
    # Each segment is bound to one of the allocated disconnect pins.
    bound_ids = {
        id(r.J1.gp1._positive._connections[0].disconnect_pin),
        id(r.J1.gp1._signal._connections[0].disconnect_pin),
        id(r.J1.gp1._ground._connections[0].disconnect_pin),
    }
    assert bound_ids == {id(p) for p in pins}


def test_disconnect_between_explicit_pin_numbers():
    a = _A("A")
    b = _B("B")
    a.J1.power.connect(b.J1.power)
    mate = Disconnect("DC1")
    [pin] = mate.between(a.J1.power, b.J1.power, pins=[7])
    assert pin.number == 7
    assert mate[7] is pin


def test_resolved_sides_per_bundle():
    h, a, b, mate = _two_bundle_setup()
    seg = next(s for s in h.segments() if s.end_a is a.J1.power)
    sides = h.resolved_sides(seg)
    assert sides == (10 + 2 + 1, 1 + 20 + 3)  # leg_a + trunk + leg_disc, leg_disc + trunk + leg_b
    assert h.resolved_length(seg) == sum(sides)


def test_validate_warns_when_disconnect_half_attached():
    a = _A("A")
    b = _B("B")
    a.J1.power.connect(b.J1.power)
    mate = Disconnect("DC1")
    mate.between(a.J1.power, b.J1.power)
    bundle = Bundle("only")
    root = bundle.breakout("root")
    root.attach(a.J1, leg_length=1)
    root.attach(b.J1, leg_length=1)
    bundle.freeze()
    h = Harness("t")
    h.add(a, b, mate, bundle)
    warnings = h.validate_bundles()
    assert any("disconnect 'DC1' not attached" in w for w in warnings)


def test_bom_emits_two_rows_and_disconnects_section():
    h, a, b, mate = _two_bundle_setup()
    bom = build_bom(h)
    # Each pass-through pin produced 2 wire rows × 2 pins = 4 rows total.
    assert len(bom.wires) == 4
    # Disconnects section lists both pins of mate.
    assert len(bom.disconnects) == 1
    entry = bom.disconnects[0]
    assert entry.id == "DC1"
    assert {row.signal_name for row in entry.pins} == {"Power", "Ground"}


def test_disconnect_between_pin_and_terminal():
    a = _A("A")
    fuse = Fuse("F1", "Main", 5)
    seg = a.J1.power.connect(fuse)
    mate = Disconnect("DC1")
    [pin] = mate.between(a.J1.power, fuse)
    h = Harness("t")
    h.add(a, mate, fuse)
    h.segments()
    assert pin._segment is seg
    assert seg.disconnect_pin is pin


def test_disconnect_between_pin_and_ground():
    a = _A("A")
    gnd = GroundSymbol("CHASSIS_GND")
    a.J1.gnd.connect(gnd)
    mate = Disconnect("DC1")
    pins = mate.between(a.J1.gnd, gnd)
    assert len(pins) == 1
    h = Harness("t")
    h.add(a, gnd, mate)
    h.segments()
    assert pins[0]._segment is not None


def test_can_disconnect_marks_only_adjacent_devices():
    class _CA(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(1, 2)

    class _CB(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(3, 4)

    class _CC(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(5, 6)

    a = _CA("CA")
    b = _CB("CB")
    c = _CC("CC")
    bus = CanBusLine("Avx", devices=[a.J1, b.J1, c.J1])
    mate = Disconnect("DC1")
    h_pin, l_pin = mate.between(a.J1.can, b.J1.can)
    h = Harness("t")
    h.add(a, b, c, bus, mate)
    h.segments()
    assert h_pin._can_rail == "high"
    assert l_pin._can_rail == "low"
    # With the H=prev / L=next convention, a single row per device points
    # toward the disconnect. That row carries BOTH pins (H and L) of the
    # disconnect since both rails pass through the same physical cable.
    assert len(h_pin._segments) == 1
    assert len(l_pin._segments) == 1
    # The CAN shield foil also passes through the disconnect, so a third
    # (shield-drain) DisconnectPin is attached alongside H and L.
    shield_pins = [p for p in mate._pins.values() if p._shield_group is not None]
    assert len(shield_pins) == 1
    expected = {id(h_pin), id(l_pin), id(shield_pins[0])}
    assert {id(p) for p in a.J1.can._low.disconnect_pins} == expected
    assert {id(p) for p in b.J1.can._high.disconnect_pins} == expected
    # The opposite rails on each side carry nothing.
    assert a.J1.can._high.disconnect_pins == []
    assert b.J1.can._low.disconnect_pins == []
    # And device c — not adjacent — has no annotation.
    assert c.J1.can._high.disconnect_pins == []
    assert c.J1.can._low.disconnect_pins == []


def test_two_can_disconnects_on_same_bus():
    """One disconnect on each side of an interior device — both annotated."""

    class _CG(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(1, 2)

    class _CH(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(3, 4)

    class _CI(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(5, 6)

    a = _CG("CG")
    b = _CH("CH")
    c = _CI("CI")
    bus = CanBusLine("Avx", devices=[a.J1, b.J1, c.J1])
    left = Disconnect("LEFT")
    right = Disconnect("RIGHT")
    left.between(a.J1.can, b.J1.can)  # a-b link
    right.between(b.J1.can, c.J1.can)  # b-c link

    h = Harness("t")
    h.add(a, b, c, bus, left, right)
    h.segments()

    # b is interior: H (prev=a) crossed by LEFT, L (next=c) crossed by RIGHT.
    # Each disconnect carries an extra shield-drain pin alongside H and L.
    left_shield = next(p for p in left._pins.values() if p._shield_group is not None)
    right_shield = next(p for p in right._pins.values() if p._shield_group is not None)
    left_ids = {id(left._pins[1]), id(left._pins[2]), id(left_shield)}
    right_ids = {id(right._pins[1]), id(right._pins[2]), id(right_shield)}
    assert {id(p) for p in b.J1.can._high.disconnect_pins} == left_ids
    assert {id(p) for p in b.J1.can._low.disconnect_pins} == right_ids


def test_can_disconnect_requires_adjacent_devices():
    class _CD(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(1, 2)

    class _CE(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(3, 4)

    class _CF(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(5, 6)

    a = _CD("CD")
    b = _CE("CE")
    c = _CF("CF")
    bus = CanBusLine("Avx2", devices=[a.J1, b.J1, c.J1])
    mate = Disconnect("DC1")
    mate.between(a.J1.can, c.J1.can)  # non-adjacent
    h = Harness("t")
    h.add(a, b, c, bus, mate)
    with pytest.raises(ValueError, match="adjacent"):
        h.segments()


def test_orphan_can_pins_dont_render():

    class _Dev(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(1, 2)

    class _Solo(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(7, 8)
            other = Pin(9, "Other")

    a = _Dev("A")
    b = _Dev("B")
    solo = _Solo("Solo")  # has CAN pins but is NOT in any CanBusLine
    bus = CanBusLine("Avx", devices=[a.J1, b.J1])

    h = Harness("t")
    h.add(a, b, solo, bus)
    result = layout(h)

    rendered_pins = {
        (row.pin._component.label, row.pin.number) for row in result.all_rows if row.pin._component is not None
    }
    # Solo's CAN pins (7, 8) are hidden because Solo isn't in any CanBusLine.
    assert ("Solo", 7) not in rendered_pins
    assert ("Solo", 8) not in rendered_pins
    # The non-CAN pin on Solo still renders if it has connections; orphan filter
    # only applies to CAN pins.
    # Devices that ARE on the bus keep their CAN rows.
    assert ("A", 1) in rendered_pins
    assert ("B", 2) in rendered_pins


def test_disconnect_autodetect_from_namespace():
    a = _A("A")
    b = _B("B")
    a.J1.power.connect(b.J1.power)
    mate = _DT2("DC1")
    mate.power.between(a.J1.power, b.J1.power)
    h = Harness("auto")
    h.autodetect(locals())
    assert mate in h.disconnects


def test_shielded_port_disconnect_allocates_shield_drain_pin():
    class Reader(Component):
        class J1(Connector):
            gp1 = GPIO(18, 19, 20, name="GP1")  # shielded by default

    class Sensor(Component):
        output = GPIO("Or", "Gr", "Bl", name="Pos")

    r = Reader("R")
    s = Sensor("S")
    r.J1.gp1.connect(s.output)
    mate = Disconnect("DC1")
    signal_pins = mate.between(r.J1.gp1, s.output)
    h = Harness("t")
    h.add(r, s, mate)
    h.segments()

    shield_pins = [p for p in mate._pins.values() if p._shield_group is not None]
    assert len(shield_pins) == 1
    assert shield_pins[0].number == max(p.number for p in signal_pins) + 1
    # The shield drain pin should be annotated on the row of one of the
    # bound signal pins so the renderer picks it up.
    sg = r.J1.gp1._sg
    assert shield_pins[0]._shield_group is sg


def test_rs232_port_disconnect_allocates_shield_drain_pin():
    class A(Component):
        class J1(Connector):
            rs = RS232(1, 2, 3)

    class B(Component):
        class J1(Connector):
            rs = RS232(4, 5, 6)

    a = A("A")
    b = B("B")
    a.J1.rs.connect(b.J1.rs)
    mate = Disconnect("DC1")
    mate.between(a.J1.rs, b.J1.rs)
    h = Harness("t")
    h.add(a, b, mate)
    h.segments()

    shield_pins = [p for p in mate._pins.values() if p._shield_group is not None]
    assert len(shield_pins) == 1


def test_standalone_shield_full_coverage_allocates_drain():
    class A(Component):
        class J1(Connector):
            sig1 = Pin(1, "Signal 1")
            sig2 = Pin(2, "Signal 2")

    class B(Component):
        class J1(Connector):
            sig1 = Pin(1, "Signal 1")
            sig2 = Pin(2, "Signal 2")

    a = A("A")
    b = B("B")
    with Shield():
        a.J1.sig1.connect(b.J1.sig1)
        a.J1.sig2.connect(b.J1.sig2)
    mate = Disconnect("DC1")
    mate.between(a.J1.sig1, b.J1.sig1)
    mate.between(a.J1.sig2, b.J1.sig2)
    h = Harness("t")
    h.add(a, b, mate)
    h.segments()

    shield_pins = [p for p in mate._pins.values() if p._shield_group is not None]
    assert len(shield_pins) == 1


def test_standalone_shield_partial_coverage_errors():
    class A(Component):
        class J1(Connector):
            sig1 = Pin(1, "Signal 1")
            sig2 = Pin(2, "Signal 2")

    class B(Component):
        class J1(Connector):
            sig1 = Pin(1, "Signal 1")
            sig2 = Pin(2, "Signal 2")

    a = A("A")
    b = B("B")
    with Shield():
        a.J1.sig1.connect(b.J1.sig1)
        a.J1.sig2.connect(b.J1.sig2)
    mate = Disconnect("DC1")
    mate.between(a.J1.sig1, b.J1.sig1)  # only one of the two shielded wires
    h = Harness("t")
    h.add(a, b, mate)
    with pytest.raises(ValueError, match="partial"):
        h.segments()


def test_can_bus_disconnect_splits_cable_and_disconnect_rows_reference_ids():
    class _Node(Component):
        def can_terminate(self):
            pass

        class J1(Connector):
            can = CanBus(1, 2)

    a = _Node("A")
    b = _Node("B")
    c = _Node("C")
    bus = CanBusLine("CAN", devices=[a.J1, b.J1, c.J1])
    mate = Disconnect("DC1")
    mate.between(a.J1.can, b.J1.can)
    h = Harness("t")
    h.add(a, b, c, bus, mate)

    bom = build_bom(h)
    can_cables = [r for r in bom.shielded_cables if r.cable_id.startswith("CAN-")]
    # The a-b cable splits into A and B; the b-c cable stays whole. Plus
    # CAN-2 (b → c). Total = 3 rows.
    assert [r.cable_id for r in can_cables] == ["CAN-1A", "CAN-1B", "CAN-2"]
    assert can_cables[0].from_label == "A.J1"
    assert can_cables[0].to_label == "DC1"
    assert can_cables[1].from_label == "DC1"
    assert can_cables[1].to_label == "B.J1"

    # Disconnect rows for CAN H, CAN L and the CAN shield reference the
    # canonical (un-suffixed) cable id, not the per-side A/B halves.
    rows = [r for entry in bom.disconnects if entry.id == "DC1" for r in entry.pins]
    assert any(r.wire_id == "CAN-1" for r in rows)


def test_bom_disconnect_drain_row_references_cable_id():
    class A(Component):
        class J1(Connector):
            sig1 = Pin(1, "Signal 1")
            sig2 = Pin(2, "Signal 2")

    class B(Component):
        class J1(Connector):
            sig1 = Pin(1, "Signal 1")
            sig2 = Pin(2, "Signal 2")

    a = A("A")
    b = B("B")
    with Shield(label="DAT"):
        a.J1.sig1.connect(b.J1.sig1)
        a.J1.sig2.connect(b.J1.sig2)
    mate = Disconnect("DC1")
    mate.between(a.J1.sig1, b.J1.sig1)
    mate.between(a.J1.sig2, b.J1.sig2)
    h = Harness("t")
    h.add(a, b, mate)
    bom = build_bom(h)

    drain_rows = [r for entry in bom.disconnects for r in entry.pins if r.gauge == "drain"]
    assert len(drain_rows) == 1
    row = drain_rows[0]
    assert row.wire_id == "DAT"
    assert "(shield foil)" not in row.from_label
    assert "(shield foil)" not in row.to_label
    assert "A" in row.from_label
    assert "B" in row.to_label


def test_between_shield_explicit_override():
    class A(Component):
        class J1(Connector):
            sig1 = Pin(1, "Signal 1")
            sig2 = Pin(2, "Signal 2")

    class B(Component):
        class J1(Connector):
            sig1 = Pin(1, "Signal 1")
            sig2 = Pin(2, "Signal 2")

    a = A("A")
    b = B("B")
    with Shield() as sh:
        a.J1.sig1.connect(b.J1.sig1)
        a.J1.sig2.connect(b.J1.sig2)
    mate = Disconnect("DC1")
    mate.between(a.J1.sig1, b.J1.sig1)
    # Explicit drain pin avoids the partial-coverage error.
    drain = mate.between_shield(sh.group)
    h = Harness("t")
    h.add(a, b, mate)
    h.segments()
    assert drain._shield_group is sh.group
    # Idempotent.
    assert mate.between_shield(sh.group) is drain
