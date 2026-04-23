from __future__ import annotations

from loome import Bundle, Fuse, GroundSymbol, Harness
from loome.model import Component, Connector, Pin, SpliceNode


class _Box(Component):
    class J1(Connector):
        p1 = Pin(1)
        p2 = Pin(2)


def _build(leg_a=2, trunk=10, leg_b=3, connect=True):
    a = _Box("A")
    b = _Box("B")
    bundle = Bundle("trunk")
    left = bundle.breakout("left")
    right = bundle.breakout("right", after=left, length=trunk)
    left.attach(a.J1, leg_length=leg_a)
    right.attach(b.J1, leg_length=leg_b)
    if connect:
        a.J1.p1.connect(b.J1.p1)
    h = Harness("h")
    h.autodetect({"a": a, "b": b, "trunk": bundle})
    return h, a, b, bundle


def test_resolved_length_sums_leg_trunk_leg():
    h, a, b, bundle = _build(leg_a=2, trunk=10, leg_b=3)
    (seg,) = [s for s in h.segments() if hasattr(s.end_a, "number") and hasattr(s.end_b, "number")]
    assert h.resolved_length(seg) == 15


def test_resolved_length_none_when_unattached():
    a = _Box("A")
    b = _Box("B")
    bundle = Bundle("trunk")
    left = bundle.breakout("left")
    left.attach(a.J1, leg_length=2)  # only a is attached
    a.J1.p1.connect(b.J1.p1)
    h = Harness("h")
    h.autodetect({"a": a, "b": b, "trunk": bundle})
    (seg,) = [s for s in h.segments() if hasattr(s.end_a, "number") and hasattr(s.end_b, "number")]
    assert h.resolved_length(seg) is None


def test_resolved_length_none_across_bundles():
    a = _Box("A")
    b = _Box("B")
    bundle1 = Bundle("t1")
    bundle2 = Bundle("t2")
    bundle1.breakout("r1").attach(a.J1, leg_length=1)
    bundle2.breakout("r2").attach(b.J1, leg_length=1)
    a.J1.p1.connect(b.J1.p1)
    h = Harness("h")
    h.autodetect({"a": a, "b": b, "t1": bundle1, "t2": bundle2})
    (seg,) = [s for s in h.segments() if hasattr(s.end_a, "number") and hasattr(s.end_b, "number")]
    assert h.resolved_length(seg) is None


def test_resolved_length_to_terminal():
    a = _Box("A")
    gnd = GroundSymbol("GND")
    bundle = Bundle("trunk")
    left = bundle.breakout("left")
    right = bundle.breakout("right", after=left, length=6)
    left.attach(a.J1, leg_length=2)
    right.attach(gnd, leg_length=1)
    a.J1.p1.connect(gnd)
    h = Harness("h")
    h.autodetect({"a": a, "gnd": gnd, "trunk": bundle})
    (seg,) = [s for s in h.segments()]
    assert h.resolved_length(seg) == 9


def test_resolved_length_through_splice():
    a = _Box("A")
    b = _Box("B")
    fuse = Fuse("f1", "Main", 5)
    splice = SpliceNode("S1")
    bundle = Bundle("trunk")
    left = bundle.breakout("left")
    mid = bundle.breakout("mid", after=left, length=4)
    right = bundle.breakout("right", after=mid, length=6)
    left.attach(a.J1, leg_length=1)
    mid.attach(splice, leg_length=2)
    right.attach(b.J1, leg_length=3)
    right.attach(fuse, leg_length=1)
    a.J1.p1.connect(splice)
    splice.connect(b.J1.p1)
    splice.connect(fuse)
    h = Harness("h")
    h.autodetect({"a": a, "b": b, "fuse": fuse, "s": splice, "trunk": bundle})
    lengths = [h.resolved_length(s) for s in h.segments()]
    # a.p1 → splice: 1 + 4 + 2 = 7
    # splice → b.p1: 2 + 6 + 3 = 11
    # splice → fuse: 2 + 6 + 1 = 9
    assert sorted(lengths) == [7, 9, 11]


def test_validate_bundles_reports_unattached_endpoint():
    a = _Box("A")
    b = _Box("B")
    bundle = Bundle("trunk")
    bundle.breakout("r").attach(a.J1, leg_length=1)  # b not attached
    a.J1.p1.connect(b.J1.p1)
    h = Harness("h")
    h.autodetect({"a": a, "b": b, "trunk": bundle})
    warnings = h.validate_bundles()
    assert any("unattached" in w for w in warnings)
