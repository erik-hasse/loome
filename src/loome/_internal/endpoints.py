from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..model import (
    BusBar,
    CircuitBreaker,
    Fuse,
    GroundSymbol,
    OffPageReference,
    Pin,
    ShieldDrainTerminal,
    SpliceNode,
    Terminal,
    WireEndpoint,
    WireSegment,
)


@runtime_checkable
class HasConnections(Protocol):
    """Endpoint-like object that owns wire segments."""

    _connections: list[WireSegment]


def pin_owner_label(pin: Pin) -> str:
    comp = pin._component
    if comp is not None:
        return comp.label
    if pin._component_class is not None:
        return pin._component_class.__name__
    return "?"


def pin_connector_name(pin: Pin) -> str:
    if pin._connector_class is None:
        return ""
    return pin._connector_class._connector_name


def pin_label(pin: Pin) -> str:
    owner = pin_owner_label(pin)
    conn = pin_connector_name(pin)
    sig = pin.signal_name or f"pin {pin.number}"
    return f"{owner}.{conn}.{sig}" if conn else f"{owner}.{sig}"


def endpoint_label(endpoint: object) -> str:
    """Human label for BOM rows, schedules, and diagnostics."""

    if isinstance(endpoint, Pin):
        return pin_label(endpoint)
    if isinstance(endpoint, SpliceNode):
        return endpoint.label or endpoint.id
    if isinstance(endpoint, Terminal):
        return endpoint.display_name()
    return repr(endpoint)


def endpoint_path(endpoint: object) -> str:
    """Stable endpoint identity used in wire-ID sidecar fingerprints."""

    if isinstance(endpoint, Pin):
        owner = pin_owner_label(endpoint)
        conn = pin_connector_name(endpoint)
        if conn:
            return f"{owner}[{conn}.{endpoint.number}]"
        return f"{owner}[{endpoint.number}]"
    if isinstance(endpoint, SpliceNode):
        return f"Splice[{endpoint.label or endpoint.id}]"
    if isinstance(endpoint, GroundSymbol):
        return f"GroundSymbol[{endpoint.label or endpoint.id}]"
    if isinstance(endpoint, OffPageReference):
        return f"OffPage[{endpoint.label or endpoint.id}]"
    if isinstance(endpoint, Fuse):
        return f"Fuse[{endpoint.name or endpoint.id}]"
    if isinstance(endpoint, CircuitBreaker):
        return f"CircuitBreaker[{endpoint.name or endpoint.id}]"
    if isinstance(endpoint, BusBar):
        return f"BusBar[{endpoint.label or endpoint.id}]"
    if isinstance(endpoint, Terminal):
        return f"{type(endpoint).__name__}[{endpoint.id}]"
    return repr(endpoint)


def segment_fingerprint(seg: WireSegment) -> str:
    return " <-> ".join(sorted([endpoint_path(seg.end_a), endpoint_path(seg.end_b)]))


def other_endpoint(seg: WireSegment, endpoint: object, *aliases: object) -> WireEndpoint:
    """Return the endpoint at the other side of *seg*.

    *aliases* lets callers pass both an instance pin and its class-level pin.
    The renderer often has both because class-level connections can be drawn
    on instance rows.
    """

    candidates = (endpoint, *aliases)
    if any(seg.end_a is candidate for candidate in candidates):
        return seg.end_b
    if any(seg.end_b is candidate for candidate in candidates):
        return seg.end_a
    raise ValueError(f"{endpoint_label(endpoint)} is not an endpoint of {segment_fingerprint(seg)}")


def terminal_load_kind(terminal: Terminal) -> str:
    if isinstance(terminal, BusBar):
        return "busbar"
    if isinstance(terminal, GroundSymbol):
        return "ground"
    if isinstance(terminal, OffPageReference):
        return "offpage"
    return "terminal"


def is_local_segment(seg: WireSegment) -> bool:
    """True for wires that stay inside one connector/component or are layout stubs."""

    a, b = seg.end_a, seg.end_b
    if isinstance(a, ShieldDrainTerminal) or isinstance(b, ShieldDrainTerminal):
        return True
    if isinstance(a, GroundSymbol) and a.local:
        return True
    if isinstance(b, GroundSymbol) and b.local:
        return True
    if isinstance(a, Pin) and isinstance(b, Pin):
        ca, cb = a._connector, b._connector
        if ca is not None and ca is cb:
            return True
        if ca is None and cb is None and a._component is not None and a._component is b._component:
            return True
    return False


def component_key_for_pin(pin: Pin) -> int:
    return id(pin._component) if pin._component is not None else id(pin._component_class)


def connector_key_for_pin(pin: Pin) -> int:
    return id(pin._connector) if pin._connector is not None else id(pin._connector_class)


def endpoint_description(endpoint: object) -> str:
    """Compact diagnostic label for validation warnings."""

    if isinstance(endpoint, Pin):
        owner = pin_owner_label(endpoint)
        conn = pin_connector_name(endpoint)
        pin = endpoint.signal_name or str(endpoint.number)
        return f"{owner}{'.' + conn if conn else ''}.{pin}"
    if isinstance(endpoint, (Terminal, SpliceNode)):
        return endpoint.id
    return repr(endpoint)
