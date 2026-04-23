from __future__ import annotations

import svgwrite

from ..harness import Harness
from ..layout.engine import PIN_NUM_W, WIRE_AREA_W, PinGroup, PinRowInfo
from ..model import Pin, ShieldGroup, SpliceNode, Terminal, WireSegment
from .colors import _wire_attrs
from .primitives import (
    _JUMPER_STUB_X,
    _MONO_CHAR_W,
    _REMOTE_BOX_PIN_NUM_W,
    _REMOTE_BOX_W,
    _REMOTE_BOX_X,
    _SHIELD_LEFT_CX,
    _SHIELD_RIGHT_CX,
    _SHIELD_RX,
    _TERM_SYMBOL_W,
    _WIRE_PAD,
    _draw_terminal,
    _draw_unconnected,
    _draw_wire_label,
    _pin_comp_label,
    _remote_label,
)
from .splices import _draw_splice_connection, _draw_splice_fan

# ── connection expansion ────────────────────────────────────────────────────


def _expand_connections(
    connections: list[WireSegment], pin: Pin, class_pin: Pin
) -> list[tuple[WireSegment, SpliceNode | None, WireSegment | None]]:
    """Expand splice connections into (incoming_seg, splice_or_None, outward_seg_or_None) tuples.

    Direct connections become [(seg, None, None)].
    A splice with N outward wires becomes N tuples [(seg, splice, out_seg), ...].
    A dead-end splice becomes [(seg, splice, None)].
    """
    result = []
    for seg in connections:
        remote = seg.end_b if (seg.end_a is pin or seg.end_a is class_pin) else seg.end_a
        if isinstance(remote, SpliceNode):
            outward = [s for s in remote._connections if s is not seg]
            if outward:
                for out_seg in outward:
                    result.append((seg, remote, out_seg))
            else:
                result.append((seg, remote, None))
        else:
            result.append((seg, None, None))
    return result


# ── jumper helper ───────────────────────────────────────────────────────────


def _is_jumper(pin: Pin, remote: Pin) -> bool:
    """True when both pins live in the same connector (or same component for direct pins)."""
    if pin._connector is not None:
        return pin._connector is remote._connector
    if pin._component is not None:
        return pin._component is remote._component and remote._connector is None
    return False


# ── wire connection drawing ─────────────────────────────────────────────────


