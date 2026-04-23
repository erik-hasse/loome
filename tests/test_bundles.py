from __future__ import annotations

import pytest

from loome import Bundle, GroundSymbol, Harness
from loome.bundles import Bundle as _BundleCls
from loome.model import Component, Connector, Pin


class _Box(Component):
    class J1(Connector):
        p1 = Pin(1)
        p2 = Pin(2)


def test_single_root_enforced():
    b = Bundle("x")
    b.breakout("a")
    with pytest.raises(ValueError, match="already has a root"):
        b.breakout("b")


def test_freeze_rejects_orphan():
    b = Bundle("x")
    root = b.breakout("root")
    # Manually construct an orphan that doesn't point back to root.
    orphan = b.breakout("orphan", after=root, length=1)
    orphan.parent = None  # detach
    with pytest.raises(ValueError, match="already has a root|orphan|no root"):
        b.freeze()


def test_distance_trunk_and_branch():
    b = Bundle("x")
    root = b.breakout("root")
    mid = b.breakout("mid", after=root, length=10)
    tail = b.breakout("tail", after=mid, length=20)
    branch = b.breakout("branch", after=mid, length=5)
    b.freeze()
    assert b.distance(root, tail) == 30
    assert b.distance(root, branch) == 15
    assert b.distance(tail, branch) == 25  # tail → mid (20) + mid → branch (5)
    assert b.distance(root, root) == 0


def test_attachment_lookup_by_pin():
    box_a = _Box("A")
    box_b = _Box("B")
    b = Bundle("x")
    left = b.breakout("left")
    right = b.breakout("right", after=left, length=100)
    left.attach(box_a.J1, leg_length=1)
    right.attach(box_b.J1, leg_length=2)
    b.freeze()

    att = b.attachment_for(box_a.J1.p1)
    assert att is not None
    assert att.breakout is left
    assert att.leg_length == 1


def test_double_attach_rejected():
    box_a = _Box("A")
    b = Bundle("x")
    left = b.breakout("left")
    right = b.breakout("right", after=left, length=100)
    left.attach(box_a.J1, leg_length=1)
    right.attach(box_a.J1, leg_length=2)
    with pytest.raises(ValueError, match="attached twice"):
        b.freeze()


def test_terminal_attachment_resolves():
    gnd = GroundSymbol("CHASSIS_GND")
    b = Bundle("x")
    root = b.breakout("root")
    root.attach(gnd, leg_length=4)
    b.freeze()
    assert b.attachment_for(gnd) is not None
    assert b.attachment_for(gnd).leg_length == 4


def test_freeze_is_idempotent():
    b = Bundle("x")
    b.breakout("root")
    b.freeze()
    b.freeze()  # second call is a no-op
    assert isinstance(b, _BundleCls)


def test_harness_autodetects_bundle_and_freezes():
    box_a = _Box("A")
    box_b = _Box("B")
    b = Bundle("trunk")
    left = b.breakout("left")
    right = b.breakout("right", after=left, length=7)
    left.attach(box_a.J1, leg_length=1)
    right.attach(box_b.J1, leg_length=1)
    box_a.J1.p1.connect(box_b.J1.p1)

    h = Harness("h")
    h.autodetect({"a": box_a, "b": box_b, "trunk": b})
    assert b in h.bundles
    # freeze() is idempotent so it's safe to call externally; but autodetect
    # already ran freeze, so attachment_for() works.
    assert b.attachment_for(box_a.J1.p1) is not None
