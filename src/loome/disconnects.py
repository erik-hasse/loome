"""Inline disconnect connectors (Molex, Deutsch DT, AMP MQS, …).

Kept in a separate module so it can import from both ``model`` (wire types)
and ``ports`` (Port subclasses) without creating a circular import.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .model import Pin, SpliceNode, Terminal, WireSegment, _default_signal_name
from .ports import RS232, CanBus, Port

# ── disconnect pins ────────────────────────────────────────────────────────


@dataclass
class DisconnectPin:
    """One pin slot on a `Disconnect`. Carries one or more WireSegments.

    For point-to-point disconnects (Pin↔Pin, Port↔Port) the pin covers exactly
    one segment. For a CAN-bus disconnect the pin (H or L) covers every
    device's H/L stub on that bus — the disconnect crimp ties them together.
    """

    number: int | str
    signal_name: str = ""
    _attr_name: str = field(default="", repr=False)
    _disconnect: "Disconnect | None" = field(default=None, repr=False)
    _segments: list[WireSegment] = field(default_factory=list, repr=False)
    _can_bus: object | None = field(default=None, repr=False)
    _can_rail: str = field(default="", repr=False)  # "high" or "low" when set

    @property
    def _segment(self) -> WireSegment | None:
        """Backward-compat: first bound segment (None if no segments yet)."""
        return self._segments[0] if self._segments else None

    def between(self, a: object, b: object) -> DisconnectPin:
        """Bind the segment with endpoints {a, b} to this pin.

        Resolution is deferred — the segment lookup happens when the harness
        first iterates segments — so callers may declare the disconnect before
        the wires it sits on. Returns ``self`` for fluency.
        """
        if self._disconnect is None:
            _bind_disconnect_pin(self, a, b)
            return self
        self._disconnect._pending.append((self, a, b))
        return self


# ── disconnect ─────────────────────────────────────────────────────────────


class Disconnect:
    """A standalone, inline connector pair (Molex, Deutsch DT, AMP MQS, ...).

    Pins are physical-layout metadata bolted onto already-declared wires. The
    `between(a, b)` API accepts either a single Pin pair (one disconnect pin)
    or a Port pair of the same type (one disconnect pin per inner segment).

    Two construction styles, parallel to ``Connector``:

      Imperative::

          wing_root = Disconnect("DC1", label="L wing root", part_number="DT06-12S")

      Declarative::

          class DT12(Disconnect):
              power = DisconnectPin(1, "Power")
              gnd   = DisconnectPin(2, "Ground")

          wing_root = DT12("DC1")
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name, val in vars(cls).items():
            if isinstance(val, DisconnectPin) and not val._attr_name:
                val._attr_name = attr_name
                if not val.signal_name:
                    val.signal_name = _default_signal_name(attr_name)

    def __init__(self, id: str, label: str = "", part_number: str = "") -> None:
        self.id = id
        self.label = label
        self.part_number = part_number
        self._pins: dict[int | str, DisconnectPin] = {}
        self._pending: list[tuple[DisconnectPin, object, object]] = []
        self._pending_can: list[tuple[DisconnectPin, DisconnectPin, object, object]] = []
        for cls in reversed(type(self).__mro__):
            if not (isinstance(cls, type) and issubclass(cls, Disconnect)):
                continue
            for attr_name, val in vars(cls).items():
                if isinstance(val, DisconnectPin):
                    pin = copy.copy(val)
                    pin._segments = []
                    pin._disconnect = self
                    setattr(self, attr_name, pin)
                    self._pins[pin.number] = pin

    def resolve(self, harness: object | None = None) -> None:
        """Resolve any pending ``between()`` bindings against now-existing wires.

        Idempotent. Called automatically by ``Harness.segments()`` and
        ``layout()`` so user code can declare disconnects before or after the
        wires they sit on. The harness is required for CAN-bus disconnects so
        ``CanBusLine`` adjacency can be checked.
        """
        if self._pending:
            pending, self._pending = self._pending, []
            for pin, a, b in pending:
                if pin._segments:
                    continue
                _bind_disconnect_pin(pin, a, b)

        if self._pending_can:
            if harness is None:
                return
            pending_can, self._pending_can = self._pending_can, []
            for h_pin, l_pin, port_a, port_b in pending_can:
                _resolve_can_disconnect(harness, h_pin, l_pin, port_a, port_b)

    def __getitem__(self, number: int | str) -> DisconnectPin:
        return self._pins[number]

    def display_name(self) -> str:
        return self.label or self.id

    def _allocate_pin(self, number: int | str | None = None, signal_name: str = "") -> DisconnectPin:
        """Create and register a new DisconnectPin. ``number=None`` auto-assigns."""
        if number is None:
            existing_ints = [n for n in self._pins if isinstance(n, int)]
            number = (max(existing_ints) + 1) if existing_ints else 1
        if number in self._pins:
            raise ValueError(f"Disconnect {self.id!r} already has a pin numbered {number!r}")
        pin = DisconnectPin(number=number, signal_name=signal_name)
        pin._disconnect = self
        self._pins[number] = pin
        return pin

    def between(
        self,
        a,
        b,
        *,
        pins: list[int | str] | None = None,
    ) -> list[DisconnectPin]:
        """Bind one or more pre-declared segments to disconnect pins.

        - ``Pin, Pin``: finds the single segment with endpoints {a, b}; one pin.
        - ``Port, Port`` (same subclass): enumerates per-rail segments and binds
          each to its own auto- or explicitly-numbered disconnect pin.
        """
        if isinstance(a, CanBus) and isinstance(b, CanBus):
            slots = list(pins) if pins is not None else [None, None]
            if len(slots) != 2:
                raise ValueError(f"CAN-bus Disconnect.between needs 2 pins (H, L); got {len(slots)}")
            h_slot, l_slot = slots
            h_pin = (
                self._pins.get(h_slot)
                if h_slot in self._pins
                else self._allocate_pin(number=h_slot, signal_name="CAN H")
            )
            l_pin = (
                self._pins.get(l_slot)
                if l_slot in self._pins
                else self._allocate_pin(number=l_slot, signal_name="CAN L")
            )
            self._pending_can.append((h_pin, l_pin, a, b))
            return [h_pin, l_pin]

        if isinstance(a, Port) and isinstance(b, Port):
            if type(a) is not type(b):
                raise TypeError(
                    f"Disconnect.between requires both ports to be the same type; "
                    f"got {type(a).__name__} and {type(b).__name__}"
                )
            pairs = _port_pin_pairs(a, b)
        elif isinstance(a, Port) or isinstance(b, Port):
            raise TypeError(
                "Disconnect.between requires both arguments to be of the same kind (both Port, or both wire endpoints)"
            )
        elif isinstance(a, (Pin, SpliceNode, Terminal)) and isinstance(b, (Pin, SpliceNode, Terminal)):
            pairs: list[tuple[object, object, str]] = [(a, b, "")]
        else:
            raise TypeError(
                f"Disconnect.between expects wire-endpoint or Port arguments; "
                f"got {type(a).__name__} and {type(b).__name__}"
            )

        if pins is not None and len(pins) != len(pairs):
            raise ValueError(
                f"`pins=` length {len(pins)} does not match the {len(pairs)} segment(s) "
                f"discovered between {a!r} and {b!r}"
            )

        result: list[DisconnectPin] = []
        for i, (pa, pb, name_hint) in enumerate(pairs):
            slot = pins[i] if pins is not None else None
            if slot is not None and slot in self._pins:
                pin = self._pins[slot]
                if not pin.signal_name and name_hint:
                    pin.signal_name = name_hint
            else:
                pin = self._allocate_pin(number=slot, signal_name=name_hint)
            pin.between(pa, pb)
            result.append(pin)
        return result