def _draw_connection(
    dwg: svgwrite.Drawing,
    seg: WireSegment,
    remote,
    wx: float,
    cy: float,
    class_pin: Pin,
    harness: Harness,
    shield: ShieldGroup | None,
    min_term_cx: float = 0,
    colored: bool = True,
    pin_shield_palette: dict | None = None,
) -> None:
    psp = pin_shield_palette or {}
    attrs = _wire_attrs(seg, psp, colored)

    if isinstance(remote, Terminal):
        label_text = _remote_label(remote, class_pin, harness)
        term_cx = (
            min_term_cx if min_term_cx > 0 else (wx + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        )
        term_cx = max(term_cx, wx + _WIRE_PAD + 20)
        wire_end = term_cx - 12
        dwg.add(dwg.line(start=(wx + _WIRE_PAD, cy), end=(wire_end, cy), **attrs))
        label_x1 = wx + _SHIELD_LEFT_CX + _SHIELD_RX if shield is not None else wx + _WIRE_PAD
        _draw_wire_label(dwg, seg, label_x1, wire_end, cy, psp, colored, harness=harness)
        _draw_terminal(dwg, remote, term_cx, cy)
        dwg.add(
            dwg.text(
                label_text,
                insert=(term_cx + 12, cy + 4),
                fill="#1e293b",
                font_size="9px",
                font_family="ui-monospace, monospace",
            )
        )
    elif isinstance(remote, Pin):
        wire_end = wx + _REMOTE_BOX_X - 4
        if shield is not None:
            lo_left = wx + _SHIELD_LEFT_CX - _SHIELD_RX
            lo_right = wx + _SHIELD_LEFT_CX + _SHIELD_RX
            if shield.single_oval:
                for x1, x2 in [(wx + _WIRE_PAD, lo_left), (lo_right, wire_end)]:
                    if x2 > x1:
                        dwg.add(dwg.line(start=(x1, cy), end=(x2, cy), **attrs))
                _draw_wire_label(dwg, seg, lo_right, wire_end, cy, psp, colored, harness=harness)
            else:
                ro_left = wx + _SHIELD_RIGHT_CX - _SHIELD_RX
                ro_right = wx + _SHIELD_RIGHT_CX + _SHIELD_RX
                for x1, x2 in [(wx + _WIRE_PAD, lo_left), (lo_right, ro_left), (ro_right, wire_end)]:
                    if x2 > x1:
                        dwg.add(dwg.line(start=(x1, cy), end=(x2, cy), **attrs))
                _draw_wire_label(dwg, seg, lo_right, ro_left, cy, psp, colored, harness=harness)
        else:
            dwg.add(dwg.line(start=(wx + _WIRE_PAD, cy), end=(wire_end, cy), **attrs))
            _draw_wire_label(dwg, seg, wx + _WIRE_PAD, wire_end, cy, psp, colored, harness=harness)
    else:
        label_x = wx + _REMOTE_BOX_X
        dwg.add(dwg.line(start=(wx + _WIRE_PAD, cy), end=(label_x - 4, cy), **attrs))
        _draw_wire_label(dwg, seg, wx + _WIRE_PAD, label_x - 4, cy, psp, colored, harness=harness)
        dwg.add(
            dwg.text(
                _remote_label(remote, class_pin, harness),
                insert=(label_x, cy + 4),
                fill="#1e293b",
                font_size="9px",
                font_family="ui-monospace, monospace",
            )
        )


# ── remote component boxes ─────────────────────────────────────────────────


def _draw_remote_box(dwg: svgwrite.Drawing, group: PinGroup, harness: Harness) -> None:
    rows = group.rows
    if not rows:
        return

    wx = rows[0].wire_start_x
    y_top = rows[0].rect.y
    y_bot = rows[-1].rect.y + rows[-1].rect.h
    box_x = wx + _REMOTE_BOX_X
    box_h = y_bot - y_top

    comp_label = ""
    conn_name = ""
    row_remotes: list[Pin | None] = []

    for row in rows:
        use_pin = row.pin if row.pin._connections else row.class_pin
        rpin: Pin | None = None
        if use_pin._connections:
            seg = use_pin._connections[0]
            remote = (
                seg.end_b if (seg.end_a is use_pin or seg.end_a is row.pin or seg.end_a is row.class_pin) else seg.end_a
            )
            if isinstance(remote, Pin):
                rpin = remote
                if not comp_label:
                    comp_label = _pin_comp_label(remote, harness)
                if not conn_name and remote._connector_class is not None:
                    conn_name = remote._connector_class._connector_name
        row_remotes.append(rpin)

    if not any(p is not None for p in row_remotes):
        return

    header = comp_label
    if conn_name:
        header += f" · {conn_name}"
    if header:
        dwg.add(
            dwg.text(
                header,
                insert=(box_x + 4, y_top - 3),
                fill="#1e3a5f",
                font_size="8px",
                font_weight="bold",
                font_family="ui-monospace, monospace",
            )
        )

    dwg.add(
        dwg.rect(
            insert=(box_x, y_top),
            size=(_REMOTE_BOX_W, box_h),
            rx=3,
            ry=3,
            fill="#eff6ff",
            stroke="#93c5fd",
            stroke_width=1,
        )
    )
    dwg.add(
        dwg.line(
            start=(box_x + _REMOTE_BOX_PIN_NUM_W, y_top),
            end=(box_x + _REMOTE_BOX_PIN_NUM_W, y_bot),
            stroke="#93c5fd",
            stroke_width=0.5,
        )
    )

    for i, (row, rpin) in enumerate(zip(rows, row_remotes)):
        cy = row.rect.y + row.rect.h / 2
        if rpin is not None:
            dwg.add(
                dwg.text(
                    str(rpin.number),
                    insert=(box_x + _REMOTE_BOX_PIN_NUM_W / 2, cy + 4),
                    text_anchor="middle",
                    fill="#64748b",
                    font_size="10px",
                    font_family="ui-monospace, monospace",
                )
            )
            dwg.add(
                dwg.text(
                    rpin.signal_name,
                    insert=(box_x + _REMOTE_BOX_PIN_NUM_W + 5, cy + 4),
                    fill="#1e293b",
                    font_size="9px",
                    font_family="ui-monospace, monospace",
                )
            )
        if i < len(rows) - 1:
            div_y = row.rect.y + row.rect.h
            dwg.add(
                dwg.line(
                    start=(box_x, div_y),
                    end=(box_x + _REMOTE_BOX_W, div_y),
                    stroke="#bfdbfe",
                    stroke_width=0.5,
                )
            )


# ── pin row ────────────────────────────────────────────────────────────────


def _draw_pin_row(
    dwg: svgwrite.Drawing,
    row_info: PinRowInfo,
    harness: Harness,
    shield: ShieldGroup | None,
    min_term_cx: float = 0,
    colored: bool = True,
    pin_shield_palette: dict | None = None,
    jumper_stubs: dict | None = None,
) -> None:
    rect = row_info.rect
    pin = row_info.pin
    class_pin = row_info.class_pin
    cy = rect.y + rect.h / 2

    dwg.add(
        dwg.rect(
            insert=(rect.x, rect.y),
            size=(rect.w, rect.h),
            fill="#ffffff",
            stroke="#e2e8f0",
            stroke_width=0.5,
        )
    )

    name_x = rect.x + PIN_NUM_W
    wire_x = row_info.wire_start_x

    for lx in [name_x, wire_x]:
        dwg.add(dwg.line(start=(lx, rect.y), end=(lx, rect.y + rect.h), stroke="#cbd5e1", stroke_width=0.5))

    dwg.add(
        dwg.text(
            str(pin.number),
            insert=(rect.x + PIN_NUM_W / 2, cy + 4),
            text_anchor="middle",
            fill="#64748b",
            font_size="10px",
            font_family="ui-monospace, monospace",
        )
    )
    dwg.add(
        dwg.text(
            pin.signal_name,
            insert=(name_x + 6, cy + 4),
            fill="#1e293b",
            font_size="10px",
            font_family="ui-monospace, monospace",
        )
    )

    connections = list(pin._connections) if pin._connections else list(class_pin._connections)

    if not connections:
        _draw_unconnected(dwg, wire_x, cy)
        return

    psp = pin_shield_palette or {}
    expanded = _expand_connections(connections, pin, class_pin)

    first_splice = expanded[0][1] if expanded else None
    if first_splice is not None and all(sp is first_splice for _, sp, _ in expanded):
        _draw_splice_fan(dwg, expanded, wire_x, rect, class_pin, harness, min_term_cx, colored, psp)
    else:
        row_h = rect.h / max(len(expanded), 1)
        for i, (seg, splice, out_seg) in enumerate(expanded):
            line_y = rect.y + row_h * (i + 0.5)
            if splice is not None:
                _draw_splice_connection(
                    dwg, seg, splice, out_seg, wire_x, line_y, class_pin, harness, min_term_cx, colored, psp
                )
            else:
                remote = seg.end_b if (seg.end_a is class_pin or seg.end_a is pin) else seg.end_a
                if isinstance(remote, Pin) and _is_jumper(pin, remote):
                    attrs = _wire_attrs(seg, psp, colored)
                    dwg.add(
                        dwg.line(start=(wire_x + _WIRE_PAD, line_y), end=(wire_x + _JUMPER_STUB_X, line_y), **attrs)
                    )
                    _draw_wire_label(
                        dwg, seg, wire_x + _WIRE_PAD, wire_x + _JUMPER_STUB_X, line_y, psp, colored, harness=harness
                    )
                    if jumper_stubs is not None:
                        entry = jumper_stubs.setdefault(id(seg), [seg, wire_x, []])
                        entry[2].append(line_y)
                else:
                    _draw_connection(
                        dwg, seg, remote, wire_x, line_y, class_pin, harness, shield, min_term_cx, colored, psp
                    )
