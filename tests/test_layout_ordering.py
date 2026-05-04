from __future__ import annotations

from loome import Component, Connector, GroundSymbol, Pin, Shield
from loome.layout.ordering import pin_sort_keys, sort_legs


def _ordered_attrs(component: Component, attrs: list[str]) -> list[str]:
    conn = component.J1
    return pin_sort_keys(
        attrs,
        get_class_pin=lambda name: getattr(type(conn), name),
        get_inst_pin=lambda name: getattr(conn, name),
    )


def test_pin_sort_keeps_connection_level_shield_mates_contiguous():
    class Local(Component):
        class J1(Connector):
            p1 = Pin(1, "P1")
            p2 = Pin(2, "P2")
            p3 = Pin(3, "P3")
            p4 = Pin(4, "P4")

    class Remote(Component):
        class J1(Connector):
            r1 = Pin(1, "R1")
            r2 = Pin(2, "R2")
            r3 = Pin(3, "R3")
            r4 = Pin(4, "R4")

    local = Local("Local")
    remote = Remote("Remote")
    local.J1.p1 >> remote.J1.r1
    local.J1.p2 >> remote.J1.r2
    with Shield():
        local.J1.p3 >> remote.J1.r3
        local.J1.p4 >> remote.J1.r4

    ordered = _ordered_attrs(local, ["p1", "p2", "p3", "p4"])

    assert abs(ordered.index("p3") - ordered.index("p4")) == 1
    assert ordered.index("p3") < ordered.index("p4")


def test_pin_sort_pairs_self_jumpers_by_remote_partner():
    class JumperBlock(Component):
        class J1(Connector):
            p1 = Pin(1, "P1")
            p2 = Pin(2, "P2")
            p3 = Pin(3, "P3")
            p4 = Pin(4, "P4")

    block = JumperBlock("Block")
    block.J1.p1 >> block.J1.p4
    block.J1.p2 >> block.J1.p3

    ordered = _ordered_attrs(block, ["p1", "p2", "p3", "p4"])

    assert ordered == ["p1", "p4", "p2", "p3"]


def test_sort_legs_places_terminal_before_pin_legs_and_orders_remote_pins():
    class Source(Component):
        class J1(Connector):
            sig = Pin(1, "Signal")

    class Remote(Component):
        class J1(Connector):
            high = Pin(10, "High")
            low = Pin(2, "Low")

    source = Source("Source")
    remote = Remote("Remote")
    gnd = GroundSymbol("GND")
    seg_high = source.J1.sig.connect(remote.J1.high)
    seg_gnd = source.J1.sig.connect(gnd)
    seg_low = source.J1.sig.connect(remote.J1.low)

    assert sort_legs([seg_high, seg_gnd, seg_low], source.J1.sig) == [seg_gnd, seg_low, seg_high]


def test_sort_legs_prioritizes_shielded_pin_leg_over_unshielded_terminal_leg():
    class Source(Component):
        class J1(Connector):
            sig = Pin(1, "Signal")

    class Remote(Component):
        class J1(Connector):
            sig = Pin(1, "Signal")

    source = Source("Source")
    remote = Remote("Remote")
    gnd = GroundSymbol("GND")
    seg_gnd = source.J1.sig.connect(gnd)
    with Shield():
        seg_remote = source.J1.sig.connect(remote.J1.sig)

    assert sort_legs([seg_gnd, seg_remote], source.J1.sig) == [seg_remote, seg_gnd]
