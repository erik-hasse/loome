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

    Priority: uncolored → explicit color → shielded → aircraft_power_2 (fuse/CB) → ground → white.
    Shield palette beats power/ground so a shielded power line reads as shield-W
    rather than flat red.  Connection-level shields (``with Shield``) derive
    color from the segment's index in its shield group — this is per-wire, so
    a pin with legs in two different shields (or one shielded and one not) gets
    distinct colors.  Class-body shields fall back to the pin-keyed palette.
    """
    if not colored:
        return {"stroke": "#222222", "stroke_width": 1.5}

    if seg.color and seg.color in _EXPLICIT_COLORS:
        attrs: dict = {"stroke": _EXPLICIT_COLORS[seg.color], "stroke_width": 1.5}
        if seg.color in ("WB", "WO"):
            attrs["stroke_dasharray"] = "5,3"
        return attrs

    # Connection-level shield: derive palette from segment index.
    if seg.shield_group is not None and seg.shield_group.segments and not seg.shield_group.cable_only:
        try:
            idx = seg.shield_group.segments.index(seg)
        except ValueError:
            idx = 0
        stroke, dash = _SHIELD_PALETTE[min(idx, len(_SHIELD_PALETTE) - 1)]
        attrs = {"stroke": stroke, "stroke_width": 1.5}
        if dash:
            attrs["stroke_dasharray"] = dash
        return attrs

    # Class-body shield: pin-keyed palette.
    for endpoint in (seg.end_a, seg.end_b):
        if isinstance(endpoint, Pin):
            palette = pin_shield_palette.get(id(endpoint))
            if palette is not None:
                stroke, dash = palette
                attrs: dict = {"stroke": stroke, "stroke_width": 1.5}
                if dash:
                    attrs["stroke_dasharray"] = dash
                return attrs

    code = seg.effective_color
    if code in _EXPLICIT_COLORS:
        return {"stroke": _EXPLICIT_COLORS[code], "stroke_width": 1.5}
    return {"stroke": _WHITE_STROKE, "stroke_width": 1.5}


def _effective_color_code(seg: WireSegment, psp: dict, colored: bool) -> str:
    """Return the color code to display on the wire label.

    Mirrors the priority in _wire_attrs: explicit > shielded > aircraft_power_2 > ground.
    """
    if not colored:
        return ""
    if seg.color:
        return seg.color
    # Connection-level shield: derive code from segment index.
    if seg.shield_group is not None and seg.shield_group.segments and not seg.shield_group.cable_only:
        try:
            idx = seg.shield_group.segments.index(seg)
        except ValueError:
            idx = 0
        return _SHIELD_PALETTE_CODES[min(idx, len(_SHIELD_PALETTE_CODES) - 1)]
    # Class-body shield: pin-keyed palette.
    for endpoint in (seg.end_a, seg.end_b):
        if isinstance(endpoint, Pin):
            palette_entry = psp.get(id(endpoint))
            if palette_entry is not None:
                try:
                    return _SHIELD_PALETTE_CODES[_SHIELD_PALETTE.index(palette_entry)]
                except ValueError:
                    pass
    return seg.effective_color


def _splice_color_code(
    seg: WireSegment,
    splice: SpliceNode,
    out_segs: list[WireSegment | None],
    colored: bool,
) -> str:
    """Color code for a splice context, propagated from outward connections.

    Mirrors _incoming_splice_attrs priority: explicit > aircraft_power_2 > ground.
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
