from __future__ import annotations

import svgwrite

from ..harness import Harness
from ..layout.engine import WIRE_AREA_W
from ..model import Pin, SpliceNode, Terminal, WireSegment
from .colors import _incoming_splice_attrs, _splice_color_code
from .primitives import (
    _MONO_CHAR_W,
    _REMOTE_BOX_X,
    _SPLICE_CX,
    _SPLICE_FAN_X,
    _TERM_SYMBOL_W,
    _WIRE_PAD,
    _draw_splice_symbol,
    _draw_terminal,
    _draw_wire_label,
    _remote_label,
)


def _draw_dead_end_splice(dwg: svgwrite.Drawing, splice: SpliceNode, x: float, cy: float) -> None:
    """Draw the splice's label text (when the splice has no outward wires)."""
    dwg.add(
        dwg.text(
            splice.label or splice.id,
            insert=(x, cy + 4),
            fill="#94a3b8",
            font_size="9px",
            font_family="ui-monospace, monospace",
        )
    )


def _draw_splice_out_leg(
    dwg: svgwrite.Drawing,
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
) -> None:
    """Draw one outward leg from a splice: wire + label + remote symbol/label."""
    dwg.add(dwg.line(start=(start_x, cy), end=(common_wire_end, cy), **attrs))
    _draw_wire_label(dwg, out_seg, start_x, common_wire_end, cy, psp, colored, color_code, harness=harness)

    if isinstance(out_remote, Terminal):
        label_text = _remote_label(out_remote, class_pin, harness)
        term_cx = common_wire_end + 12
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
        dwg.add(
            dwg.text(
                _remote_label(out_remote, class_pin, harness),
                insert=(common_wire_end + pin_label_offset, cy + 4),
                fill="#1e3a5f",
                font_size="9px",
                font_family="ui-monospace, monospace",
            )
        )
    else:
        dwg.add(
            dwg.text(
                _remote_label(out_remote, class_pin, harness),
                insert=(common_wire_end + pin_label_offset, cy + 4),
                fill="#1e293b",
                font_size="9px",
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
) -> float:
    """Return where this leg's wire should end (pre-symbol-gap)."""
    if out_seg is None:
        return fan_x + 30
    if isinstance(out_remote, Terminal):
        label_text = _remote_label(out_remote, class_pin, harness)
        tcx = (
            min_term_cx if min_term_cx > 0 else (wx + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        )
        tcx = max(tcx, fan_x + 20)
        return tcx - 12
    return default_wire_end


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
    """Draw a pin→splice→single-outward pattern as one horizontal track."""
    psp = pin_shield_palette or {}
    splice_cx = wx + _SPLICE_CX
    in_attrs = _incoming_splice_attrs(incoming_seg, splice, [out_seg], psp, colored)
    cc = _splice_color_code(incoming_seg, splice, [out_seg], colored)

    dwg.add(dwg.line(start=(wx + _WIRE_PAD, cy), end=(splice_cx - 6, cy), **in_attrs))
    _draw_wire_label(dwg, incoming_seg, wx + _WIRE_PAD, splice_cx - 6, cy, psp, colored, cc, harness=harness)
    _draw_splice_symbol(dwg, splice_cx, cy)

    if out_seg is None:
        _draw_dead_end_splice(dwg, splice, splice_cx + 10, cy)
        return

    out_start = splice_cx + 6
    out_remote = out_seg.end_b if out_seg.end_a is splice else out_seg.end_a

    if isinstance(out_remote, Terminal):
        label_text = _remote_label(out_remote, class_pin, harness)
        term_cx = (
            min_term_cx if min_term_cx > 0 else (wx + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W)
        )
        term_cx = max(term_cx, out_start + 20)
        wire_end = term_cx - 12
    else:
        wire_end = wx + _REMOTE_BOX_X - 4

    pin_label_offset = 4 if isinstance(out_remote, Pin) else 4
    _draw_splice_out_leg(
        dwg,
        out_seg,
        out_remote,
        out_start,
        cy,
        wire_end,
        class_pin,
        harness,
        in_attrs,
        cc,
        psp,
        colored,
        pin_label_offset=pin_label_offset,
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
    splice_attrs = _incoming_splice_attrs(incoming_seg, splice, out_segs, psp, colored)
    cc = _splice_color_code(incoming_seg, splice, out_segs, colored)

    dwg.add(dwg.line(start=(wx + _WIRE_PAD, center_y), end=(splice_cx - 6, center_y), **splice_attrs))
    _draw_wire_label(dwg, incoming_seg, wx + _WIRE_PAD, splice_cx - 6, center_y, psp, colored, cc, harness=harness)
    _draw_splice_symbol(dwg, splice_cx, center_y)

    # Pre-compute a common wire_end so all fan legs are the same length.
    default_wire_end = wx + _REMOTE_BOX_X - 4
    leg_wire_ends: list[float] = []
    for _, _, out_seg in expanded:
        out_remote = None if out_seg is None else (out_seg.end_b if out_seg.end_a is splice else out_seg.end_a)
        leg_wire_ends.append(
            _splice_leg_wire_end(wx, fan_x, out_seg, out_remote, class_pin, harness, min_term_cx, default_wire_end)
        )
    common_wire_end = max(leg_wire_ends) if leg_wire_ends else default_wire_end

    for i, (_seg, sp, out_seg) in enumerate(expanded):
        sub_y = rect.y + row_h * (i + 0.5)

        dwg.add(dwg.line(start=(splice_cx + 5, center_y), end=(fan_x, sub_y), **splice_attrs))

        if out_seg is None:
            _draw_dead_end_splice(dwg, sp, fan_x + 4, sub_y)
            continue

        out_remote = out_seg.end_b if out_seg.end_a is splice else out_seg.end_a
        _draw_splice_out_leg(
            dwg,
            out_seg,
            out_remote,
            fan_x,
            sub_y,
            common_wire_end,
            class_pin,
            harness,
            splice_attrs,
            cc,
            psp,
            colored,
            pin_label_offset=8,
        )