# ── private helpers ────────────────────────────────────────────────────────


def _find_segment_between(a: object, b: object) -> WireSegment | None:
    """Locate the unique WireSegment with endpoints {a, b}, if any."""
    candidates = getattr(a, "_connections", None) or getattr(b, "_connections", None) or []
    for seg in candidates:
        if (seg.end_a is a and seg.end_b is b) or (seg.end_a is b and seg.end_b is a):
            return seg
    return None


def _bind_disconnect_pin(pin: DisconnectPin, a: object, b: object) -> WireSegment:
    """Find the segment with endpoints {a, b} and bind it to ``pin``."""
    seg = _find_segment_between(a, b)
    if seg is None:
        raise ValueError(
            f"Disconnect pin {_describe_disconnect_pin(pin)}: no wire segment found between "
            f"{_endpoint_repr(a)} and {_endpoint_repr(b)}; declare the wire (with `>>` or "
            f"`.connect()`) somewhere in the harness so it exists at resolve time"
        )
    if seg.disconnect_pin is not None and seg.disconnect_pin is not pin:
        raise ValueError(
            f"Segment {_endpoint_repr(a)} ↔ {_endpoint_repr(b)} already passes through "
            f"disconnect pin {_describe_disconnect_pin(seg.disconnect_pin)}"
        )
    if pin._segments and not any(s is seg for s in pin._segments):
        raise ValueError(f"Disconnect pin {_describe_disconnect_pin(pin)} is already bound to a different segment")
    if not any(s is seg for s in pin._segments):
        pin._segments.append(seg)
    seg.disconnect_pin = pin
    return seg


