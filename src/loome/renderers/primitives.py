from __future__ import annotations

import drawsvg as draw

from ..harness import Harness
from ..layout.engine import COMPONENT_HEADER_H, CONNECTOR_HEADER_H, PIN_NUM_W, PinRowInfo
from ..model import (
    BusBar,
    CircuitBreaker,
    Fuse,
    GroundSymbol,
    OffPageReference,
    Pin,
    SpliceNode,
    Terminal,
    WireSegment,
)
from .colors import _effective_color_code

# X offsets within the wire column (relative to wire_start_x)
_WIRE_PAD = 6  # gap before wire begins
_SHIELD_LEFT_CX = 40  # center x of left shield oval
_SHIELD_RIGHT_CX = 322  # center x of right shield oval (just inside _REMOTE_BOX_X)
_SHIELD_RX = 7  # half-width of each oval
_MONO_CHAR_W = 5.4  # estimated px width of one monospace char at 9px
_TERM_SYMBOL_W = 22  # px from wire end to symbol center (gap + half symbol width)
_CAN_TERM_BOX_W = 18  # width of the spanning TERM box
_CAN_TERM_BOX_CX = _WIRE_PAD + _CAN_TERM_BOX_W // 2  # box center, left-justified in wire area (= 15)
_CAN_TERM_WIRE_START = _WIRE_PAD + _CAN_TERM_BOX_W + 4  # wire start for terminated pins (= 28)
_CAN_TERM_SHIELD_SHIFT = _CAN_TERM_WIRE_START - _WIRE_PAD  # how far right the shield moves (= 22)

# Remote component box (drawn to the right of the wire / shield area)
_REMOTE_BOX_X = 340  # left edge of box, relative to wire_start_x
_REMOTE_BOX_W = 140  # box width  (ends at 480 / 500)
_REMOTE_BOX_PIN_NUM_W = 26  # width of the pin-number column inside box

# Splice symbol position (relative to wire_start_x)
_SPLICE_CX = 80  # center x of the X symbol
_SPLICE_FAN_X = 100  # x where fan diagonals end and outward horizontals begin

# Multi-direct-connection bullet position (relative to wire_start_x).
# Sits BEFORE the left shield oval so the bullet visually appears outside the
# shielded bundle, with branches dropping below to additional rows.
_BULLET_CX = 22

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
    if isinstance(remote, SpliceNode):
        return remote.label or remote.id
    if isinstance(remote, (Fuse, CircuitBreaker)):
        block = harness.block_label_for(remote)
        base = remote.display_name()
        return f"{block} · {base}" if block else base
    if isinstance(remote, Terminal):
        return remote.display_name()
    return "[–]"


# ── atomic drawing primitives ──────────────────────────────────────────────


def _draw_wire_label(
    dwg: draw.Drawing,
    seg: WireSegment,
    x1: float,
    x2: float,
    cy: float,
    psp: dict | None = None,
    colored: bool = True,
    color_code_override: str | None = None,
    harness: Harness | None = None,
) -> None:
    color_code = (
        color_code_override if color_code_override is not None else _effective_color_code(seg, psp or {}, colored)
    )
    parts = [p for p in [seg.wire_id, str(seg.gauge) if seg.gauge else "", color_code] if p]
    label = "".join(parts)
    length_str = harness.format_wire_length(seg) if harness is not None else ""
    if length_str:
        label = f"{label} / {length_str}" if label else length_str
    # Place label just inside the left edge of the segment. For shielded wires
    # x1 is already lo_right (just past the left oval), so this stays clear of the ovals.
    label_x = x1 + 4
    if label:
        dwg.append(
            draw.Text(
                label,
                7,
                label_x,
                cy - 3,
                fill="#94a3b8",
                font_family="ui-monospace, monospace",
            )
        )
    if seg.notes:
        dwg.append(
            draw.Text(
                seg.notes,
                9,
                label_x,
                cy + 9,
                fill="#475569",
                font_style="italic",
                font_family="ui-monospace, monospace",
            )
        )


def _draw_splice_symbol(dwg: draw.Drawing, cx: float, cy: float) -> None:
    r = 4
    dwg.append(draw.Line(cx - r, cy - r, cx + r, cy + r, stroke="#475569", stroke_width=1.5))
    dwg.append(draw.Line(cx + r, cy - r, cx - r, cy + r, stroke="#475569", stroke_width=1.5))


def _draw_bullet(dwg: draw.Drawing, cx: float, cy: float) -> None:
    """Filled dot marking a junction where one pin's wire branches to multiple destinations."""
    dwg.append(draw.Circle(cx, cy, 3.5, fill="#334155", stroke="#334155"))


