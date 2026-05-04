from __future__ import annotations

from ..model import Pin, ShieldGroup, WireEndpoint, WireSegment


def endpoint_shield_group(endpoint: object) -> ShieldGroup | None:
    sg = getattr(endpoint, "shield_group", None)
    return sg if isinstance(sg, ShieldGroup) else None


def segment_shield_groups(seg: WireSegment) -> tuple[ShieldGroup, ...]:
    """All shield groups known to touch this segment, deduped in priority order."""

    groups = [
        seg.shield_group,
        seg.end_a_shield_group,
        seg.end_b_shield_group,
        endpoint_shield_group(seg.end_a),
        endpoint_shield_group(seg.end_b),
    ]
    result: list[ShieldGroup] = []
    for sg in groups:
        if sg is not None and not any(existing is sg for existing in result):
            result.append(sg)
    return tuple(result)


def segment_shield_for_endpoint(
    seg: WireSegment,
    endpoint: WireEndpoint,
    *aliases: WireEndpoint,
) -> ShieldGroup | None:
    """Return the shield group that should be used from one endpoint's view."""

    if seg.shield_group is not None:
        return seg.shield_group
    candidates = (endpoint, *aliases)
    if any(seg.end_a is candidate for candidate in candidates):
        return seg.end_a_shield_group or endpoint_shield_group(seg.end_a) or endpoint_shield_group(endpoint)
    if any(seg.end_b is candidate for candidate in candidates):
        return seg.end_b_shield_group or endpoint_shield_group(seg.end_b) or endpoint_shield_group(endpoint)
    return endpoint_shield_group(endpoint)


def segment_source_shield_group(seg: WireSegment) -> ShieldGroup | None:
    """Canonical physical-cable owner for segment-level reports.

    Connection-level shields own their member segments directly. Port shields
    have one endpoint-local group at each side of the cable; use the end_a side
    as the canonical owner so BOM and wire-ID assignment produce one cable row
    instead of one per side.
    """

    return seg.shield_group or seg.end_a_shield_group or endpoint_shield_group(seg.end_a)


def segments_for_shield(sg: ShieldGroup, all_segments: list[WireSegment]) -> list[WireSegment]:
    if sg.segments:
        return list(sg.segments)
    return [seg for seg in all_segments if segment_source_shield_group(seg) is sg]


def is_single_oval_pin(endpoint: object) -> bool:
    sg = endpoint_shield_group(endpoint)
    return sg is not None and sg.single_oval


def segment_touches_single_oval_shield(seg: WireSegment) -> bool:
    return any(sg.single_oval for sg in segment_shield_groups(seg)) or any(
        isinstance(endpoint, Pin) and is_single_oval_pin(endpoint) for endpoint in (seg.end_a, seg.end_b)
    )
