from __future__ import annotations

from ..model import Pin, WireSegment
from .endpoints import segment_fingerprint

DEFAULT_SYSTEM = "GEN"


def component_system(endpoint: object) -> str | None:
    if isinstance(endpoint, Pin):
        comp = endpoint._component
        if comp is not None:
            return getattr(comp, "_system", None)
    return None


def resolve_system(seg: WireSegment, default: str | None) -> str | None:
    if seg.system:
        return seg.system
    a = component_system(seg.end_a)
    if a:
        return a
    b = component_system(seg.end_b)
    if b:
        return b
    return default


def require_system(seg: WireSegment, default: str | None) -> str:
    system = resolve_system(seg, default)
    if system is None:
        raise ValueError(
            f"wire segment {segment_fingerprint(seg)} has no system assigned and harness.default_system is None; "
            "wrap it in a System(...) block, set the component's system, or set a Harness.default_system."
        )
    return system