def _draw_wire_around_ovals(
    dwg: draw.Drawing,
    x1: float,
    x2: float,
    cy: float,
    wx: float,
    shield,
    attrs: dict,
) -> None:
    """Draw a horizontal wire from x1→x2 at cy, breaking around shield ovals.

    When ``shield`` is None, draws one line. Otherwise skips the x-span(s)
    occupied by the left oval (and the right oval, unless ``shield.single_oval``)
    so the wire visually enters/exits each oval instead of passing through it.
    """
    if shield is None or x2 <= x1:
        if x2 > x1:
            dwg.append(draw.Line(x1, cy, x2, cy, **attrs))
        return

    spans: list[tuple[float, float]] = []
    lo_l = wx + _SHIELD_LEFT_CX - _SHIELD_RX
    lo_r = wx + _SHIELD_LEFT_CX + _SHIELD_RX
    if lo_l < x2 and lo_r > x1:
        spans.append((lo_l, lo_r))
    if not shield.single_oval:
        ro_l = wx + _SHIELD_RIGHT_CX - _SHIELD_RX
        ro_r = wx + _SHIELD_RIGHT_CX + _SHIELD_RX
        if ro_l < x2 and ro_r > x1:
            spans.append((ro_l, ro_r))

    cursor = x1
    for span_l, span_r in spans:
        if span_l > cursor:
            dwg.append(draw.Line(cursor, cy, span_l, cy, **attrs))
        cursor = max(cursor, span_r)
    if cursor < x2:
        dwg.append(draw.Line(cursor, cy, x2, cy, **attrs))


def _draw_unconnected(dwg: draw.Drawing, wx: float, cy: float) -> None:
    dwg.append(
        draw.Line(
            wx + _WIRE_PAD,
            cy,
            wx + _REMOTE_BOX_X - 4,
            cy,
            stroke="#cbd5e1",
            stroke_width=1,
            stroke_dasharray="4,3",
        )
    )
    dwg.append(
        draw.Text(
            "[–]",
            9,
            wx + _REMOTE_BOX_X,
            cy + 4,
            fill="#94a3b8",
            font_family="ui-monospace, monospace",
        )
    )


def _draw_terminal(dwg: draw.Drawing, remote: Terminal, x: float, y: float) -> None:
    """Draw the terminal's symbol at (x, y). Dispatched on concrete subclass.

    Extension point: new Terminal subclasses add a case here (and can be
    exported from the public API without touching layout or wire drawing).
    """
    if isinstance(remote, GroundSymbol):
        if remote.filled:
            dwg.append(
                draw.Lines(
                    x,
                    y + 10,
                    x - 7,
                    y - 2,
                    x + 7,
                    y - 2,
                    close=True,
                    fill="#334155",
                    stroke="#334155",
                    stroke_width=1,
                )
            )
        else:
            stem_end = y + 4
            dwg.append(draw.Line(x, y - 2, x, stem_end, stroke="#475569", stroke_width=1))
            dwg.append(
                draw.Lines(
                    x - 5,
                    stem_end,
                    x + 5,
                    stem_end,
                    x,
                    stem_end + 8,
                    close=True,
                    fill="white",
                    stroke="#475569",
                    stroke_width=1,
                )
            )
    elif isinstance(remote, BusBar):
        dwg.append(
            draw.Rectangle(
                x - 10,
                y - 3,
                20,
                6,
                fill="#1e293b",
                stroke="#1e293b",
                stroke_width=1,
            )
        )
    elif isinstance(remote, OffPageReference):
        dwg.append(
            draw.Lines(
                x - 7,
                y - 5,
                x + 2,
                y - 5,
                x + 8,
                y,
                x + 2,
                y + 5,
                x - 7,
                y + 5,
                close=True,
                fill="#dcfce7",
                stroke="#166534",
                stroke_width=1,
            )
        )
    elif isinstance(remote, Fuse):
        dwg.append(
            draw.Rectangle(
                x - 9,
                y - 5,
                18,
                10,
                rx=2,
                fill="#fef9c3",
                stroke="#a16207",
                stroke_width=1.5,
            )
        )
        dwg.append(draw.Line(x - 5, y, x + 5, y, stroke="#a16207", stroke_width=1.5))
    elif isinstance(remote, CircuitBreaker):
        dwg.append(
            draw.Rectangle(
                x - 9,
                y - 5,
                18,
                10,
                rx=2,
                fill="#fff7ed",
                stroke="#c2410c",
                stroke_width=1.5,
            )
        )
        dwg.append(draw.Line(x - 4, y + 4, x + 4, y - 4, stroke="#c2410c", stroke_width=1.5))


