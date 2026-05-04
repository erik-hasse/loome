from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loome import (
    CanBus,
    CanBusLine,
    Component,
    Connector,
    GroundSymbol,
    Harness,
    Pin,
    Shield,
    System,
)
from loome.bom import build_bom
from loome.wire_ids import (
    DEFAULT_SYSTEM,
    _format_gauge,
    assign_wire_ids,
    fingerprint_segment,
)


class _Box(Component):
    class J1(Connector):
        pwr = Pin(1, "Power")
        gnd = Pin(2, "Ground")


def _harness(ns: dict) -> Harness:
    h = Harness("t")
    h.autodetect(ns)
    return h


def test_default_system_when_none_set():
    a = _Box("A")
    gnd = GroundSymbol("GND")
    a.J1.gnd >> gnd
    h = _harness({"a": a, "gnd": gnd})
    assign_wire_ids(h, None)
    [seg] = h.segments()
    assert seg.wire_id.startswith(DEFAULT_SYSTEM)


def test_system_context_manager():
    a = _Box("A")
    b = _Box("B")
    with System("AVI"):
        a.J1.pwr >> b.J1.pwr
    h = _harness({"a": a, "b": b})
    assign_wire_ids(h, None)
    [seg] = [s for s in h.segments() if s.end_a is a.J1.pwr or s.end_b is a.J1.pwr]
    assert seg.wire_id.startswith("AVI")


def test_wire_override_beats_context():
    a = _Box("A")
    b = _Box("B")
    with System("AVI"):
        (a.J1.pwr >> b.J1.pwr).system("PWR")
    h = _harness({"a": a, "b": b})
    assign_wire_ids(h, None)
    [seg] = [s for s in h.segments() if s.end_a is a.J1.pwr]
    assert seg.wire_id.startswith("PWR")


def test_wire_builder_fluent_modifiers_mutate_underlying_segment():
    a = _Box("A")
    b = _Box("B")

    (a.J1.pwr >> b.J1.pwr).gauge(18).color("R").wire_id("W-1").notes("route left").system("PWR")
    h = _harness({"a": a, "b": b})

    [seg] = h.segments()
    assert seg.gauge == 18
    assert seg.color == "R"
    assert seg.wire_id == "W-1"
    assert seg.notes == "route left"
    assert seg.system == "PWR"


def test_component_default_system():
    a = _Box("A", system="ENG")
    gnd = GroundSymbol("GND")
    a.J1.gnd >> gnd
    h = _harness({"a": a, "gnd": gnd})
    assign_wire_ids(h, None)
    [seg] = h.segments()
    assert seg.wire_id.startswith("ENG")


def test_active_context_wins_over_component_system():
    a = _Box("A", system="ENG")
    b = _Box("B")
    with System("AVI"):
        a.J1.pwr >> b.J1.pwr
    h = _harness({"a": a, "b": b})
    assign_wire_ids(h, None)
    [seg] = [s for s in h.segments() if s.end_a is a.J1.pwr]
    assert seg.wire_id.startswith("AVI")


def test_invalid_system_code():
    System("ABCD")
    with pytest.raises(ValueError):
        System("ABCDE")


def test_format_helpers():
    assert _format_gauge(22) == "22"
    assert _format_gauge(8) == "08"
    assert _format_gauge("20") == "20"


def test_one_letter_color():
    a = _Box("A")
    gnd = GroundSymbol("GND")
    (a.J1.gnd >> gnd).color("B")
    h = _harness({"a": a, "gnd": gnd})
    assign_wire_ids(h, None)
    [seg] = h.segments()
    assert seg.wire_id == "GEN22B01"


def test_two_letter_color():
    a = _Box("A")
    b = _Box("B")
    (a.J1.pwr >> b.J1.pwr).color("BL")
    h = _harness({"a": a, "b": b})
    assign_wire_ids(h, None)
    [seg] = [s for s in h.segments() if s.end_a is a.J1.pwr]
    assert "BL" in seg.wire_id


def test_sidecar_persists_and_preserves_ids(tmp_path: Path):
    spec = tmp_path / "spec.py"
    spec.write_text("# placeholder")  # only used for sidecar path
    sidecar = tmp_path / "spec.wires.yaml"

    # Run 1: two wires.
    a = _Box("A")
    b = _Box("B")
    with System("AVI"):
        a.J1.pwr >> b.J1.pwr
        a.J1.gnd >> b.J1.gnd
    h = _harness({"a": a, "b": b})
    assign_wire_ids(h, spec)
    pwr_id = next(s for s in h.segments() if s.end_a is a.J1.pwr).wire_id
    gnd_id = next(s for s in h.segments() if s.end_a is a.J1.gnd).wire_id
    assert sidecar.exists()

    # Run 2: same harness rebuilt fresh — IDs must be preserved.
    a2 = _Box("A")
    b2 = _Box("B")
    with System("AVI"):
        a2.J1.pwr >> b2.J1.pwr
        a2.J1.gnd >> b2.J1.gnd
    h2 = _harness({"a": a2, "b": b2})
    assign_wire_ids(h2, spec)
    assert next(s for s in h2.segments() if s.end_a is a2.J1.pwr).wire_id == pwr_id
    assert next(s for s in h2.segments() if s.end_a is a2.J1.gnd).wire_id == gnd_id


