from __future__ import annotations

from ..model import CircuitBreaker, Fuse, GroundSymbol, Pin, SpliceNode, WireSegment

_POWER_STROKE = "#dc2626"  # red  — connected to fuse or CB
_GROUND_STROKE = "#111111"  # black — connected to ground
_WHITE_STROKE = "#9ca3af"  # medium gray — represents "white" wire

# Shielded pairs cycle through: White (gray), White-Blue (dashed), White-Orange (dashed)
_SHIELD_PALETTE: list[tuple[str, str | None]] = [
    (_WHITE_STROKE, None),
    ("#3b82f6", "5,3"),
    ("#f97316", "5,3"),
]
_SHIELD_PALETTE_CODES: list[str] = ["W", "WB", "WO"]

# Explicit WireColor code → SVG stroke value
_EXPLICIT_COLORS: dict[str, str] = {
    "W": _WHITE_STROKE,
    "R": _POWER_STROKE,
    "B": _GROUND_STROKE,
    "N": _GROUND_STROKE,
    "BL": "#3b82f6",
    "WB": "#3b82f6",  # white-blue (dashed in shielded context)
    "OR": "#f97316",
    "WO": "#f97316",  # white-orange (dashed in shielded context)
    "Y": "#eab308",
    "GN": "#16a34a",
    "GR": "#6b7280",
    "PK": "#ec4899",
    "VT": "#8b5cf6",
}


def _wire_attrs(
    seg: WireSegment,
    pin_shield_palette: dict[int, tuple[str, str | None]],
    colored: bool,
) -> dict:
    """Return SVG stroke keyword args for a wire segment.

    Priority: uncolored → explicit color → power (fuse/CB) → ground → shielded → white.
    Shield palette is checked end_a-first so that a wire's color is the same at both
    ends of the physical wire.
    """
    if not colored:
        return {"stroke": "#222222", "stroke_width": 1.5}

    if seg.color and seg.color in _EXPLICIT_COLORS:
        attrs: dict = {"stroke": _EXPLICIT_COLORS[seg.color], "stroke_width": 1.5}
        if seg.color in ("WB", "WO"):
            attrs["stroke_dasharray"] = "5,3"
        return attrs

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


def _effective_color_code(seg: WireSegment, psp: dict, colored: bool) -> str:
    """Return the color code to display on the wire label.

    Mirrors the priority in _wire_attrs: explicit > power > ground > shielded.
    """
    if not colored:
        return ""
    if seg.color:
        return seg.color
    if isinstance(seg.end_a, (Fuse, CircuitBreaker)) or isinstance(seg.end_b, (Fuse, CircuitBreaker)):
        return "R"
    if isinstance(seg.end_a, GroundSymbol) or isinstance(seg.end_b, GroundSymbol):
        return "B"
    for endpoint in (seg.end_a, seg.end_b):
        if isinstance(endpoint, Pin):
            palette_entry = psp.get(id(endpoint))
            if palette_entry is not None:
                try:
                    return _SHIELD_PALETTE_CODES[_SHIELD_PALETTE.index(palette_entry)]
                except ValueError:
                    pass
    return ""


def _splice_color_code(
    seg: WireSegment,
    splice: SpliceNode,
    out_segs: list[WireSegment | None],
    colored: bool,
) -> str:
    """Color code for a splice context, propagated from outward connections.

    Mirrors _incoming_splice_attrs priority: explicit > power > ground.
    """
    if not colored:
        return ""
    if seg.color:
        return seg.color
    for s in out_segs:
        if s is None:
            continue
        remote = s.end_b if s.end_a is splice else s.end_a
        if isinstance(remote, (Fuse, CircuitBreaker)):
            return "R"
    for s in out_segs:
        if s is None:
            continue
        remote = s.end_b if s.end_a is splice else s.end_a
        if isinstance(remote, GroundSymbol):
            return "B"
    return ""


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
        attrs: dict = {"stroke": _EXPLICIT_COLORS[seg.color], "stroke_width": 1.5}
        if seg.color in ("WB", "WO"):
            attrs["stroke_dasharray"] = "5,3"
        return attrs

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