def _attach_disconnect_pin_to_segment(pin: DisconnectPin, seg: WireSegment) -> None:
    """Mark a segment as passing through ``pin`` (no endpoint search).

    Used for CAN buses where each device's H/L stub is annotated with the same
    disconnect pin even though the segments don't directly touch each other.
    """
    if seg.disconnect_pin is not None and seg.disconnect_pin is not pin:
        raise ValueError(
            f"Segment {_endpoint_repr(seg.end_a)} ↔ {_endpoint_repr(seg.end_b)} already "
            f"passes through disconnect pin {_describe_disconnect_pin(seg.disconnect_pin)}"
        )
    if not any(s is seg for s in pin._segments):
        pin._segments.append(seg)
    seg.disconnect_pin = pin


def _port_pin_pairs(a, b) -> list[tuple[Pin, Pin, str]]:
    """Discover the (pin_a, pin_b, signal_hint) tuples for a Port↔Port disconnect.

    Handles per-port crossover semantics: RS232 pairs TX↔RX. ``CanBus`` is
    handled separately by the caller because its segments are not direct.
    """
    if isinstance(a, RS232):
        ordered: list[tuple[Pin, Pin, str]] = []
        if a._tx is not None and b._rx is not None:
            ordered.append((a._tx, b._rx, f"{a._name} TX↔RX"))
        if a._rx is not None and b._tx is not None:
            ordered.append((a._rx, b._tx, f"{a._name} RX↔TX"))
        if a._gnd is not None and b._gnd is not None:
            ordered.append((a._gnd, b._gnd, f"{a._name} GND"))
        return ordered

    pairs: list[tuple[Pin, Pin, str]] = []
    for attr in a._pin_attrs:
        pa = getattr(a, f"_{attr}", None)
        pb = getattr(b, f"_{attr}", None)
        if isinstance(pa, Pin) and isinstance(pb, Pin):
            hint = f"{getattr(a, '_name', type(a).__name__)} {attr}"
            pairs.append((pa, pb, hint))
    return pairs


