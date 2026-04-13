from __future__ import annotations

from pathlib import Path

import svgwrite

from ..layout.engine import (
    COMPONENT_HEADER_H,
    CONNECTOR_HEADER_H,
    PIN_NUM_W,
    WIRE_AREA_W,
    LayoutResult,
    PinGroup,
    PinRowInfo,
)
from ..model import (
    CircuitBreaker,
    Fuse,
    GroundSymbol,
    Harness,
    OffPageReference,
    Pin,
    ShieldGroup,
    SpliceNode,
    WireSegment,
)

WIRE_COLORS: dict[str, str] = {
    "N": "#888888",
    "W": "#d0d0d0",
    "": "#222222",
}

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


def _wire_color(seg: WireSegment) -> str:
    return WIRE_COLORS.get(seg.color, "#222222")


def _compute_min_term_cx(layout: LayoutResult, harness: Harness) -> float:
    """Return the smallest terminal-symbol cx across all terminal connections.

    Using the minimum means every wire is as short as the one with the longest
    label, keeping all symbols and labels in a single aligned column.
    """
    min_cx = float("inf")
    for group in layout.pin_groups:
        if group.target_key[0] != "terminal":
            continue
        for row in group.rows:
            use_pin = row.pin if row.pin._connections else row.class_pin
            if not use_pin._connections:
                continue
            seg = use_pin._connections[0]
            if seg.end_a is use_pin or seg.end_a is row.pin or seg.end_a is row.class_pin:
                remote = seg.end_b
            else:
                remote = seg.end_a
            if not isinstance(remote, (GroundSymbol, OffPageReference, Fuse, CircuitBreaker)):
                continue
            label_text = _remote_label(remote, row.class_pin, harness)
            label_right = row.wire_start_x + WIRE_AREA_W - 4
            cx = label_right - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W
            min_cx = min(min_cx, cx)
    return min_cx if min_cx != float("inf") else 0


def render(harness: Harness, layout: LayoutResult, output_path: str | Path) -> None:
    # Two pin→row lookups: by class-pin ID and by instance-pin ID.
    class_pin_to_row: dict[int, PinRowInfo] = {id(ri.class_pin): ri for ri in layout.pin_rows.values()}
    inst_pin_to_row: dict[int, PinRowInfo] = {id(ri.pin): ri for ri in layout.pin_rows.values()}

    def _find_row(pin: Pin) -> PinRowInfo | None:
        return class_pin_to_row.get(id(pin)) or inst_pin_to_row.get(id(pin))

    # Build shield lookup keyed by pin ID.  Include both the source pins (class-
    # level, named in the ShieldGroup) and the remote pins reachable via their
    # connections.  For remote instance pins we also add the corresponding class
    # pin so the shield renders correctly on both sides of the cable.
    shield_by_pin: dict[int, ShieldGroup] = {}
    for sg in harness.shield_groups:
        for p in sg.pins:
            shield_by_pin[id(p)] = sg
            for seg in p._connections:
                remote = seg.end_b if seg.end_a is p else seg.end_a
                if isinstance(remote, Pin):
                    shield_by_pin[id(remote)] = sg
                    # Also register the class-pin so the lookup by class_pin works
                    row = inst_pin_to_row.get(id(remote))
                    if row:
                        shield_by_pin[id(row.class_pin)] = sg

    # Pre-pass: find the minimum terminal-symbol cx across every terminal connection
    # so all wires + symbols align to a single column.
    min_term_cx = _compute_min_term_cx(layout, harness)

    dwg = svgwrite.Drawing(
        str(output_path),
        size=(layout.canvas_width, layout.canvas_height),
        profile="full",
    )
    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))

    for comp in harness.components:
        sect_rect = layout.section_rects[id(comp)]
        _draw_section_bg(dwg, sect_rect, comp.label)

        # Direct pins (no connector header)
        for attr_name, inst_pin in comp._direct_pins.items():
            row_info = layout.pin_rows.get(id(inst_pin))
            if row_info is None:
                continue
            shield = shield_by_pin.get(id(row_info.class_pin))
            _draw_pin_row(dwg, row_info, harness, shield, min_term_cx)

        for conn_name, conn in comp._connectors.items():
            conn_rect = layout.connector_rects[id(conn)]
            _draw_connector_header(dwg, conn_rect, conn_name)

            for attr_name, inst_pin in vars(conn).items():
                if not isinstance(inst_pin, Pin):
                    continue
                row_info = layout.pin_rows.get(id(inst_pin))
                if row_info is None:
                    continue
                shield = shield_by_pin.get(id(row_info.class_pin))
                _draw_pin_row(dwg, row_info, harness, shield, min_term_cx)

        # Draw the section border stroke AFTER content so it sits on top
        # of the pin row fills, keeping the rounded corners clean.
        dwg.add(
            dwg.rect(
                insert=(sect_rect.x, sect_rect.y),
                size=(sect_rect.w, sect_rect.h),
                rx=6,
                ry=6,
                fill="none",
                stroke="#334155",
                stroke_width=2,
            )
        )

    # ── shield ovals (drawn after all rows, on top of wire lines) ──────────
    for sg in harness.shield_groups:
        source_rows = [class_pin_to_row[id(p)] for p in sg.pins if id(p) in class_pin_to_row]
        if source_rows:
            _draw_shield_ovals(dwg, source_rows, sg.label)

        # Discover remote pins grouped by their component class
        remote_rows_by_comp: dict[int, list[PinRowInfo]] = {}
        for p in sg.pins:
            for seg in p._connections:
                remote = seg.end_b if seg.end_a is p else seg.end_a
                if isinstance(remote, Pin) and remote._component_class is not None:
                    row = _find_row(remote)
                    if row is not None:
                        key = id(remote._component_class)
                        remote_rows_by_comp.setdefault(key, []).append(row)

        for rows in remote_rows_by_comp.values():
            _draw_shield_ovals(dwg, rows, sg.label)

    # ── remote component boxes ──────────────────────────────────────────────
    for group in layout.pin_groups:
        if group.target_key[0] == "component":
            _draw_remote_box(dwg, group, harness)

    dwg.save()


