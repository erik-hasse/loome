from __future__ import annotations

from loome import Harness
from loome.layout.engine import layout
from loome.model import Component, Connector
from loome.ports import RS232
from loome.renderers.context import build_render_context


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
