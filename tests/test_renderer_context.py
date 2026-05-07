from __future__ import annotations

from loome import Harness
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
