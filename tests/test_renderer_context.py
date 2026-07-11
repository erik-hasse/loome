from __future__ import annotations

from loome import Fuse, GroundSymbol, Harness, Pin
from loome.layout.engine import layout
from loome.model import Component, Connector, Shield
from loome.ports import RS232
from loome.renderers.context import build_render_context
from loome.renderers.svg import _build_shield_oval_plan, render


class _Serial(Component):
    class J1(Connector):
        serial = RS232(1, 2, 3, name="SER")


def test_render_context_indexes_rows_segments_and_shields():
    a = _Serial("A")
    b = _Serial("B")
    a.J1.serial.connect(b.J1.serial)
    h = Harness("h")
    h.autodetect({"a": a, "b": b})

    result = layout(h)
    ctx = build_render_context(h, result)

    row = ctx.rows.primary_inst_row(a.J1.serial.tx)
    assert row is not None
    assert ctx.rows.row_for_pin(a.J1.serial.tx) is row
    assert id(a.J1.serial.tx) in ctx.rows.rendered_pin_ids
    assert ctx.shield_for_row(row) is a.J1.serial._sg
    assert id(a.J1.serial.tx) in ctx.pin_shield_palette
    assert id(b.J1.serial.rx) in ctx.pin_shield_palette
    assert row in ctx.rows.rows_for_segment(a.J1.serial.tx._connections[0])


def _planned_rows(plan):
    return [
        *[row for rows in plan.near_rows_by_inst.values() for row in rows],
        *[row for rows in plan.far_rows_by_inst.values() for row in rows],
    ]


def test_shield_oval_plan_treats_port_shields_as_near_side_owners():
    a = _Serial("A")
    b = _Serial("B")
    a.J1.serial.connect(b.J1.serial)
    h = Harness("h")
    h.autodetect({"a": a, "b": b})

    result = layout(h)
    ctx = build_render_context(h, result)
    local_plan = _build_shield_oval_plan(a.J1.serial._sg, ctx)
    remote_plan = _build_shield_oval_plan(b.J1.serial._sg, ctx)

    assert _planned_rows(_build_shield_oval_plan(_Serial.J1.serial._sg, ctx)) == []
    assert len([row for rows in local_plan.near_rows_by_inst.values() for row in rows]) == 3
    assert local_plan.far_rows_by_inst == {}
    assert len([row for rows in remote_plan.near_rows_by_inst.values() for row in rows]) == 3
    assert remote_plan.far_rows_by_inst == {}


def test_connection_level_shield_plan_overrides_endpoint_owned_port_shields():
    a = _Serial("A")
    b = _Serial("B")

    with Shield() as shield:
        a.J1.serial.tx.connect(b.J1.serial.rx)

    h = Harness("h")
    h.autodetect({"a": a, "b": b, "shield": shield})
    result = layout(h)
    ctx = build_render_context(h, result)

    assert _planned_rows(_build_shield_oval_plan(a.J1.serial._sg, ctx)) == []
    explicit_plan = _build_shield_oval_plan(shield.group, ctx)
    assert len([row for rows in explicit_plan.near_rows_by_inst.values() for row in rows]) == 1
    assert len([row for rows in explicit_plan.far_rows_by_inst.values() for row in rows]) == 1


def test_svg_render_accepts_mutable_shield_groups(tmp_path):
    a = _Serial("A")
    b = _Serial("B")
    a.J1.serial.connect(b.J1.serial)
    h = Harness("h")
    h.autodetect({"a": a, "b": b})

    output = tmp_path / "out.svg"
    render(h, layout(h), output)

    assert output.exists()


def test_svg_render_combines_shared_fuse_legs_into_one_terminal_junction(tmp_path):
    class Display(Component):
        class J1(Connector):
            power_1 = Pin(11, "Power 1")
            power_2 = Pin(12, "Power 2")
            power_3 = Pin(31, "Power 3")
            power_4 = Pin(32, "Power 4")

    display = Display("Display")
    fuse = Fuse("F1", amps=7.5)
    display.J1.power_1 >> fuse
    display.J1.power_1 >> display.J1.power_2
    display.J1.power_3 >> fuse
    display.J1.power_3 >> display.J1.power_4
    h = Harness("h")
    h.autodetect({"display": display, "fuse": fuse})

    output = tmp_path / "out.svg"
    result = layout(h)
    render(h, result, output)
    svg = output.read_text()

    rows = [
        result.pin_rows[id(pin)]
        for pin in (display.J1.power_1, display.J1.power_2, display.J1.power_3, display.J1.power_4)
    ]
    assert all(current.rect.y + current.rect.h == following.rect.y for current, following in zip(rows, rows[1:]))

    assert svg.count(">F1 7.5A</text>") == 1
    assert svg.count('fill="#fef9c3"') == 1
    assert svg.count('stroke="#dc2626"') >= 6
    fuse_symbol = next(line for line in svg.splitlines() if 'fill="#fef9c3"' in line)
    assert f'y="{rows[0].rect.y + rows[0].rect.h / 2 - 5}"' in fuse_symbol


def test_svg_render_keeps_distinct_fuses_separate(tmp_path):
    class Loads(Component):
        class J1(Connector):
            load_1 = Pin(1, "Load 1")
            load_2 = Pin(2, "Load 2")

    loads = Loads("Loads")
    fuse_1 = Fuse("F1", amps=5)
    fuse_2 = Fuse("F2", amps=5)
    loads.J1.load_1 >> fuse_1
    loads.J1.load_2 >> fuse_2
    h = Harness("h")
    h.autodetect({"loads": loads, "fuse_1": fuse_1, "fuse_2": fuse_2})

    output = tmp_path / "out.svg"
    render(h, layout(h), output)
    svg = output.read_text()

    assert svg.count('fill="#fef9c3"') == 2
    assert svg.count(">F1 5A</text>") == 1
    assert svg.count(">F2 5A</text>") == 1


def test_svg_render_combines_shared_ground_legs_into_one_terminal_junction(tmp_path):
    class Display(Component):
        class J1(Connector):
            ground_1 = Pin(9, "Ground 1")
            ground_2 = Pin(10, "Ground 2")
            ground_3 = Pin(15, "Ground 3")
            ground_4 = Pin(16, "Ground 4")

    display = Display("Display")
    ground = GroundSymbol("GND")
    for pin in (display.J1.ground_1, display.J1.ground_2, display.J1.ground_3, display.J1.ground_4):
        pin >> ground
    h = Harness("h")
    h.autodetect({"display": display, "ground": ground})

    output = tmp_path / "out.svg"
    result = layout(h)
    render(h, result, output)
    svg = output.read_text()

    rows = [
        result.pin_rows[id(pin)]
        for pin in (display.J1.ground_1, display.J1.ground_2, display.J1.ground_3, display.J1.ground_4)
    ]
    assert all(current.rect.y + current.rect.h == following.rect.y for current, following in zip(rows, rows[1:]))
    assert svg.count(">GND</text>") == 1
    assert svg.count('stroke="#111111"') >= 8
