from __future__ import annotations

import drawsvg as draw

from .._internal.endpoints import other_endpoint
from ..harness import Harness
from ..layout.engine import WIRE_AREA_W
from ..model import Pin, ShieldGroup, SpliceNode, Terminal, WireEndpoint, WireSegment
from .colors import _effective_color_code, _incoming_splice_attrs, _splice_color_code, _wire_attrs
from .primitives import (
    _MONO_CHAR_W,
    _REMOTE_BOX_X,
    _SHIELD_LEFT_CX,
    _SHIELD_RX,
    _SPLICE_CX,
    _SPLICE_FAN_X,
    _TERM_SYMBOL_W,
    _WIRE_PAD,
    _draw_splice_symbol,
    _draw_terminal,
    _draw_wire_around_ovals,
    _draw_wire_label,
    _remote_label,
)


def _draw_dead_end_splice(dwg: draw.Drawing, splice: SpliceNode, x: float, cy: float) -> None:
    """Draw the splice's label text (when the splice has no outward wires)."""
    dwg.append(
        draw.Text(
            splice.label or splice.id,
            9,
            x,
            cy + 4,
            fill="#94a3b8",
            font_family="ui-monospace, monospace",
        )
    )


def _draw_splice_out_leg(
    dwg: draw.Drawing,
    out_seg: WireSegment,
    out_remote,
    start_x: float,
    cy: float,
    common_wire_end: float,
    class_pin: Pin,
    harness: Harness,
    attrs: dict,
    color_code: str,
    psp: dict,
    colored: bool,
    pin_label_offset: int = 4,
    wx: float = 0.0,
    shield: ShieldGroup | None = None,
    local_endpoint: WireEndpoint | None = None,
) -> None:
    """Draw one outward leg from a splice: wire + label + remote symbol/label."""
    _draw_wire_around_ovals(dwg, start_x, common_wire_end, cy, wx, shield, attrs)
    _draw_wire_label(
        dwg,
        out_seg,
        start_x,
        common_wire_end,
        cy,
        psp,
        colored,
        color_code,
        harness=harness,
        local_pin=local_endpoint,
    )

    if isinstance(out_remote, Terminal):
        label_text = _remote_label(out_remote, class_pin, harness)
        term_cx = common_wire_end + 12
        _draw_terminal(dwg, out_remote, term_cx, cy)
        dwg.append(
            draw.Text(
                label_text,
                9,
                term_cx + 12,
                cy + 4,
                fill="#1e293b",
                font_family="ui-monospace, monospace",
            )
        )
    elif isinstance(out_remote, Pin):
        dwg.append(
            draw.Text(
                _remote_label(out_remote, class_pin, harness),
                9,
                common_wire_end + pin_label_offset,
                cy + 4,
                fill="#1e3a5f",
                font_family="ui-monospace, monospace",
            )
        )
    else:
        dwg.append(
            draw.Text(
                _remote_label(out_remote, class_pin, harness),
                9,
                common_wire_end + pin_label_offset,
                cy + 4,
                fill="#1e293b",
                font_family="ui-monospace, monospace",
            )
        )


