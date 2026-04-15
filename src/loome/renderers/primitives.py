from __future__ import annotations

import svgwrite

from ..layout.engine import COMPONENT_HEADER_H, CONNECTOR_HEADER_H, PIN_NUM_W, PinRowInfo
from ..model import (
    CircuitBreaker,
    Fuse,
    GroundSymbol,
    Harness,
    OffPageReference,
    Pin,
    SpliceNode,
    WireSegment,
)
from .colors import _effective_color_code

# X offsets within the wire column (relative to wire_start_x)
_WIRE_PAD = 6  # gap before wire begins
_SHIELD_LEFT_CX = 40  # center x of left shield oval
_SHIELD_RIGHT_CX = 130  # center x of right shield oval
_SHIELD_RX = 7  # half-width of each oval
_MONO_CHAR_W = 5.4  # estimated px width of one monospace char at 9px
_TERM_SYMBOL_W = 22  # px from wire end to symbol center (gap + half symbol width)

# Remote component box (drawn to the right of the wire / shield area)
_REMOTE_BOX_X = 148  # left edge of box, relative to wire_start_x
_REMOTE_BOX_W = 140  # box width  (ends at 288 / 300)
_REMOTE_BOX_PIN_NUM_W = 26  # width of the pin-number column inside box

# Splice symbol position (relative to wire_start_x)
_SPLICE_CX = 80  # center x of the X symbol
_SPLICE_FAN_X = 100  # x where fan diagonals end and outward horizontals begin

# Jumper connections (both pins in the same connector)
_JUMPER_STUB_X = 40  # how far the horizontal stub extends before the vertical bar


# ── label helpers ──────────────────────────────────────────────────────────


def _comp_label(comp_cls: type | None, harness: Harness) -> str:
    if comp_cls is None:
        return "?"
    for comp in harness.components:
        if type(comp) is comp_cls:
            return comp.label
    return comp_cls.__name__


def _pin_comp_label(pin: Pin, harness: Harness) -> str:
    comp = getattr(pin, "_component", None)
    if comp is not None:
        return comp.label
    return _comp_label(pin._component_class, harness)


def _remote_label(remote, class_pin: Pin, harness: Harness) -> str:
    if isinstance(remote, Pin):
        comp_label = _pin_comp_label(remote, harness)
        if remote._connector_class is not None:
            conn_name = remote._connector_class._connector_name
            return f"{comp_label} {conn_name}.{remote.number}"
        return f"{comp_label}.{remote.number}"
    elif isinstance(remote, SpliceNode):
        return remote.label or remote.id
    elif isinstance(remote, GroundSymbol):
        return remote.label
    elif isinstance(remote, OffPageReference):
        return remote.label or remote.id
    elif isinstance(remote, (Fuse, CircuitBreaker)):
        return f"{remote.name} {remote.amps}A"
    return "[–]"


# ── atomic drawing primitives ──────────────────────────────────────────────


def _draw_wire_label(
    dwg: svgwrite.Drawing,
    seg: WireSegment,
    x1: float,
    x2: float,
    cy: float,
    psp: dict | None = None,
    colored: bool = True,
    color_code_override: str | None = None,
) -> None:
    color_code = (
        color_code_override if color_code_override is not None else _effective_color_code(seg, psp or {}, colored)
    )
    parts = [p for p in [seg.wire_id, str(seg.gauge) if seg.gauge else "", color_code] if p]
    label = "".join(parts)
    # Place label just inside the left edge of the segment. For shielded wires
    # x1 is already lo_right (just past the left oval), so this stays clear of the ovals.
    label_x = x1 + 4
    if label:
        dwg.add(
            dwg.text(
                label,
                insert=(label_x, cy - 3),
                fill="#94a3b8",
                font_size="7px",
                font_family="ui-monospace, monospace",
            )
        )
    if seg.notes:
        dwg.add(
            dwg.text(
                seg.notes,
                insert=(label_x, cy + 8),
                fill="#94a3b8",
                font_size="7px",
                font_style="italic",
                font_family="ui-monospace, monospace",
            )
        )


def _draw_splice_symbol(dwg: svgwrite.Drawing, cx: float, cy: float) -> None:
    r = 4
    dwg.add(dwg.line(start=(cx - r, cy - r), end=(cx + r, cy + r), stroke="#475569", stroke_width=1.5))
    dwg.add(dwg.line(start=(cx + r, cy - r), end=(cx - r, cy + r), stroke="#475569", stroke_width=1.5))


def _draw_unconnected(dwg: svgwrite.Drawing, wx: float, cy: float) -> None:
    dwg.add(
        dwg.line(
            start=(wx + _WIRE_PAD, cy),
            end=(wx + _REMOTE_BOX_X - 4, cy),
            stroke="#cbd5e1",
            stroke_width=1,
            stroke_dasharray="4,3",
        )
    )
    dwg.add(
        dwg.text(
            "[–]",
            insert=(wx + _REMOTE_BOX_X, cy + 4),
            fill="#94a3b8",
            font_size="9px",
            font_family="ui-monospace, monospace",
        )
    )