def test_added_wire_does_not_renumber_existing(tmp_path: Path):
    spec = tmp_path / "spec.py"
    spec.write_text("# placeholder")

    # Run 1: only pwr wire.
    a = _Box("A")
    b = _Box("B")
    with System("AVI"):
        a.J1.pwr >> b.J1.pwr
    h = _harness({"a": a, "b": b})
    assign_wire_ids(h, spec)
    pwr_id = next(s for s in h.segments() if s.end_a is a.J1.pwr).wire_id

    # Run 2: same pwr + new gnd. pwr_id must not change.
    a2 = _Box("A")
    b2 = _Box("B")
    with System("AVI"):
        a2.J1.pwr >> b2.J1.pwr
        a2.J1.gnd >> b2.J1.gnd
    h2 = _harness({"a": a2, "b": b2})
    assign_wire_ids(h2, spec)
    assert next(s for s in h2.segments() if s.end_a is a2.J1.pwr).wire_id == pwr_id
    new_id = next(s for s in h2.segments() if s.end_a is a2.J1.gnd).wire_id
    assert new_id != pwr_id


def test_removed_wire_becomes_orphan(tmp_path: Path):
    spec = tmp_path / "spec.py"
    spec.write_text("# placeholder")
    sidecar = tmp_path / "spec.wires.yaml"

    a = _Box("A")
    b = _Box("B")
    with System("AVI"):
        a.J1.pwr >> b.J1.pwr
        a.J1.gnd >> b.J1.gnd
    h = _harness({"a": a, "b": b})
    assign_wire_ids(h, spec)
    gnd_id = next(s for s in h.segments() if s.end_a is a.J1.gnd).wire_id

    # Run 2: drop the gnd wire.
    a2 = _Box("A")
    b2 = _Box("B")
    with System("AVI"):
        a2.J1.pwr >> b2.J1.pwr
    h2 = _harness({"a": a2, "b": b2})
    assign_wire_ids(h2, spec)
    data = yaml.safe_load(sidecar.read_text())
    assert any(o["id"] == gnd_id for o in data["orphans"])


def test_shielded_group_gets_one_id():
    class _Sig(Component):
        class J1(Connector):
            a = Pin(1, "A")
            b = Pin(2, "B")

    src = _Sig("S")
    dst = _Sig("D")
    with System("AVI"):
        with Shield():
            src.J1.a >> dst.J1.a
            src.J1.b >> dst.J1.b
    h = _harness({"src": src, "dst": dst})
    assign_wire_ids(h, None)
    ids = {s.wire_id for s in h.segments()}
    assert len(ids) == 1
    [wid] = ids
    assert "SH" in wid
    assert wid.startswith("AVI")


def test_can_bus_segments_get_one_id_per_pair():
    class _Node(Component):
        system = "CAN"

        def can_terminate(self):
            self.J1.can.terminate()

        class J1(Connector):
            can = CanBus(1, 2)

    a, b, c = _Node("A"), _Node("B"), _Node("C")
    bus = CanBusLine("Main CAN", devices=[a.J1, b.J1, c.J1])
    h = Harness("h")
    h.autodetect({"a": a, "b": b, "c": c, "bus": bus})
    assign_wire_ids(h, None)

    bom = build_bom(h)
    can_rows = [r for r in bom.shielded_cables if r.cable_id.startswith("CAN")]
    assert len(can_rows) == 2  # A↔B and B↔C
    for r in can_rows:
        assert "SH" in r.cable_id
        assert r.cable_id.startswith("CAN")
    # Each adjacent pair gets a distinct ID.
    assert len({r.cable_id for r in can_rows}) == 2


def test_fingerprint_stable_across_endpoint_order():
    a = _Box("A")
    gnd = GroundSymbol("G")
    seg1 = a.J1.gnd.connect(gnd)
    fp1 = fingerprint_segment(seg1)

    a2 = _Box("A")
    gnd2 = GroundSymbol("G")
    seg2 = gnd2.connect(a2.J1.gnd) if False else a2.J1.gnd.connect(gnd2)
    # Even if we swap end_a/end_b in the data class, the fingerprint sorts.
    seg2.end_a, seg2.end_b = seg2.end_b, seg2.end_a
    assert fingerprint_segment(seg2) == fp1
