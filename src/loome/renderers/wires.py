from __future__ import annotations

import re

import svgwrite

from ..harness import Harness
from ..layout.engine import PIN_NUM_W, WIRE_AREA_W, PinGroup, PinRowInfo
from ..model import Pin, ShieldGroup, SpliceNode, Terminal, WireSegment
from .colors import _wire_attrs
from .primitives import (
    _BULLET_CX,
    _CAN_TERM_SHIELD_SHIFT,
    _CAN_TERM_WIRE_START,
    _JUMPER_STUB_X,
    _MONO_CHAR_W,
    _REMOTE_BOX_PIN_NUM_W,
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


def _pin_row_id(pin: Pin) -> str:
    """Return a stable SVG element ID for the left-side row of *pin*."""
    parts: list[str] = []
    if pin._component is not None:
        parts.append(pin._component.label)
    if pin._connector_class is not None:
        parts.append(pin._connector_class._connector_name)
    parts.append(str(pin.number))
    return "pr-" + re.sub(r"[^a-zA-Z0-9_-]", "_", "-".join(parts))


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
    start_x_offset: float = _WIRE_PAD,
    wire_end_x: float | None = None,
    shield_x_offset: float = 0,
) -> None:
    """Draw the leg of wire from ``wx + start_x_offset`` to the remote endpoint.

    Multi-direct-connection rows pass a larger ``start_x_offset`` so the leg
    begins at the bullet position instead of right at the pin column.
    """
    psp = pin_shield_palette or {}
    attrs = _wire_attrs(seg, psp, colored)
    start_x = wx + start_x_offset
    right_edge = wire_end_x if wire_end_x is not None else (wx + WIRE_AREA_W)

    if isinstance(remote, Terminal):
        label_text = _remote_label(remote, class_pin, harness)
        term_cx = min_term_cx if min_term_cx > 0 else (right_edge - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        term_cx = max(term_cx, start_x + 20)
        wire_end = term_cx - 12
        dwg.add(dwg.line(start=(start_x, cy), end=(wire_end, cy), **attrs))
        label_x1 = wx + _SHIELD_LEFT_CX + _SHIELD_RX + shield_x_offset if shield is not None else start_x
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
        dwg.add(dwg.line(start=(start_x, cy), end=(wire_end, cy), **attrs))
        if shield is not None:
            lo_right = wx + _SHIELD_LEFT_CX + _SHIELD_RX
            if shield.single_oval:
                _draw_wire_label(dwg, seg, lo_right, wire_end, cy, psp, colored, harness=harness)
            else:
                ro_left = wx + _SHIELD_RIGHT_CX - _SHIELD_RX
                _draw_wire_label(dwg, seg, lo_right, ro_left, cy, psp, colored, harness=harness)
        else:
            _draw_wire_label(dwg, seg, start_x, wire_end, cy, psp, colored, harness=harness)
    else:
        label_x = wx + _REMOTE_BOX_X
        dwg.add(dwg.line(start=(start_x, cy), end=(label_x - 4, cy), **attrs))
        _draw_wire_label(dwg, seg, start_x, label_x - 4, cy, psp, colored, harness=harness)
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
    remote_box_w: float,
    rendered_pin_ids: set[int] | None = None,
) -> None:
    rows = group.rows
    if not rows:
        return

    wx = rows[0].wire_start_x
    y_top = rows[0].rect.y
    y_bot = rows[-1].rect.y + rows[-1].rect.h
    box_x = wx + _REMOTE_BOX_X
    box_h = y_bot - y_top
    box_w = remote_box_w

    comp_label = ""
    conn_name = ""
    row_remotes: list[Pin | None] = []

    for row in rows:
        use_pin = row.pin if row.pin._connections else row.class_pin
        rpin: Pin | None = None
        # Per-leg row knows its segment directly. Fall back to first connection.
        seg = row.segment if row.segment is not None else (use_pin._connections[0] if use_pin._connections else None)
        if seg is not None:
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
            size=(box_w, box_h),
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
            if rendered_pin_ids is None or id(rpin) in rendered_pin_ids:
                target_id = _pin_row_id(rpin)
                link = dwg.a(
                    href=f"#{target_id}",
                    target="_self",
                    **{"class": "pin-link"},
                )
                link.add(
                    dwg.rect(
                        insert=(box_x, row.rect.y),
                        size=(box_w, row.rect.h),
                        fill="none",
                        **{"pointer-events": "all"},
                    )
                )
                dwg.add(link)
        if i < len(rows) - 1:
            div_y = row.rect.y + row.rect.h
            dwg.add(
                dwg.line(
                    start=(box_x, div_y),
                    end=(box_x + box_w, div_y),
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

    row_id = _pin_row_id(pin) if not row_info.is_continuation else None
    dwg.add(
        dwg.rect(
            insert=(rect.x, rect.y),
            size=(rect.w, rect.h),
            fill="#ffffff",
            stroke="#e2e8f0",
            stroke_width=0.5,
            **({"id": row_id} if row_id is not None else {}),
        )
    )

    name_x = rect.x + PIN_NUM_W
    wire_x = row_info.wire_start_x

    for lx in [name_x, wire_x]:
        dwg.add(dwg.line(start=(lx, rect.y), end=(lx, rect.y + rect.h), stroke="#cbd5e1", stroke_width=0.5))

    if not row_info.is_continuation:
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

    psp = pin_shield_palette or {}

    # ── Per-leg row path (multi-direct-connection or single direct) ──────────
    if row_info.segment is not None and not _segment_terminates_at_splice(row_info.segment, class_pin, pin):
        seg = row_info.segment
        remote = seg.end_b if (seg.end_a is class_pin or seg.end_a is pin) else seg.end_a

        is_primary = not row_info.is_continuation
        has_continuations = bool(row_info.continuation_rows)

        if is_primary and has_continuations:
            # Multi-direct-connection primary row: draw the pre-bullet stub
            # and the leg from bullet to remote here. The bullet glyph and
            # vertical drop are drawn in a deferred pass so they sit above
            # the continuation rows' backgrounds and the leg wire.
            bullet_cx = wire_x + _BULLET_CX
            attrs = _wire_attrs(seg, psp, colored)
            dwg.add(dwg.line(start=(wire_x + _WIRE_PAD, cy), end=(bullet_cx, cy), **attrs))
            if isinstance(remote, Pin) and _is_jumper(pin, remote):
                bar_x = wire_x + _JUMPER_STUB_X
                dwg.add(dwg.line(start=(bullet_cx, cy), end=(bar_x, cy), **attrs))
                _draw_wire_label(dwg, seg, bullet_cx, bar_x, cy, psp, colored, harness=harness)
                if jumper_stubs is not None:
                    entry = jumper_stubs.setdefault(id(seg), [seg, wire_x, bar_x, []])
                    entry[3].append(cy)
            else:
                _draw_connection(
                    dwg,
                    seg,
                    remote,
                    wire_x,
                    cy,
                    class_pin,
                    harness,
                    shield,
                    min_term_cx,
                    colored,
                    psp,
                    start_x_offset=_BULLET_CX,
                    wire_end_x=row_info.wire_end_x,
                )
            return

        if row_info.is_continuation:
            # Continuation: wire starts at bullet x; no pre-bullet stub, no
            # bullet glyph (already drawn by primary), no vertical drop.
            if isinstance(remote, Pin) and _is_jumper(pin, remote):
                # The bullet drop is the visual connector — no horizontal stub needed.
                # Record the PRIMARY row's cy so the bar terminates at the bullet,
                # not at the continuation placeholder below it.
                if jumper_stubs is not None:
                    bar_x = wire_x + _BULLET_CX
                    primary = row_info.primary_row
                    bar_cy = (primary.rect.y + primary.rect.h / 2) if primary is not None else cy
                    entry = jumper_stubs.setdefault(id(seg), [seg, wire_x, bar_x, []])
                    entry[3].append(bar_cy)
            else:
                _draw_connection(
                    dwg,
                    seg,
                    remote,
                    wire_x,
                    cy,
                    class_pin,
                    harness,
                    shield,
                    min_term_cx,
                    colored,
                    psp,
                    start_x_offset=_BULLET_CX,
                    wire_end_x=row_info.wire_end_x,
                )
            return

        # Primary, single direct connection — same visual as before.
        if isinstance(remote, Pin) and _is_jumper(pin, remote):
            attrs = _wire_attrs(seg, psp, colored)
            # When the other end is multi-direct it renders a bullet drop at
            # _BULLET_CX; meet that drop there instead of extending to _JUMPER_STUB_X.
            remote_is_multi = len(remote._connections) > 1
            bar_x = wire_x + (_BULLET_CX if remote_is_multi else _JUMPER_STUB_X)
            dwg.add(dwg.line(start=(wire_x + _WIRE_PAD, cy), end=(bar_x, cy), **attrs))
            _draw_wire_label(dwg, seg, wire_x + _WIRE_PAD, bar_x, cy, psp, colored, harness=harness)
            if jumper_stubs is not None:
                entry = jumper_stubs.setdefault(id(seg), [seg, wire_x, bar_x, []])
                entry[3].append(cy)
        else:
            terminated = pin._can_terminated
            _draw_connection(
                dwg,
                seg,
                remote,
                wire_x,
                cy,
                class_pin,
                harness,
                shield,
                min_term_cx,
                colored,
                psp,
                start_x_offset=_CAN_TERM_WIRE_START if terminated else _WIRE_PAD,
                wire_end_x=row_info.wire_end_x,
                shield_x_offset=_CAN_TERM_SHIELD_SHIFT if terminated else 0,
            )
        return

    # ── Legacy path: SpliceNode-mediated or unconnected ─────────────────────
    connections = list(pin._connections) if pin._connections else list(class_pin._connections)

    if not connections:
        _draw_unconnected(dwg, wire_x, cy)
        return

    expanded = _expand_connections(connections, pin, class_pin)

    first_splice = expanded[0][1] if expanded else None
    if first_splice is not None and all(sp is first_splice for _, sp, _ in expanded):
        _draw_splice_fan(
            dwg,
            expanded,
            wire_x,
            rect,
            class_pin,
            harness,
            min_term_cx,
            colored,
            psp,
            shield=shield,
            wire_end_x=row_info.wire_end_x,
        )
    else:
        row_h = rect.h / max(len(expanded), 1)
        for i, (seg, splice, out_seg) in enumerate(expanded):
            line_y = rect.y + row_h * (i + 0.5)
            if splice is not None:
                _draw_splice_connection(
                    dwg,
                    seg,
                    splice,
                    out_seg,
                    wire_x,
                    line_y,
                    class_pin,
                    harness,
                    min_term_cx,
                    colored,
                    psp,
                    shield=shield,
                    wire_end_x=row_info.wire_end_x,
                )
            else:
                remote = seg.end_b if (seg.end_a is class_pin or seg.end_a is pin) else seg.end_a
                if isinstance(remote, Pin) and _is_jumper(pin, remote):
                    attrs = _wire_attrs(seg, psp, colored)
                    remote_is_multi = len(remote._connections) > 1
                    bar_x = wire_x + (_BULLET_CX if remote_is_multi else _JUMPER_STUB_X)
                    dwg.add(dwg.line(start=(wire_x + _WIRE_PAD, line_y), end=(bar_x, line_y), **attrs))
                    _draw_wire_label(dwg, seg, wire_x + _WIRE_PAD, bar_x, line_y, psp, colored, harness=harness)
                    if jumper_stubs is not None:
                        entry = jumper_stubs.setdefault(id(seg), [seg, wire_x, bar_x, []])
                        entry[3].append(line_y)
                else:
                    _draw_connection(
                        dwg,
                        seg,
                        remote,
                        wire_x,
                        line_y,
                        class_pin,
                        harness,
                        shield,
                        min_term_cx,
                        colored,
                        psp,
                        wire_end_x=row_info.wire_end_x,
                    )


def _segment_terminates_at_splice(seg: WireSegment, class_pin: Pin, pin: Pin) -> bool:
    """True when this segment's *remote* end is a SpliceNode."""
    remote = seg.end_b if (seg.end_a is class_pin or seg.end_a is pin) else seg.end_a
    return isinstance(remote, SpliceNode)


def _draw_bullet_and_drop(
    dwg: svgwrite.Drawing,
    primary: PinRowInfo,
    colored: bool = True,
    pin_shield_palette: dict | None = None,
) -> tuple[float, float] | None:
    """Draw the drop lines for a multi-direct-connection bullet and return the bullet position.

    Returns ``(bullet_cx, cy)`` so the caller can draw the bullet glyph later,
    on top of any jumper bars that are rendered after this call. Returns None if
    there is nothing to draw.
    """
    if not primary.continuation_rows or primary.segment is None:
        return None
    psp = pin_shield_palette or {}
    cy = primary.rect.y + primary.rect.h / 2
    bullet_cx = primary.wire_start_x + _BULLET_CX
    # Draw the drop in segments, each colored by the continuation it feeds into.
    # Jumper continuations are skipped — the jumper bar (drawn from jumper_stubs)
    # already shows the connection going upward; no downward drop is needed.
    prev_y = cy
    for cont in primary.continuation_rows:
        cont_cy = cont.rect.y + cont.rect.h / 2
        if cont.segment is not None:
            remote = (
                cont.segment.end_b
                if (cont.segment.end_a is cont.class_pin or cont.segment.end_a is cont.pin)
                else cont.segment.end_a
            )
            if isinstance(remote, Pin) and _is_jumper(cont.pin, remote):
                prev_y = cont_cy
                continue
        seg_for_color = cont.segment if cont.segment is not None else primary.segment
        dwg.add(
            dwg.line(start=(bullet_cx, prev_y), end=(bullet_cx, cont_cy), **_wire_attrs(seg_for_color, psp, colored))
        )
        prev_y = cont_cy
    return bullet_cx, cy