def _draw_terminal(dwg: svgwrite.Drawing, remote, x: float, y: float) -> None:
    if isinstance(remote, GroundSymbol):
        pts = [(x, y + 10), (x - 7, y - 2), (x + 7, y - 2)]
        dwg.add(dwg.polygon(points=pts, fill="#334155", stroke="#334155", stroke_width=1))
    elif isinstance(remote, OffPageReference):
        pts = [(x - 7, y - 5), (x + 2, y - 5), (x + 8, y), (x + 2, y + 5), (x - 7, y + 5)]
        dwg.add(dwg.polygon(points=pts, fill="#dcfce7", stroke="#166534", stroke_width=1))
    elif isinstance(remote, Fuse):
        dwg.add(
            dwg.rect(
                insert=(x - 9, y - 5),
                size=(18, 10),
                rx=2,
                ry=2,
                fill="#fef9c3",
                stroke="#a16207",
                stroke_width=1.5,
            )
        )
        dwg.add(dwg.line(start=(x - 5, y), end=(x + 5, y), stroke="#a16207", stroke_width=1.5))
    elif isinstance(remote, CircuitBreaker):
        dwg.add(
            dwg.rect(
                insert=(x - 9, y - 5),
                size=(18, 10),
                rx=2,
                ry=2,
                fill="#fff7ed",
                stroke="#c2410c",
                stroke_width=1.5,
            )
        )
        dwg.add(dwg.line(start=(x - 4, y + 4), end=(x + 4, y - 4), stroke="#c2410c", stroke_width=1.5))


# ── section / connector chrome ─────────────────────────────────────────────


def _draw_section_bg(dwg: svgwrite.Drawing, rect, label: str) -> None:
    dwg.add(dwg.rect(insert=(rect.x, rect.y), size=(rect.w, rect.h), rx=6, ry=6, fill="#f8fafc", stroke="none"))
    # Dark header with rounded top corners; square rect fills in the rounded bottom corners.
    dwg.add(dwg.rect(insert=(rect.x, rect.y), size=(rect.w, COMPONENT_HEADER_H), rx=6, ry=6, fill="#334155"))
    dwg.add(dwg.rect(insert=(rect.x, rect.y + COMPONENT_HEADER_H - 6), size=(rect.w, 6), fill="#334155"))
    dwg.add(
        dwg.text(
            label,
            insert=(rect.x + 12, rect.y + COMPONENT_HEADER_H - 8),
            fill="white",
            font_size="13px",
            font_weight="bold",
            font_family="ui-monospace, monospace",
        )
    )


def _draw_connector_header(dwg: svgwrite.Drawing, rect, conn_name: str) -> None:
    dwg.add(
        dwg.rect(
            insert=(rect.x, rect.y),
            size=(rect.w, CONNECTOR_HEADER_H),
            fill="#dbeafe",
            stroke="#93c5fd",
            stroke_width=1,
        )
    )
    mid_y = rect.y + CONNECTOR_HEADER_H - 7
    dwg.add(
        dwg.text(
            "#",
            insert=(rect.x + PIN_NUM_W / 2, mid_y),
            text_anchor="middle",
            fill="#1e3a5f",
            font_size="10px",
            font_family="ui-monospace, monospace",
        )
    )
    dwg.add(
        dwg.text(
            conn_name,
            insert=(rect.x + PIN_NUM_W + 6, mid_y),
            fill="#1e3a5f",
            font_size="10px",
            font_weight="bold",
            font_family="ui-monospace, monospace",
        )
    )


# ── shield ovals ────────────────────────────────────────────────────────────


def _draw_shield_ovals(dwg: svgwrite.Drawing, rows: list[PinRowInfo], label: str) -> None:
    wx = rows[0].wire_start_x
    y_top = min(r.rect.y for r in rows)
    y_bot = max(r.rect.y + r.rect.h for r in rows)
    cy = (y_top + y_bot) / 2
    ry = (y_bot - y_top) / 2 + 2

    for cx_off in (_SHIELD_LEFT_CX, _SHIELD_RIGHT_CX):
        dwg.add(
            dwg.ellipse(
                center=(wx + cx_off, cy),
                r=(_SHIELD_RX, ry),
                fill="#f1f5f9",
                stroke="#475569",
                stroke_width=1,
            )
        )

    if label:
        dwg.add(
            dwg.text(
                label,
                insert=(wx + _SHIELD_RIGHT_CX, y_top - 2),
                text_anchor="middle",
                fill="#475569",
                font_size="8px",
                font_weight="bold",
                font_family="ui-monospace, monospace",
            )
        )