# ── section / connector chrome ─────────────────────────────────────────────


def _draw_section_bg(dwg: svgwrite.Drawing, rect, label: str) -> None:
    dwg.add(
        dwg.rect(
            insert=(rect.x, rect.y),
            size=(rect.w, rect.h),
            rx=6,
            ry=6,
            fill="#f8fafc",
            stroke="none",
        )
    )
    # Dark header with rounded top corners matching the section background.
    # The square rect below it fills in the rounded bottom corners of the header.
    dwg.add(
        dwg.rect(
            insert=(rect.x, rect.y),
            size=(rect.w, COMPONENT_HEADER_H),
            rx=6,
            ry=6,
            fill="#334155",
        )
    )
    dwg.add(
        dwg.rect(
            insert=(rect.x, rect.y + COMPONENT_HEADER_H - 6),
            size=(rect.w, 6),
            fill="#334155",
        )
    )
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


# ── pin row ────────────────────────────────────────────────────────────────


def _draw_pin_row(
    dwg: svgwrite.Drawing,
    row_info: PinRowInfo,
    harness: Harness,
    shield: ShieldGroup | None,
    min_term_cx: float = 0,
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
        dwg.add(
            dwg.line(
                start=(lx, rect.y),
                end=(lx, rect.y + rect.h),
                stroke="#cbd5e1",
                stroke_width=0.5,
            )
        )

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

    # Instance-level connections override class-level (for multi-instance components).
    if pin._connections:
        connections: list[WireSegment] = list(pin._connections)
    else:
        connections = list(class_pin._connections)

    if not connections:
        _draw_unconnected(dwg, wire_x, cy)
        return

    row_h = rect.h / max(len(connections), 1)
    for i, seg in enumerate(connections):
        line_y = rect.y + row_h * (i + 0.5)
        remote = seg.end_b if (seg.end_a is class_pin or seg.end_a is pin) else seg.end_a
        _draw_connection(dwg, seg, remote, wire_x, line_y, class_pin, harness, shield, min_term_cx)


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
) -> None:
    stroke = _wire_color(seg)
    is_terminal = isinstance(remote, (GroundSymbol, OffPageReference, Fuse, CircuitBreaker))

    if is_terminal:
        label_text = _remote_label(remote, class_pin, harness)
        # Use the globally pre-computed minimum so all terminal symbols align.
        term_cx = (
            min_term_cx if min_term_cx > 0 else (wx + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        )
        term_cx = max(term_cx, wx + _WIRE_PAD + 20)
        wire_end = term_cx - 12
        dwg.add(
            dwg.line(
                start=(wx + _WIRE_PAD, cy),
                end=(wire_end, cy),
                stroke=stroke,
                stroke_width=1.5,
            )
        )
        _draw_wire_label(dwg, seg, wx + _WIRE_PAD, wire_end, cy)
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
        # Wire runs to the left edge of the remote box; the box itself is drawn later.
        wire_end = wx + _REMOTE_BOX_X - 4
        if shield is not None:
            lo_left = wx + _SHIELD_LEFT_CX - _SHIELD_RX
            lo_right = wx + _SHIELD_LEFT_CX + _SHIELD_RX
            ro_left = wx + _SHIELD_RIGHT_CX - _SHIELD_RX
            ro_right = wx + _SHIELD_RIGHT_CX + _SHIELD_RX
            for x1, x2 in [(wx + _WIRE_PAD, lo_left), (lo_right, ro_left), (ro_right, wire_end)]:
                if x2 > x1:
                    dwg.add(
                        dwg.line(
                            start=(x1, cy),
                            end=(x2, cy),
                            stroke=stroke,
                            stroke_width=1.5,
                        )
                    )
            _draw_wire_label(dwg, seg, lo_right, ro_left, cy)
        else:
            dwg.add(
                dwg.line(
                    start=(wx + _WIRE_PAD, cy),
                    end=(wire_end, cy),
                    stroke=stroke,
                    stroke_width=1.5,
                )
            )
            _draw_wire_label(dwg, seg, wx + _WIRE_PAD, wire_end, cy)
    else:
        # SpliceNode or other — keep text label
        label_x = wx + _REMOTE_BOX_X
        dwg.add(
            dwg.line(
                start=(wx + _WIRE_PAD, cy),
                end=(label_x - 4, cy),
                stroke=stroke,
                stroke_width=1.5,
            )
        )
        _draw_wire_label(dwg, seg, wx + _WIRE_PAD, label_x - 4, cy)
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


def _draw_remote_box(
    dwg: svgwrite.Drawing,
    group: PinGroup,
    harness: Harness,
) -> None:
    rows = group.rows
    if not rows:
        return

    wx = rows[0].wire_start_x
    y_top = rows[0].rect.y
    y_bot = rows[-1].rect.y + rows[-1].rect.h
    box_x = wx + _REMOTE_BOX_X
    box_h = y_bot - y_top

    # Collect the remote pin for each source row.
    # Prefer instance-pin connections (may differ from class-pin connections).
    comp_label = ""
    conn_name = ""
    row_remotes: list[Pin | None] = []

    for row in rows:
        use_pin = row.pin if row.pin._connections else row.class_pin
        rpin: Pin | None = None
        if use_pin._connections:
            seg = use_pin._connections[0]
            # The "far end" is whichever endpoint isn't us
            if seg.end_a is use_pin or seg.end_a is row.pin or seg.end_a is row.class_pin:
                remote = seg.end_b
            else:
                remote = seg.end_a
            if isinstance(remote, Pin):
                rpin = remote
                if not comp_label:
                    comp_label = _comp_label(remote._component_class, harness)
                if not conn_name and remote._connector_class is not None:
                    conn_name = remote._connector_class._connector_name
        row_remotes.append(rpin)

    if not any(p is not None for p in row_remotes):
        return

    # Small floating label above the box (fits in the GROUP_GAP)
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

    # Box background
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

    # Vertical divider between pin-number and signal-name columns
    dwg.add(
        dwg.line(
            start=(box_x + _REMOTE_BOX_PIN_NUM_W, y_top),
            end=(box_x + _REMOTE_BOX_PIN_NUM_W, y_bot),
            stroke="#93c5fd",
            stroke_width=0.5,
        )
    )

    # Per-row content
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
        # Row divider (between rows, not after last)
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


# ── shield ovals (drawn after all pin rows) ────────────────────────────────


def _draw_shield_ovals(dwg: svgwrite.Drawing, rows: list[PinRowInfo], label: str) -> None:
    wx = rows[0].wire_start_x
    y_top = min(r.rect.y for r in rows)
    y_bot = max(r.rect.y + r.rect.h for r in rows)
    cy = (y_top + y_bot) / 2
    ry = (y_bot - y_top) / 2 + 2  # slight vertical padding

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


# ── helpers ────────────────────────────────────────────────────────────────


def _draw_wire_label(dwg: svgwrite.Drawing, seg: WireSegment, x1: float, x2: float, cy: float) -> None:
    if seg.label:
        dwg.add(
            dwg.text(
                seg.label,
                insert=(x1 + (x2 - x1) * 0.25, cy - 3),
                fill="#94a3b8",
                font_size="7px",
                font_family="ui-monospace, monospace",
            )
        )


def _draw_terminal(dwg: svgwrite.Drawing, remote, x: float, y: float) -> None:
    if isinstance(remote, GroundSymbol):
        # Downward-pointing triangle (chassis ground)
        pts = [(x, y + 10), (x - 7, y - 2), (x + 7, y - 2)]
        dwg.add(
            dwg.polygon(
                points=pts,
                fill="#334155",
                stroke="#334155",
                stroke_width=1,
            )
        )
    elif isinstance(remote, OffPageReference):
        pts = [
            (x - 7, y - 5),
            (x + 2, y - 5),
            (x + 8, y),
            (x + 2, y + 5),
            (x - 7, y + 5),
        ]
        dwg.add(
            dwg.polygon(
                points=pts,
                fill="#dcfce7",
                stroke="#166534",
                stroke_width=1,
            )
        )
    elif isinstance(remote, Fuse):
        # Cartridge fuse: rectangle with a short line through the middle (IEC style)
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
        dwg.add(
            dwg.line(
                start=(x - 5, y),
                end=(x + 5, y),
                stroke="#a16207",
                stroke_width=1.5,
            )
        )
    elif isinstance(remote, CircuitBreaker):
        # Circuit breaker: rectangle with a diagonal trip indicator
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
        dwg.add(
            dwg.line(
                start=(x - 4, y + 4),
                end=(x + 4, y - 4),
                stroke="#c2410c",
                stroke_width=1.5,
            )
        )


def _remote_label(remote, class_pin: Pin, harness: Harness) -> str:
    if isinstance(remote, Pin):
        comp_label = _comp_label(remote._component_class, harness)
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


def _comp_label(comp_cls: type | None, harness: Harness) -> str:
    if comp_cls is None:
        return "?"
    for comp in harness.components:
        if type(comp) is comp_cls:
            return comp.label
    return comp_cls.__name__