def _resolve_can_disconnect(harness, h_pin: DisconnectPin, l_pin: DisconnectPin, port_a, port_b) -> None:
    """Bind every CAN H/L stub on a bus to the disconnect's H/L pins.

    Validates that the two CAN ports belong to the same ``CanBusLine`` and are
    adjacent (so the disconnect splits the bus into two halves). Each device on
    the bus has H and L stub segments to a shared OffPageReference; we mark
    every such segment with the corresponding disconnect pin so the renderer
    annotates the row and BoM lists the rail under the disconnect.
    """
    bus = _find_can_bus_for_ports(harness, port_a, port_b)
    if bus is None:
        bus_count = len(getattr(harness, "can_buses", []) or [])
        if bus_count == 0:
            hint = (
                " — the harness has no CanBusLine registered. If you create the bus "
                "without binding it (e.g. `CanBusLine(...)` rather than `bus = CanBusLine(...)`) "
                "autodetect can't pick it up; assign it to a variable."
            )
        else:
            bus_names = [getattr(b, "name", "?") for b in harness.can_buses]
            hint = (
                f" — checked {bus_count} bus(es) ({bus_names!r}); neither contained both "
                f"CAN ports' connectors. Verify both connectors are listed in CanBusLine.devices."
            )
        raise ValueError(
            f"Disconnect {h_pin._disconnect.id!r}: no CanBusLine in harness contains both "
            f"CAN ports passed to between(){hint}"
        )
    dev_a = bus.connector_for_pin(port_a._high)
    dev_b = bus.connector_for_pin(port_b._high)
    devices = list(bus.devices)
    try:
        idx_a = devices.index(dev_a)
        idx_b = devices.index(dev_b)
    except ValueError as exc:
        raise ValueError(
            f"Disconnect {h_pin._disconnect.id!r}: CAN port connector not found in CanBusLine {bus.name!r}"
        ) from exc
    if abs(idx_a - idx_b) != 1:
        raise ValueError(
            f"Disconnect {h_pin._disconnect.id!r}: CAN ports must be adjacent on "
            f"CanBusLine {bus.name!r} (got positions {idx_a} and {idx_b}). v1 only "
            f"supports adjacent-hop CAN disconnects."
        )

    h_pin._can_bus = bus
    h_pin._can_rail = "high"
    if not h_pin.signal_name:
        h_pin.signal_name = f"{bus.name} CAN H"
    l_pin._can_bus = bus
    l_pin._can_rail = "low"
    if not l_pin.signal_name:
        l_pin.signal_name = f"{bus.name} CAN L"

    if idx_a < idx_b:
        low_side, high_side = port_a, port_b
    else:
        low_side, high_side = port_b, port_a
    low_side._low.disconnect_pins.extend([h_pin, l_pin])
    high_side._high.disconnect_pins.extend([h_pin, l_pin])
    l_pin._segments.append(_stub_segment_for(low_side._low))
    h_pin._segments.append(_stub_segment_for(high_side._high))


def _stub_segment_for(pin: Pin) -> WireSegment:
    """Return the CanBus stub segment from a port pin to the shared OPR.

    CanBus auto-connections live on the *class-level* pin (created at port
    init), so an instance pin's `_connections` may be empty even though a
    segment exists. Walk the connector class MRO to find it.
    """
    if pin._connections:
        return pin._connections[0]
    cls = pin._connector_class
    if cls is not None:
        attr = pin._attr_name
        for c in cls.__mro__:
            class_pin = vars(c).get(attr) if isinstance(c, type) else None
            if isinstance(class_pin, Pin) and class_pin._connections:
                return class_pin._connections[0]
    raise ValueError(
        f"CAN pin {pin.signal_name or pin.number!r} has no segment — has the CanBus port been initialized?"
    )


def _find_can_bus_for_ports(harness, port_a, port_b):
    """Return the CanBusLine in ``harness`` covering both CAN ports' H pins, or None."""
    for bus in getattr(harness, "can_buses", []) or []:
        if bus.covers_pin(port_a._high) and bus.covers_pin(port_b._high):
            return bus
    return None


def _describe_disconnect_pin(pin: DisconnectPin) -> str:
    disc = pin._disconnect
    if disc is None:
        return f"pin {pin.number}"
    return f"{disc.id}:{pin.number}"


def _endpoint_repr(ep) -> str:
    if isinstance(ep, Pin):
        owner = (
            ep._component.label
            if ep._component is not None
            else (ep._component_class.__name__ if ep._component_class is not None else "?")
        )
        conn = ep._connector_class._connector_name if ep._connector_class is not None else ""
        sig = ep.signal_name or str(ep.number)
        return f"{owner}{'.' + conn if conn else ''}.{sig}"
    if isinstance(ep, (Terminal, SpliceNode)):
        return ep.id
    return repr(ep)
