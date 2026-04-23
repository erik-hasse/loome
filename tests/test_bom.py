from __future__ import annotations

import csv
import io

from loome import (
    BusBar,
    CircuitBreaker,
    CircuitBreakerBank,
    Fuse,
    FuseBlock,
    GroundSymbol,
    Harness,
    SpliceNode,
)
from loome.bom import (
    build_bom,
    build_fuse_schedule,
    render_bom_csv,
    render_bom_md,
    render_fuse_schedule_csv,
    render_fuse_schedule_md,
    trace_loads,
)
from loome.model import Component, Connector, Pin


class _Load(Component):
    class J1(Connector):
        pwr = Pin(1, "Power")
        gnd = Pin(2, "Ground")


def _harness(ns: dict) -> Harness:
    h = Harness("test")
    h.autodetect(ns)
    return h


def test_trace_loads_direct_pin():
    load = _Load("Load A")
    fuse = Fuse("F1", name="F1", amps=5)
    load.J1.pwr.connect(fuse, gauge=22, color="R")

    h = _harness({"load": load, "fuse": fuse})
    wire, loads = trace_loads(fuse, h)

    assert wire is not None
    assert len(loads) == 1
    assert loads[0].kind == "pin"
    assert "Load A" in loads[0].label
    assert "Power" in loads[0].label


def test_trace_loads_through_splice():
    a = _Load("A")
    b = _Load("B")
    fuse = Fuse("F1", name="F1", amps=5)
    splice = SpliceNode("S1", label="PWR_BUS")
    a.J1.pwr.connect(splice)
    b.J1.pwr.connect(splice)
    splice.connect(fuse)

    h = _harness({"a": a, "b": b, "fuse": fuse, "splice": splice})
    _, loads = trace_loads(fuse, h)

    labels = {ld.label for ld in loads}
    assert any("A" in lbl for lbl in labels)
    assert any("B" in lbl for lbl in labels)


def test_trace_loads_through_busbar_records_both():
    load = _Load("L")
    fuse = Fuse("F1", name="F1", amps=5)
    bar = BusBar("PWR_BAR", label="Power Bar")
    fuse_splice = SpliceNode("FS", label="fuse-to-bar")
    fuse.id  # keep reference
    # fuse → splice → bar → pin
    fuse_splice.connect(fuse)
    fuse_splice.connect(bar)
    load.J1.pwr.connect(bar)

    h = _harness({"load": load, "fuse": fuse, "bar": bar, "fs": fuse_splice})
    _, loads = trace_loads(fuse, h)

    kinds = [ld.kind for ld in loads]
    assert "busbar" in kinds
    assert "pin" in kinds
    assert any("Power Bar" in ld.label for ld in loads if ld.kind == "busbar")


def test_trace_loads_class_level_expands_to_all_instances():
    class _Servo(Component):
        class J1(Connector):
            pwr = Pin(1, "Power")

    fuse = Fuse("FAP", name="AP", amps=5)
    _Servo.J1.pwr.connect(fuse)

    s1 = _Servo("Servo 1")
    s2 = _Servo("Servo 2")
    h = _harness({"s1": s1, "s2": s2, "fuse": fuse})

    _, loads = trace_loads(fuse, h)
    labels = {ld.label for ld in loads}
    assert any("Servo 1" in lbl for lbl in labels)
    assert any("Servo 2" in lbl for lbl in labels)


def test_trace_loads_cycle_guard():
    fuse = Fuse("F1", name="F1", amps=5)
    s1 = SpliceNode("S1")
    s2 = SpliceNode("S2")
    s1.connect(fuse)
    s1.connect(s2)
    s2.connect(s1)  # cycle

    h = _harness({"fuse": fuse, "s1": s1, "s2": s2})
    _, loads = trace_loads(fuse, h)
    # No pins downstream, and the cycle doesn't hang; we may or may not emit
    # terminal loads, but the call must return.
    assert isinstance(loads, list)


def test_fuse_schedule_includes_location_from_block():
    load = _Load("L")
    fuse = Fuse("F1", name="Air Data", amps=5)
    block = FuseBlock("FB1", label="Main Panel Block")
    block.place(3, fuse)
    load.J1.pwr.connect(fuse)

    h = _harness({"load": load, "fuse": fuse, "block": block})
    schedule = build_fuse_schedule(h)
    assert len(schedule) == 1
    assert schedule[0].location == "FB1:3"


def test_cb_bank_location_reported():
    load = _Load("L")
    cb = CircuitBreaker("CB1", name="Landing", amps=15)
    bar = BusBar("BAR1", label="Main Bus")
    bank = CircuitBreakerBank("CBBAR1", label="Main Bank", bus=bar)
    bank.place(2, cb)
    load.J1.pwr.connect(cb)

    h = _harness({"load": load, "cb": cb, "bar": bar, "bank": bank})
    schedule = build_fuse_schedule(h)
    assert schedule[0].location == "CBBAR1:2"


def test_bom_has_wires_totals_and_terminals():
    load = _Load("L")
    fuse = Fuse("F1", name="F1", amps=5)
    gnd = GroundSymbol("GND")
    load.J1.pwr.connect(fuse, gauge=22, color="R")
    load.J1.gnd.connect(gnd, gauge=22, color="B")

    h = _harness({"load": load, "fuse": fuse, "gnd": gnd})
    bom = build_bom(h)

    assert len(bom.wires) == 2
    assert "22" in bom.gauge_totals
    assert bom.gauge_totals["22"].count == 2
    assert "Fuse" in bom.terminals_by_type
    assert "GroundSymbol" in bom.terminals_by_type
    assert any(conn[0] == "L" for conn in bom.connectors)


def test_bom_synthesizes_wire_ids_for_empty_ones():
    load = _Load("L")
    gnd = GroundSymbol("GND")
    load.J1.gnd.connect(gnd, gauge=22, color="B")
    h = _harness({"load": load, "gnd": gnd})

    bom = build_bom(h)
    assert bom.wires[0].wire_id == "22B-1"


def test_markdown_renderers_produce_nonempty_tables():
    load = _Load("L")
    fuse = Fuse("F1", name="F1", amps=5)
    load.J1.pwr.connect(fuse, gauge=22, color="R")
    h = _harness({"load": load, "fuse": fuse})

    md = render_fuse_schedule_md(build_fuse_schedule(h), h)
    assert "Fuse / CB Schedule" in md
    assert "| F  |" in md or "| F " in md
    assert "F1" in md

    bom_md = render_bom_md(build_bom(h), h)
    assert "## Wires" in bom_md
    assert "## Totals by gauge" in bom_md
    assert "## Connectors" in bom_md
    assert "## Terminals" in bom_md


def test_csv_renderers_parse_back():
    load = _Load("L")
    fuse = Fuse("F1", name="F1", amps=5)
    load.J1.pwr.connect(fuse, gauge=22, color="R")
    h = _harness({"load": load, "fuse": fuse})

    sched_csv = render_fuse_schedule_csv(build_fuse_schedule(h), h)
    rows = list(csv.reader(io.StringIO(sched_csv)))
    assert rows[0] == ["Type", "ID", "Name", "Amps", "Location", "Wire", "Length", "Feeds"]
    assert rows[1][0] == "F"
    assert rows[1][1] == "F1"

    bom_csv = render_bom_csv(build_bom(h), h)
    assert "Wire ID,Gauge,Color" in bom_csv
    assert "# Wires" in bom_csv