def _splice_leg_wire_end(
    wx: float,
    fan_x: float,
    out_seg: WireSegment | None,
    out_remote,
    class_pin: Pin,
    harness: Harness,
    min_term_cx: float,
    default_wire_end: float,
    wire_end_x: float,
) -> float:
    """Return where this leg's wire should end (pre-symbol-gap)."""
    if out_seg is None:
        return fan_x + 30
    if isinstance(out_remote, Terminal):
        label_text = _remote_label(out_remote, class_pin, harness)
        tcx = min_term_cx if min_term_cx > 0 else (wire_end_x - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        tcx = max(tcx, fan_x + 20)
        return tcx - 12
    return default_wire_end


def _draw_splice_connection(
    dwg: draw.Drawing,
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
    shield: ShieldGroup | None = None,
    wire_end_x: float | None = None,
    local_pin: Pin | None = None,
) -> None:
    """Draw a pin→splice→single-outward pattern as one horizontal track."""
    psp = pin_shield_palette or {}
    splice_cx = wx + _SPLICE_CX
    in_attrs = _incoming_splice_attrs(incoming_seg, splice, [out_seg], psp, colored)
    cc = _splice_color_code(incoming_seg, splice, [out_seg], colored)

    _draw_wire_around_ovals(dwg, wx + _WIRE_PAD, splice_cx - 6, cy, wx, shield, in_attrs)
    label_x1 = wx + _SHIELD_LEFT_CX + _SHIELD_RX if shield is not None else wx + _WIRE_PAD
    _draw_wire_label(
        dwg,
        incoming_seg,
        label_x1,
        splice_cx - 6,
        cy,
        psp,
        colored,
        cc,
        harness=harness,
        local_pin=local_pin or class_pin,
    )
    _draw_splice_symbol(dwg, splice_cx, cy)

    if out_seg is None:
        _draw_dead_end_splice(dwg, splice, splice_cx + 10, cy)
        return

    out_start = splice_cx + 6
    out_remote = other_endpoint(out_seg, splice)
    out_attrs = _wire_attrs(out_seg, psp, colored)
    out_cc = _effective_color_code(out_seg, psp, colored)

    right_edge = wire_end_x if wire_end_x is not None else (wx + WIRE_AREA_W)
    if isinstance(out_remote, Terminal):
        label_text = _remote_label(out_remote, class_pin, harness)
        term_cx = min_term_cx if min_term_cx > 0 else (right_edge - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        term_cx = max(term_cx, out_start + 20)
        wire_end = term_cx - 12
    else:
        wire_end = wx + _REMOTE_BOX_X - 4

    _draw_splice_out_leg(
        dwg,
        out_seg,
        out_remote,
        out_start,
        cy,
        wire_end,
        class_pin,
        harness,
        out_attrs,
        out_cc,
        psp,
        colored,
        pin_label_offset=4,
        wx=wx,
        shield=shield,
        local_endpoint=splice,
    )


def _draw_splice_fan(
    dwg: draw.Drawing,
    expanded: list[tuple],
    wx: float,
    rect,
    class_pin: Pin,
    harness: Harness,
    min_term_cx: float = 0,
    colored: bool = True,
    pin_shield_palette: dict | None = None,
    shield: ShieldGroup | None = None,
    wire_end_x: float | None = None,
    local_pin: Pin | None = None,
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
    splice_attrs = _incoming_splice_attrs(incoming_seg, splice, out_segs, psp, colored)
    cc = _splice_color_code(incoming_seg, splice, out_segs, colored)

    _draw_wire_around_ovals(dwg, wx + _WIRE_PAD, splice_cx - 6, center_y, wx, shield, splice_attrs)
    label_x1 = wx + _SHIELD_LEFT_CX + _SHIELD_RX if shield is not None else wx + _WIRE_PAD
    _draw_wire_label(
        dwg,
        incoming_seg,
        label_x1,
        splice_cx - 6,
        center_y,
        psp,
        colored,
        cc,
        harness=harness,
        local_pin=local_pin or class_pin,
    )
    _draw_splice_symbol(dwg, splice_cx, center_y)

    # Pre-compute a common wire_end so all fan legs are the same length.
    default_wire_end = wx + _REMOTE_BOX_X - 4
    right_edge = wire_end_x if wire_end_x is not None else (wx + WIRE_AREA_W)
    leg_wire_ends: list[float] = []
    for _, _, out_seg in expanded:
        out_remote = None if out_seg is None else other_endpoint(out_seg, splice)
        leg_wire_ends.append(
            _splice_leg_wire_end(
                wx, fan_x, out_seg, out_remote, class_pin, harness, min_term_cx, default_wire_end, right_edge
            )
        )
    common_wire_end = max(leg_wire_ends) if leg_wire_ends else default_wire_end

    for i, (_seg, sp, out_seg) in enumerate(expanded):
        sub_y = rect.y + row_h * (i + 0.5)

        if out_seg is not None:
            out_remote = other_endpoint(out_seg, splice)
            out_attrs = _wire_attrs(out_seg, psp, colored)
            out_cc = _effective_color_code(out_seg, psp, colored)
        else:
            out_remote = None
            out_attrs = splice_attrs
            out_cc = cc

        dwg.append(draw.Line(splice_cx + 5, center_y, fan_x, sub_y, **out_attrs))

        if out_seg is None:
            _draw_dead_end_splice(dwg, sp, fan_x + 4, sub_y)
            continue

        _draw_splice_out_leg(
            dwg,
            out_seg,
            out_remote,
            fan_x,
            sub_y,
            common_wire_end,
            class_pin,
            harness,
            out_attrs,
            out_cc,
            psp,
            colored,
            pin_label_offset=8,
            wx=wx,
            shield=shield,
            local_endpoint=splice,
        )
