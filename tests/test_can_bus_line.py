from __future__ import annotations

from loome import Bundle, CanBus, CanBusLine, Harness
from loome.model import Component, Connector


class _Node(Component):
    def can_terminate(self):
        self.J1.can.terminate()

    class J1(Connector):
        can = CanBus(1, 2)


def test_can_bus_resolved_length_is_trunk_sum():
    a, b, c = _Node("A"), _Node("B"), _Node("C")
    bundle = Bundle("trunk")
    ba = bundle.breakout("a")
    bb = bundle.breakout("b", after=ba, length=20)
    bc = bundle.breakout("c", after=bb, length=30)
    ba.attach(a.J1, leg_length=1)
    bb.attach(b.J1, leg_length=2)
    bc.attach(c.J1, leg_length=3)

    bus = CanBusLine("Main CAN", devices=[a.J1, b.J1, c.J1])

    h = Harness("h")
    h.autodetect({"a": a, "b": b, "c": c, "trunk": bundle, "bus": bus})

    assert bus.resolved_length(h) == 50  # 20 + 30
    segs = bus.segments(h)
    assert [d for _, _, d in segs] == [20, 30]


def test_can_pin_segment_length_is_leg():
    a, b = _Node("A"), _Node("B")
    bundle = Bundle("trunk")
    ba = bundle.breakout("a")
    bb = bundle.breakout("b", after=ba, length=50)
    ba.attach(a.J1, leg_length=4)
    bb.attach(b.J1, leg_length=7)
    bus = CanBusLine("Main CAN", devices=[a.J1, b.J1])

    h = Harness("h")
    h.autodetect({"a": a, "b": b, "trunk": bundle, "bus": bus})

    # CAN pins auto-connect at class level; segments live on the class-level pin.
    class_high = type(a.J1).can_high
    high_seg = next(s for s in h.segments() if s.end_a is class_high or s.end_b is class_high)
    # The segment's CAN-pin endpoint belongs to _Node's class, which is shared across
    # a and b. resolved_length picks the first matching CanBusLine device's leg.
    assert h.resolved_length(high_seg) in (4, 7)


def test_can_bus_warns_if_device_unattached():
    a, b = _Node("A"), _Node("B")
    bundle = Bundle("trunk")
    bundle.breakout("r").attach(a.J1, leg_length=1)  # b not attached
    bus = CanBusLine("Main CAN", devices=[a.J1, b.J1])

    h = Harness("h")
    h.autodetect({"a": a, "b": b, "trunk": bundle, "bus": bus})

    warnings = h.validate_bundles()
    assert any("CAN bus" in w and "not attached" in w for w in warnings)
    assert bus.resolved_length(h) is None


def test_warns_if_can_capable_connector_not_in_bus():
    a, b, c = _Node("A"), _Node("B"), _Node("C")
    bundle = Bundle("trunk")
    ba = bundle.breakout("a")
    bb = bundle.breakout("b", after=ba, length=10)
    bc = bundle.breakout("c", after=bb, length=10)
    ba.attach(a.J1, leg_length=1)
    bb.attach(b.J1, leg_length=1)
    bc.attach(c.J1, leg_length=1)
    bus = CanBusLine("Main CAN", devices=[a.J1, b.J1])  # c omitted

    h = Harness("h")
    h.autodetect({"a": a, "b": b, "c": c, "trunk": bundle, "bus": bus})

    warnings = h.validate_bundles()
    assert any("CAN-capable" in w and "C.J1" in w for w in warnings)
    assert not any("A.J1" in w and "CAN-capable" in w for w in warnings)
    assert not any("B.J1" in w and "CAN-capable" in w for w in warnings)
