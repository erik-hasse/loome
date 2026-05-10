from __future__ import annotations

import re

import drawsvg as draw

from .._internal.endpoints import other_endpoint
from ..harness import Harness
from ..layout.engine import PIN_NUM_W, PIN_ROW_H, WIRE_AREA_W, PinGroup, PinRowInfo
from ..model import GroundSymbol, Pin, ShieldDrainTerminal, ShieldGroup, SpliceNode, Terminal, WireSegment
from .builder import run_key_for_segment
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
    _can_neighbor_info,
    _draw_terminal,
    _draw_unconnected,
    _draw_wire_label,
    _pin_comp_label,
    _remote_label,
)
from .splices import _draw_splice_connection, _draw_splice_fan

_DRAIN_PIN_COLOR = "#475569"  # same as block-drain triangle


class _AnchorLink(draw.DrawingParentElement):
    TAG_NAME = "a"


def _can_neighbor_link_target(local_pin: Pin | None, harness: Harness) -> str | None:
    """Return the SVG element id of the neighbor's CAN row to scroll to, or None.

    For an L pin (next-direction row), the target is the neighbor's H row
    (which points back at us via its prev direction); for an H pin, the
    target is the neighbor's L row. This way clicking always lands on the
    row that names the device you came from.
    """
    if local_pin is None or harness is None:
        return None
    info = _can_neighbor_info(local_pin, harness)
    if info is None:
        return None
    _bus, neighbor = info
    if neighbor is None:
        return None
    is_high = "high" in (local_pin.signal_name or "").lower()
    target_attr = "can_low" if is_high else "can_high"
    target_pin = getattr(neighbor, target_attr, None)
    if not isinstance(target_pin, Pin) or target_pin._component is None:
        return None
    return _pin_row_id(target_pin)


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
        remote = other_endpoint(seg, pin, class_pin)
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
    dwg: draw.Drawing,
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
    local_pin: Pin | None = None,
) -> None:
    """Draw the leg of wire from ``wx + start_x_offset`` to the remote endpoint.

    Multi-direct-connection rows pass a larger ``start_x_offset`` so the leg
    begins at the bullet position instead of right at the pin column.
    """
    psp = pin_shield_palette or {}
    attrs = _wire_attrs(seg, psp, colored)
    start_x = wx + start_x_offset
    right_edge = wire_end_x if wire_end_x is not None else (wx + WIRE_AREA_W)

    if isinstance(remote, ShieldDrainTerminal):
        # Draw only a short horizontal stub from wire start to left shield oval x.
        # The vertical connection from oval bottom to this row is drawn in svg.py.
        stub_end = wx + _SHIELD_LEFT_CX + shield_x_offset
        dwg.append(draw.Line(start_x, cy, stub_end, cy, stroke=_DRAIN_PIN_COLOR, stroke_width=1.5))
        return

    if isinstance(remote, Terminal):
        label_text = _remote_label(remote, class_pin, harness, local_pin=local_pin)
        if isinstance(remote, GroundSymbol) and remote.style == "open":
            # Local ground: place close to connector, similar to a jumper stub.
            term_cx = start_x + 30
        else:
            term_cx = (
                min_term_cx if min_term_cx > 0 else (right_edge - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
            )
            term_cx = max(term_cx, start_x + 20)
        # GroundSymbol drops downward from the wire, so the wire extends to term_cx.
        # Other terminals are sideways symbols that occupy the 12px gap before term_cx.
        wire_end = term_cx if isinstance(remote, GroundSymbol) else term_cx - 12
        dwg.append(draw.Line(start_x, cy, wire_end, cy, **attrs))
        label_x1 = wx + _SHIELD_LEFT_CX + _SHIELD_RX + shield_x_offset if shield is not None else start_x
        _draw_wire_label(dwg, seg, label_x1, wire_end, cy, psp, colored, harness=harness, local_pin=local_pin)
        _draw_terminal(dwg, remote, term_cx, cy)
        # Make CAN "To <neighbor>" labels clickable in the same way as remote
        # box pins: wrap the label text in an anchor pointing to the neighbor's
        # CAN H row. Falls back to a plain text node when there's no jump target.
        link_target = _can_neighbor_link_target(local_pin or class_pin, harness)
        label_node = draw.Text(
            label_text,
            9,
            term_cx + 12,
            cy + 4,
            fill="#1e293b",
            font_family="ui-monospace, monospace",
        )
        if link_target is not None:
            link = _AnchorLink(href=f"#{link_target}", target="_self", **{"class": "pin-link"})
            link.append(label_node)
            label_w = len(label_text) * _MONO_CHAR_W
            link.append(
                draw.Rectangle(
                    term_cx + 10,
                    cy - 7,
                    label_w + 6,
                    14,
                    fill="none",
                    **{"pointer-events": "all"},
                )
            )
            dwg.append(link)
        else:
            dwg.append(label_node)
    elif isinstance(remote, Pin):
        wire_end = wx + _REMOTE_BOX_X - 4
        dwg.append(draw.Line(start_x, cy, wire_end, cy, **attrs))
        if shield is not None:
            lo_right = wx + _SHIELD_LEFT_CX + _SHIELD_RX
            if shield.single_oval:
                _draw_wire_label(dwg, seg, lo_right, wire_end, cy, psp, colored, harness=harness, local_pin=local_pin)
            else:
                ro_left = wx + _SHIELD_RIGHT_CX - _SHIELD_RX
                _draw_wire_label(dwg, seg, lo_right, ro_left, cy, psp, colored, harness=harness, local_pin=local_pin)
        else:
            _draw_wire_label(dwg, seg, start_x, wire_end, cy, psp, colored, harness=harness, local_pin=local_pin)
    else:
        label_x = wx + _REMOTE_BOX_X
        dwg.append(draw.Line(start_x, cy, label_x - 4, cy, **attrs))
        _draw_wire_label(dwg, seg, start_x, label_x - 4, cy, psp, colored, harness=harness, local_pin=local_pin)
        dwg.append(
            draw.Text(
                _remote_label(remote, class_pin, harness),
                9,
                label_x,
                cy + 4,
                fill="#1e293b",
                font_family="ui-monospace, monospace",
            )
        )


# ── remote component boxes ─────────────────────────────────────────────────


def _draw_remote_box(
    dwg: draw.Drawing,
    group: PinGroup,
    harness: Harness,
    remote_box_w: float,
    rendered_pin_ids: set[int] | None = None,
    extra_drain_pins: list[Pin] | None = None,
) -> list[float]:
    """Draw the remote component box and return the cy of each drain pin row (if any)."""
    rows = group.rows
    if not rows:
        return []

    wx = rows[0].wire_start_x
    y_top = rows[0].rect.y
    y_bot = rows[-1].rect.y + rows[-1].rect.h
    box_x = wx + _REMOTE_BOX_X
    drain_rows_h = len(extra_drain_pins) * PIN_ROW_H if extra_drain_pins else 0
    box_h = y_bot - y_top + drain_rows_h
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
            remote = other_endpoint(seg, use_pin, row.pin, row.class_pin)
            if isinstance(remote, Pin):
                rpin = remote
                if not comp_label:
                    comp_label = _pin_comp_label(remote, harness)
                if not conn_name and remote._connector_class is not None:
                    conn_name = remote._connector_class._connector_name
        row_remotes.append(rpin)

    if not any(p is not None for p in row_remotes):
        return []

    header = comp_label
    if conn_name:
        header += f" · {conn_name}"
    if header:
        dwg.append(
            draw.Text(
                header,
                8,
                box_x + 4,
                y_top - 3,
                fill="#1e3a5f",
                font_weight="bold",
                font_family="ui-monospace, monospace",
            )
        )

    dwg.append(
        draw.Rectangle(
            box_x,
            y_top,
            box_w,
            box_h,
            rx=3,
            fill="#eff6ff",
            stroke="#93c5fd",
            stroke_width=1,
        )
    )
    dwg.append(
        draw.Line(
            box_x + _REMOTE_BOX_PIN_NUM_W,
            y_top,
            box_x + _REMOTE_BOX_PIN_NUM_W,
            y_bot + drain_rows_h,
            stroke="#93c5fd",
            stroke_width=0.5,
        )
    )

    for i, (row, rpin) in enumerate(zip(rows, row_remotes)):
        cy = row.rect.y + row.rect.h / 2
        if rpin is not None:
            dwg.append(
                draw.Text(
                    str(rpin.number),
                    10,
                    box_x + _REMOTE_BOX_PIN_NUM_W / 2,
                    cy + 4,
                    text_anchor="middle",
                    fill="#64748b",
                    font_family="ui-monospace, monospace",
                )
            )
            dwg.append(
                draw.Text(
                    rpin.signal_name,
                    9,
                    box_x + _REMOTE_BOX_PIN_NUM_W + 5,
                    cy + 4,
                    fill="#1e293b",
                    font_family="ui-monospace, monospace",
                )
            )
            if rendered_pin_ids is None or id(rpin) in rendered_pin_ids:
                target_id = _pin_row_id(rpin)
                seg = row.segment
                if seg is None:
                    use_pin = row.pin if row.pin._connections else row.class_pin
                    seg = use_pin._connections[0] if use_pin._connections else None
                run_key = run_key_for_segment(harness, seg, row.pin) if seg is not None else None
                link = _AnchorLink(
                    href=f"#{target_id}",
                    target="_self",
                    **{"class": "pin-link"},
                )
                link.append(
                    draw.Rectangle(
                        box_x,
                        row.rect.y,
                        box_w,
                        row.rect.h,
                        fill="none",
                        **({"data-seg-id": run_key, "class": "builder-wire"} if run_key is not None else {}),
                        **{"pointer-events": "all"},
                    )
                )
                dwg.append(link)
        if i < len(rows) - 1:
            div_y = row.rect.y + row.rect.h
            dwg.append(
                draw.Line(
                    box_x,
                    div_y,
                    box_x + box_w,
                    div_y,
                    stroke="#bfdbfe",
                    stroke_width=0.5,
                )
            )

    # Drain pin rows at the bottom.
    drain_cys: list[float] = []
    if extra_drain_pins:
        dwg.append(draw.Line(box_x, y_bot, box_x + box_w, y_bot, stroke="#bfdbfe", stroke_width=0.5))
        for j, dp in enumerate(extra_drain_pins):
            row_y = y_bot + j * PIN_ROW_H
            cy_dp = row_y + PIN_ROW_H / 2
            drain_cys.append(cy_dp)
            dwg.append(
                draw.Text(
                    str(dp.number),
                    10,
                    box_x + _REMOTE_BOX_PIN_NUM_W / 2,
                    cy_dp + 4,
                    text_anchor="middle",
                    fill="#64748b",
                    font_family="ui-monospace, monospace",
                )
            )
            dwg.append(
                draw.Text(
                    dp.signal_name,
                    9,
                    box_x + _REMOTE_BOX_PIN_NUM_W + 5,
                    cy_dp + 4,
                    fill="#1e293b",
                    font_family="ui-monospace, monospace",
                )
            )
            if rendered_pin_ids is None or id(dp) in rendered_pin_ids:
                target_id = _pin_row_id(dp)
                link = _AnchorLink(href=f"#{target_id}", target="_self", **{"class": "pin-link"})
                link.append(
                    draw.Rectangle(
                        box_x,
                        row_y,
                        box_w,
                        PIN_ROW_H,
                        fill="none",
                        **{"pointer-events": "all"},
                    )
                )
                dwg.append(link)
            if j < len(extra_drain_pins) - 1:
                dwg.append(
                    draw.Line(
                        box_x,
                        row_y + PIN_ROW_H,
                        box_x + box_w,
                        row_y + PIN_ROW_H,
                        stroke="#bfdbfe",
                        stroke_width=0.5,
                    )
                )
    return drain_cys


# ── pin row ────────────────────────────────────────────────────────────────


def _draw_pin_row(
    dwg: draw.Drawing,
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

    if rect.h == 0:
        # Zero-height jumper continuation: no visual row, but still record in jumper_stubs
        # so the bar connecting primary cy → target pin cy can be drawn.
        if row_info.is_continuation and row_info.segment is not None and jumper_stubs is not None:
            seg = row_info.segment
            remote = other_endpoint(seg, pin, class_pin)
            if isinstance(remote, Pin) and _is_jumper(pin, remote):
                bar_x = row_info.wire_start_x + _BULLET_CX
                primary = row_info.primary_row
                bar_cy = (primary.rect.y + primary.rect.h / 2) if primary is not None else cy
                entry = jumper_stubs.setdefault(id(seg), [seg, row_info.wire_start_x, bar_x, []])
                entry[3].append(bar_cy)
        return

    row_id = _pin_row_id(pin) if not row_info.is_continuation else None
    run_key = run_key_for_segment(harness, row_info.segment, pin) if row_info.segment is not None else None
    dwg.append(
        draw.Rectangle(
            rect.x,
            rect.y,
            rect.w,
            rect.h,
            fill="#ffffff",
            stroke="#e2e8f0",
            stroke_width=0.5,
            **({"id": row_id} if row_id is not None else {}),
            **({"data-seg-id": run_key, "class": "builder-wire"} if run_key is not None else {}),
        )
    )

    name_x = rect.x + PIN_NUM_W
    wire_x = row_info.wire_start_x

    for lx in [name_x, wire_x]:
        dwg.append(draw.Line(lx, rect.y, lx, rect.y + rect.h, stroke="#cbd5e1", stroke_width=0.5))

    if not row_info.is_continuation:
        dwg.append(
            draw.Text(
                str(pin.number),
                10,
                rect.x + PIN_NUM_W / 2,
                cy + 4,
                text_anchor="middle",
                fill="#64748b",
                font_family="ui-monospace, monospace",
            )
        )
        dwg.append(
            draw.Text(
                pin.signal_name,
                10,
                name_x + 6,
                cy + 4,
                fill="#1e293b",
                font_family="ui-monospace, monospace",
            )
        )

    psp = pin_shield_palette or {}

    # ── Per-leg row path (multi-direct-connection or single direct) ──────────
    if row_info.segment is not None and not _segment_terminates_at_splice(row_info.segment, class_pin, pin):
        seg = row_info.segment
        remote = other_endpoint(seg, pin, class_pin)

        is_primary = not row_info.is_continuation
        has_continuations = bool(row_info.continuation_rows)

        if is_primary and has_continuations:
            # Multi-direct-connection primary row: draw the pre-bullet stub
            # and the leg from bullet to remote here. The bullet glyph and
            # vertical drop are drawn in a deferred pass so they sit above
            # the continuation rows' backgrounds and the leg wire.
            bullet_cx = wire_x + _BULLET_CX
            attrs = _wire_attrs(seg, psp, colored)
            dwg.append(draw.Line(wire_x + _WIRE_PAD, cy, bullet_cx, cy, **attrs))
            if isinstance(remote, Pin) and _is_jumper(pin, remote):
                bar_x = wire_x + _JUMPER_STUB_X
                dwg.append(draw.Line(bullet_cx, cy, bar_x, cy, **attrs))
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
                    local_pin=pin,
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
                    local_pin=pin,
                )
            return

        # Primary, single direct connection — same visual as before.
        if isinstance(remote, Pin) and _is_jumper(pin, remote):
            attrs = _wire_attrs(seg, psp, colored)
            # When the other end is multi-direct it renders a bullet drop at
            # _BULLET_CX; meet that drop there instead of extending to _JUMPER_STUB_X.
            remote_is_multi = len(remote._connections) > 1
            bar_x = wire_x + (_BULLET_CX if remote_is_multi else _JUMPER_STUB_X)
            dwg.append(draw.Line(wire_x + _WIRE_PAD, cy, bar_x, cy, **attrs))
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
                local_pin=pin,
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
            local_pin=pin,
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
                    local_pin=pin,
                )
            else:
                remote = other_endpoint(seg, pin, class_pin)
                if isinstance(remote, Pin) and _is_jumper(pin, remote):
                    attrs = _wire_attrs(seg, psp, colored)
                    remote_is_multi = len(remote._connections) > 1
                    bar_x = wire_x + (_BULLET_CX if remote_is_multi else _JUMPER_STUB_X)
                    dwg.append(draw.Line(wire_x + _WIRE_PAD, line_y, bar_x, line_y, **attrs))
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
                        local_pin=pin,
                    )


def _segment_terminates_at_splice(seg: WireSegment, class_pin: Pin, pin: Pin) -> bool:
    """True when this segment's *remote* end is a SpliceNode."""
    remote = other_endpoint(seg, pin, class_pin)
    return isinstance(remote, SpliceNode)


def _draw_bullet_and_drop(
    dwg: draw.Drawing,
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
        if cont.rect.h == 0:
            continue  # zero-height jumper row — no drop to draw
        cont_cy = cont.rect.y + cont.rect.h / 2
        if cont.segment is not None:
            remote = other_endpoint(cont.segment, cont.pin, cont.class_pin)
            if isinstance(remote, Pin) and _is_jumper(cont.pin, remote):
                prev_y = cont_cy
                continue
        seg_for_color = cont.segment if cont.segment is not None else primary.segment
        dwg.append(draw.Line(bullet_cx, prev_y, bullet_cx, cont_cy, **_wire_attrs(seg_for_color, psp, colored)))
        prev_y = cont_cy
    return bullet_cx, cy