def _draw_can_term_box(dwg: draw.Drawing, cx: float, y_top: float, y_bot: float) -> None:
    """Draw a single spanning TERM box for a CAN bus termination point."""
    h = y_bot - y_top
    mid_y = (y_top + y_bot) / 2
    dwg.append(
        draw.Rectangle(
            cx - _CAN_TERM_BOX_W / 2,
            y_top,
            _CAN_TERM_BOX_W,
            h,
            rx=2,
            fill="#f0fdf4",
            stroke="#166534",
            stroke_width=1.5,
        )
    )
    dwg.append(
        draw.Text(
            "TERM",
            7,
            cx,
            mid_y + 2,
            text_anchor="middle",
            fill="#166534",
            font_weight="bold",
            font_family="ui-monospace, monospace",
            transform=f"rotate(90, {cx}, {mid_y})",
        )
    )


# ── section / connector chrome ─────────────────────────────────────────────


def _draw_section_bg(dwg: draw.Drawing, rect, label: str) -> None:
    dwg.append(draw.Rectangle(rect.x, rect.y, rect.w, rect.h, rx=6, fill="#f8fafc", stroke="none"))
    # Dark header wrapped in a sticky group so it can float with the viewport.
    g = draw.Group(id=f"sh-comp-{int(rect.y)}")
    g.append(draw.Rectangle(rect.x, rect.y, rect.w, COMPONENT_HEADER_H, rx=6, fill="#334155"))
    g.append(draw.Rectangle(rect.x, rect.y + COMPONENT_HEADER_H - 6, rect.w, 6, fill="#334155"))
    g.append(
        draw.Text(
            label,
            13,
            rect.x + 12,
            rect.y + COMPONENT_HEADER_H - 8,
            fill="white",
            font_weight="bold",
            font_family="ui-monospace, monospace",
        )
    )
    dwg.append(g)


def _draw_connector_header(dwg: draw.Drawing, rect, conn_name: str) -> None:
    g = draw.Group(id=f"sh-conn-{int(rect.y)}")
    g.append(
        draw.Rectangle(
            rect.x,
            rect.y,
            rect.w,
            CONNECTOR_HEADER_H,
            fill="#dbeafe",
            stroke="#93c5fd",
            stroke_width=1,
        )
    )
    mid_y = rect.y + CONNECTOR_HEADER_H - 7
    g.append(
        draw.Text(
            "#",
            10,
            rect.x + PIN_NUM_W / 2,
            mid_y,
            text_anchor="middle",
            fill="#1e3a5f",
            font_family="ui-monospace, monospace",
        )
    )
    g.append(
        draw.Text(
            conn_name,
            10,
            rect.x + PIN_NUM_W + 6,
            mid_y,
            fill="#1e3a5f",
            font_weight="bold",
            font_family="ui-monospace, monospace",
        )
    )
    dwg.append(g)


# ── shield ovals ────────────────────────────────────────────────────────────


def _draw_shield_ovals(
    dwg: draw.Drawing,
    rows: list[PinRowInfo],
    label: str,
    drain_label: str = "",
    drain_remote_label: str = "",
    single_oval: bool = False,
    x_offset: float = 0,
) -> None:
    wx = rows[0].wire_start_x
    y_top = min(r.rect.y for r in rows)
    y_bot = max(r.rect.y + r.rect.h for r in rows)
    cy = (y_top + y_bot) / 2
    ry = (y_bot - y_top) / 2 + 2
    oval_bottom = cy + ry

    left_cx = _SHIELD_LEFT_CX + x_offset
    cx_offsets = [left_cx] if single_oval else [left_cx, _SHIELD_RIGHT_CX]
    for cx_off in cx_offsets:
        dwg.append(
            draw.Ellipse(
                wx + cx_off,
                cy,
                _SHIELD_RX,
                ry,
                fill="#f1f5f9",
                stroke="#475569",
                stroke_width=1,
            )
        )

    if label:
        dwg.append(
            draw.Text(
                label,
                8,
                wx + _SHIELD_RIGHT_CX,
                y_top - 2,
                text_anchor="middle",
                fill="#475569",
                font_weight="bold",
                font_family="ui-monospace, monospace",
            )
        )

    # Ground symbol: stem + open downward triangle.
    # drain_label → left oval (source/component-proximal side)
    # drain_remote_label → right oval (remote/cable-exit side)
    for cx_off, dlabel in ((left_cx, drain_label), (_SHIELD_RIGHT_CX, drain_remote_label)):
        if not dlabel:
            continue
        tx = wx + cx_off
        stem_end = oval_bottom + 4
        tri_h = 8
        dwg.append(draw.Line(tx, oval_bottom, tx, stem_end, stroke="#475569", stroke_width=1))
        dwg.append(
            draw.Lines(
                tx - 5,
                stem_end,
                tx + 5,
                stem_end,
                tx,
                stem_end + tri_h,
                close=True,
                fill="white",
                stroke="#475569",
                stroke_width=1,
            )
        )
