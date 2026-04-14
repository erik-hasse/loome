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

# Wire color palette
_POWER_STROKE = "#dc2626"  # red — connected to fuse or CB
_GROUND_STROKE = "#111111"  # black — connected to ground
_WHITE_STROKE = "#9ca3af"  # medium gray — represents "white" wire
# Shielded pairs cycle through: White (gray), White-Blue (dashed), White-Orange (dashed)
_SHIELD_PALETTE: list[tuple[str, str | None]] = [
    (_WHITE_STROKE, None),
    ("#3b82f6", "5,3"),
    ("#f97316", "5,3"),
]
# Explicit WireColor code → SVG stroke value
_EXPLICIT_COLORS: dict[str, str] = {
    "W": _WHITE_STROKE,
    "R": _POWER_STROKE,
    "B": _GROUND_STROKE,
    "N": _GROUND_STROKE,
    "BL": "#3b82f6",
    "OR": "#f97316",
    "Y": "#eab308",
    "GN": "#16a34a",
    "GR": "#6b7280",
    "PK": "#ec4899",
    "VT": "#8b5cf6",
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

# Splice symbol position (relative to wire_start_x)
_SPLICE_CX = 50  # center x of the X symbol
_SPLICE_FAN_X = 70  # x where fan diagonals end and outward horizontals begin


def _wire_attrs(
    seg: WireSegment,
    pin_shield_palette: dict[int, tuple[str, str | None]],
    colored: bool,
) -> dict:
    """Return SVG stroke keyword args for a wire segment.

    Priority: uncolored → explicit color → power (fuse/CB) → ground → shielded → white.
    """
    if not colored:
        return {"stroke": "#222222", "stroke_width": 1.5}

    # Explicit WireColor set by the user always wins
    if seg.color and seg.color in _EXPLICIT_COLORS:
        return {"stroke": _EXPLICIT_COLORS[seg.color], "stroke_width": 1.5}

    if isinstance(seg.end_a, (Fuse, CircuitBreaker)) or isinstance(seg.end_b, (Fuse, CircuitBreaker)):
        return {"stroke": _POWER_STROKE, "stroke_width": 1.5}

    if isinstance(seg.end_a, GroundSymbol) or isinstance(seg.end_b, GroundSymbol):
        return {"stroke": _GROUND_STROKE, "stroke_width": 1.5}

    for endpoint in (seg.end_a, seg.end_b):
        if isinstance(endpoint, Pin):
            palette = pin_shield_palette.get(id(endpoint))
            if palette is not None:
                stroke, dash = palette
                attrs: dict = {"stroke": stroke, "stroke_width": 1.5}
                if dash:
                    attrs["stroke_dasharray"] = dash
                return attrs

    return {"stroke": _WHITE_STROKE, "stroke_width": 1.5}


def _incoming_splice_attrs(
    seg: WireSegment,
    splice: SpliceNode,
    out_segs: list[WireSegment | None],
    psp: dict,
    colored: bool,
) -> dict:
    """Color for the wire leading INTO a splice, propagated from outward connections.

    Explicit color on the incoming segment is still honored. Otherwise the
    highest-priority outward destination wins: fuse/CB > ground > auto.
    """
    if not colored:
        return {"stroke": "#222222", "stroke_width": 1.5}

    if seg.color and seg.color in _EXPLICIT_COLORS:
        return {"stroke": _EXPLICIT_COLORS[seg.color], "stroke_width": 1.5}

    for out_seg in out_segs:
        if out_seg is None:
            continue
        remote = out_seg.end_b if out_seg.end_a is splice else out_seg.end_a
        if isinstance(remote, (Fuse, CircuitBreaker)):
            return {"stroke": _POWER_STROKE, "stroke_width": 1.5}

    for out_seg in out_segs:
        if out_seg is None:
            continue
        remote = out_seg.end_b if out_seg.end_a is splice else out_seg.end_a
        if isinstance(remote, GroundSymbol):
            return {"stroke": _GROUND_STROKE, "stroke_width": 1.5}

    return _wire_attrs(seg, psp, colored)


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


def _compute_min_term_cx(layout: LayoutResult, harness: Harness) -> float:
    """Return the smallest terminal-symbol cx across all terminal connections.

    Scans both direct pin→terminal connections and pin→splice→terminal paths
    so all symbols align to the same column regardless of how they're reached.
    """
    min_cx = float("inf")

    def _check(label_text: str, wire_start_x: float) -> None:
        nonlocal min_cx
        cx = wire_start_x + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W
        min_cx = min(min_cx, cx)

    # Direct pin → terminal
    for group in layout.pin_groups:
        if group.target_key[0] != "terminal":
            continue
        for row in group.rows:
            use_pin = row.pin if row.pin._connections else row.class_pin
            if not use_pin._connections:
                continue
            seg = use_pin._connections[0]
            remote = (
                seg.end_b if (seg.end_a is use_pin or seg.end_a is row.pin or seg.end_a is row.class_pin) else seg.end_a
            )
            if not isinstance(remote, (GroundSymbol, OffPageReference, Fuse, CircuitBreaker)):
                continue
            _check(_remote_label(remote, row.class_pin, harness), row.wire_start_x)

    # Pin → splice → terminal
    if layout.pin_rows:
        wire_start_x = next(iter(layout.pin_rows.values())).wire_start_x
        for splice in harness.splice_nodes:
            for seg in splice._connections:
                remote = seg.end_b if seg.end_a is splice else seg.end_a
                if isinstance(remote, GroundSymbol):
                    _check(remote.label, wire_start_x)
                elif isinstance(remote, OffPageReference):
                    _check(remote.label or remote.id, wire_start_x)
                elif isinstance(remote, (Fuse, CircuitBreaker)):
                    _check(f"{remote.name} {remote.amps}A", wire_start_x)

    return min_cx if min_cx != float("inf") else 0


def render(harness: Harness, layout: LayoutResult, output_path: str | Path, colored: bool = True) -> None:
    # Build shield palette lookup: pin id → (stroke, dasharray or None)
    pin_shield_palette: dict[int, tuple[str, str | None]] = {}
    for sg in harness.shield_groups:
        for idx, p in enumerate(sg.pins):
            pin_shield_palette[id(p)] = _SHIELD_PALETTE[min(idx, len(_SHIELD_PALETTE) - 1)]

    # Two pin→row lookups: by class-pin ID and by instance-pin ID.
    # class_pin_to_row maps to the LAST row seen for that class pin; use
    # class_pin_to_rows (plural) when you need all instances sharing a class pin.
    class_pin_to_row: dict[int, PinRowInfo] = {id(ri.class_pin): ri for ri in layout.pin_rows.values()}
    inst_pin_to_row: dict[int, PinRowInfo] = {id(ri.pin): ri for ri in layout.pin_rows.values()}
    class_pin_to_rows: dict[int, list[PinRowInfo]] = {}
    for ri in layout.pin_rows.values():
        class_pin_to_rows.setdefault(id(ri.class_pin), []).append(ri)

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
            _draw_pin_row(dwg, row_info, harness, shield, min_term_cx, colored, pin_shield_palette)

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
                _draw_pin_row(dwg, row_info, harness, shield, min_term_cx, colored, pin_shield_palette)

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
        # Source-side ovals: group by component instance so that multiple
        # instances sharing the same class pin each get their own oval pair.
        source_by_inst: dict[int, list[PinRowInfo]] = {}
        for p in sg.pins:
            for ri in class_pin_to_rows.get(id(p), []):
                inst_key = id(ri.pin._component) if ri.pin._component is not None else id(ri.pin)
                source_by_inst.setdefault(inst_key, []).append(ri)
        for inst_rows in source_by_inst.values():
            _draw_shield_ovals(dwg, inst_rows, sg.label)

        # Remote-side ovals: group by SOURCE instance (not the remote component)
        # so that two instances of the same component (e.g. roll_trim / pitch_trim)
        # that both connect into the same remote component (GEA24) each get their
        # own oval covering only their own subset of pins.
        remote_rows_by_source: dict[int, list[PinRowInfo]] = {}

        def _add_remote_for_source(src_pin: Pin, source_key: int) -> None:
            for seg in src_pin._connections:
                remote = seg.end_b if seg.end_a is src_pin else seg.end_a
                if not isinstance(remote, Pin):
                    continue
                row = _find_row(remote)
                if row is not None:
                    remote_rows_by_source.setdefault(source_key, []).append(row)

        for p in sg.pins:
            _add_remote_for_source(p, id(sg))  # class-level: all sg pins share one key
            for ri in class_pin_to_rows.get(id(p), []):
                source_key = id(ri.pin._component) if ri.pin._component is not None else id(ri.pin)
                _add_remote_for_source(ri.pin, source_key)  # instance-level: one key per instance

        for rows in remote_rows_by_source.values():
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
    colored: bool = True,
    pin_shield_palette: dict | None = None,
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

    psp = pin_shield_palette or {}
    expanded = _expand_connections(connections, pin, class_pin)

    # When every expanded entry goes through the same splice, draw a single
    # junction with fan lines.  Fall back to per-row drawing for mixed cases.
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
                _draw_connection(
                    dwg, seg, remote, wire_x, line_y, class_pin, harness, shield, min_term_cx, colored, psp
                )


def _draw_splice_fan(
    dwg: svgwrite.Drawing,
    expanded: list[tuple],
    wx: float,
    rect,
    class_pin: Pin,
    harness: Harness,
    min_term_cx: float = 0,
    colored: bool = True,
    pin_shield_palette: dict | None = None,
) -> None:
    """Draw a splice as one incoming wire → X junction → diagonal fan legs."""
    psp = pin_shield_palette or {}
    n = len(expanded)
    row_h = rect.h / n
    center_y = rect.y + rect.h / 2
    splice_cx = wx + _SPLICE_CX
    fan_x = wx + _SPLICE_FAN_X

    incoming_seg, splice, _ = expanded[0]
    out_segs = [out_seg for _, _, out_seg in expanded]
    # One dominant color for every wire in this splice node: if any outward leg
    # reaches a fuse/CB or ground, ALL legs inherit that color.
    splice_attrs = _incoming_splice_attrs(incoming_seg, splice, out_segs, psp, colored)

    # Single incoming wire to the junction
    dwg.add(
        dwg.line(
            start=(wx + _WIRE_PAD, center_y),
            end=(splice_cx - 6, center_y),
            **splice_attrs,
        )
    )
    _draw_wire_label(dwg, incoming_seg, wx + _WIRE_PAD, splice_cx - 6, center_y)

    _draw_splice_symbol(dwg, splice_cx, center_y)

    # Fan: one diagonal leg per outward connection
    for i, (seg, sp, out_seg) in enumerate(expanded):
        sub_y = rect.y + row_h * (i + 0.5)
        leg_attrs = splice_attrs  # all legs share the splice's dominant color

        # Diagonal from junction to fan_x at sub_y — uses the outward leg's color
        dwg.add(
            dwg.line(
                start=(splice_cx + 5, center_y),
                end=(fan_x, sub_y),
                **leg_attrs,
            )
        )

        if out_seg is None:
            label = sp.label or sp.id
            dwg.add(
                dwg.text(
                    label,
                    insert=(fan_x + 4, sub_y + 4),
                    fill="#94a3b8",
                    font_size="9px",
                    font_family="ui-monospace, monospace",
                )
            )
            continue

        out_remote = out_seg.end_b if out_seg.end_a is splice else out_seg.end_a

        if isinstance(out_remote, (GroundSymbol, OffPageReference, Fuse, CircuitBreaker)):
            label_text = _remote_label(out_remote, class_pin, harness)
            term_cx = (
                min_term_cx
                if min_term_cx > 0
                else (wx + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
            )
            term_cx = max(term_cx, fan_x + 20)
            wire_end = term_cx - 12
            dwg.add(dwg.line(start=(fan_x, sub_y), end=(wire_end, sub_y), **leg_attrs))
            _draw_wire_label(dwg, out_seg, fan_x, wire_end, sub_y)
            _draw_terminal(dwg, out_remote, term_cx, sub_y)
            dwg.add(
                dwg.text(
                    label_text,
                    insert=(term_cx + 12, sub_y + 4),
                    fill="#1e293b",
                    font_size="9px",
                    font_family="ui-monospace, monospace",
                )
            )
        elif isinstance(out_remote, Pin):
            wire_end = wx + _REMOTE_BOX_X - 4
            dwg.add(dwg.line(start=(fan_x, sub_y), end=(wire_end, sub_y), **leg_attrs))
            _draw_wire_label(dwg, out_seg, fan_x, wire_end, sub_y)
            ref = _remote_label(out_remote, class_pin, harness)
            dwg.add(
                dwg.text(
                    ref,
                    insert=(wx + _REMOTE_BOX_X + 4, sub_y + 4),
                    fill="#1e3a5f",
                    font_size="9px",
                    font_family="ui-monospace, monospace",
                )
            )
        else:
            wire_end = wx + _REMOTE_BOX_X - 4
            dwg.add(dwg.line(start=(fan_x, sub_y), end=(wire_end, sub_y), **leg_attrs))
            _draw_wire_label(dwg, out_seg, fan_x, wire_end, sub_y)
            dwg.add(
                dwg.text(
                    _remote_label(out_remote, class_pin, harness),
                    insert=(wx + _REMOTE_BOX_X, sub_y + 4),
                    fill="#1e293b",
                    font_size="9px",
                    font_family="ui-monospace, monospace",
                )
            )


def _draw_splice_symbol(dwg: svgwrite.Drawing, cx: float, cy: float) -> None:
    r = 4
    dwg.add(dwg.line(start=(cx - r, cy - r), end=(cx + r, cy + r), stroke="#475569", stroke_width=1.5))
    dwg.add(dwg.line(start=(cx + r, cy - r), end=(cx - r, cy + r), stroke="#475569", stroke_width=1.5))


def _draw_splice_connection(
    dwg: svgwrite.Drawing,
    incoming_seg: WireSegment,
    splice: SpliceNode,
    out_seg: WireSegment | None,
    wx: float,
    cy: float,
    class_pin: Pin,
    harness: Harness,
    min_term_cx: float = 0,
    colored: bool = True,
    pin_shield_palette: dict | None = None,
) -> None:
    psp = pin_shield_palette or {}
    splice_cx = wx + _SPLICE_CX
    in_attrs = _incoming_splice_attrs(incoming_seg, splice, [out_seg], psp, colored)

    # Incoming wire from pin to splice symbol
    dwg.add(dwg.line(start=(wx + _WIRE_PAD, cy), end=(splice_cx - 6, cy), **in_attrs))
    _draw_wire_label(dwg, incoming_seg, wx + _WIRE_PAD, splice_cx - 6, cy)

    _draw_splice_symbol(dwg, splice_cx, cy)

    if out_seg is None:
        # Dead-end splice: show splice id/label as annotation
        label = splice.label or splice.id
        dwg.add(
            dwg.text(
                label,
                insert=(splice_cx + 10, cy + 4),
                fill="#94a3b8",
                font_size="9px",
                font_family="ui-monospace, monospace",
            )
        )
        return

    out_start = splice_cx + 6
    out_remote = out_seg.end_b if out_seg.end_a is splice else out_seg.end_a
    out_attrs = in_attrs  # all legs share the splice's dominant color

    if isinstance(out_remote, (GroundSymbol, OffPageReference, Fuse, CircuitBreaker)):
        label_text = _remote_label(out_remote, class_pin, harness)
        term_cx = (
            min_term_cx if min_term_cx > 0 else (wx + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        )
        term_cx = max(term_cx, out_start + 20)
        wire_end = term_cx - 12
        dwg.add(dwg.line(start=(out_start, cy), end=(wire_end, cy), **out_attrs))
        _draw_wire_label(dwg, out_seg, out_start, wire_end, cy)
        _draw_terminal(dwg, out_remote, term_cx, cy)
        dwg.add(
            dwg.text(
                label_text,
                insert=(term_cx + 12, cy + 4),
                fill="#1e293b",
                font_size="9px",
                font_family="ui-monospace, monospace",
            )
        )
    elif isinstance(out_remote, Pin):
        wire_end = wx + _REMOTE_BOX_X - 4
        dwg.add(dwg.line(start=(out_start, cy), end=(wire_end, cy), **out_attrs))
        _draw_wire_label(dwg, out_seg, out_start, wire_end, cy)
        dwg.add(
            dwg.text(
                _remote_label(out_remote, class_pin, harness),
                insert=(wx + _REMOTE_BOX_X + 4, cy + 4),
                fill="#1e3a5f",
                font_size="9px",
                font_family="ui-monospace, monospace",
            )
        )
    else:
        # Nested splice or other unknown endpoint
        wire_end = wx + _REMOTE_BOX_X - 4
        dwg.add(dwg.line(start=(out_start, cy), end=(wire_end, cy), **out_attrs))
        _draw_wire_label(dwg, out_seg, out_start, wire_end, cy)
        dwg.add(
            dwg.text(
                _remote_label(out_remote, class_pin, harness),
                insert=(wx + _REMOTE_BOX_X, cy + 4),
                fill="#1e293b",
                font_size="9px",
                font_family="ui-monospace, monospace",
            )
        )


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
    colored: bool = True,
    pin_shield_palette: dict | None = None,
) -> None:
    attrs = _wire_attrs(seg, pin_shield_palette or {}, colored)
    is_terminal = isinstance(remote, (GroundSymbol, OffPageReference, Fuse, CircuitBreaker))

    if is_terminal:
        label_text = _remote_label(remote, class_pin, harness)
        # Use the globally pre-computed minimum so all terminal symbols align.
        term_cx = (
            min_term_cx if min_term_cx > 0 else (wx + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        )
        term_cx = max(term_cx, wx + _WIRE_PAD + 20)
        wire_end = term_cx - 12
        dwg.add(dwg.line(start=(wx + _WIRE_PAD, cy), end=(wire_end, cy), **attrs))
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
                    dwg.add(dwg.line(start=(x1, cy), end=(x2, cy), **attrs))
            _draw_wire_label(dwg, seg, lo_right, ro_left, cy)
        else:
            dwg.add(dwg.line(start=(wx + _WIRE_PAD, cy), end=(wire_end, cy), **attrs))
            _draw_wire_label(dwg, seg, wx + _WIRE_PAD, wire_end, cy)
    else:
        # SpliceNode or other — keep text label
        label_x = wx + _REMOTE_BOX_X
        dwg.add(dwg.line(start=(wx + _WIRE_PAD, cy), end=(label_x - 4, cy), **attrs))
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
                    comp_label = _pin_comp_label(remote, harness)
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


def _comp_label(comp_cls: type | None, harness: Harness) -> str:
    if comp_cls is None:
        return "?"
    for comp in harness.components:
        if type(comp) is comp_cls:
            return comp.label
    return comp_cls.__name__


def _pin_comp_label(pin: Pin, harness: Harness) -> str:
    """Return the component label for a pin, using the instance reference when available."""
    comp = getattr(pin, "_component", None)
    if comp is not None:
        return comp.label
    return _comp_label(pin._component_class, harness)
