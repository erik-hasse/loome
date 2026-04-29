from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from typing import Literal, Self

WireColor = Literal[
    "",  # auto (default)
    "W",  # White  → medium gray
    "R",  # Red
    "B",  # Black
    "N",  # Black (Noir — common in aviation docs)
    "BL",  # Blue
    "OR",  # Orange
    "Y",  # Yellow
    "GN",  # Green
    "GR",  # Gray
    "PK",  # Pink
    "VT",  # Violet
]


# ── terminals ──────────────────────────────────────────────────────────────
#
# Terminal subclasses are endpoints a wire runs *to* — they render as a symbol
# (ground triangle, off-page chevron, fuse/CB box, bus-bar stripe) rather than
# as a pin inside a component block. `display_name()` is the single source of
# truth for the text shown next to the symbol. Adding a new Terminal subclass
# and teaching the renderer to draw its symbol is the standard extension path
# (see README: diodes, bus bars, relays).


@dataclass
class Terminal:
    """Base class for symbol-rendered wire endpoints."""

    id: str

    def display_name(self) -> str:
        return self.id


@dataclass
class GroundSymbol(Terminal):
    label: str = "GND"
    filled: bool = True

    def display_name(self) -> str:
        return self.label


@dataclass
class OffPageReference(Terminal):
    label: str = ""

    def display_name(self) -> str:
        return self.label or self.id


@dataclass
class Fuse(Terminal):
    name: str = ""
    amps: int | float = 0

    def display_name(self) -> str:
        return f"{self.name or self.id} {self.amps}A"


@dataclass
class CircuitBreaker(Terminal):
    name: str = ""
    amps: int | float = 0

    def display_name(self) -> str:
        return f"{self.name} {self.amps}A"


@dataclass
class BusBar(Terminal):
    """A named aircraft_power_2 or ground rail that accepts many wire taps.

    Reserved as a first-class Terminal so the renderer can draw a thick
    horizontal bar with labeled tap points instead of stubbing every wire
    into an ``OffPageReference``.
    """

    label: str = ""

    def display_name(self) -> str:
        return self.label or self.id


# ── protective-device containers ───────────────────────────────────────────
#
# Grouping objects for harness organization and the fuse schedule. Not
# Terminals — they don't sit on a wire. The bundle renderer will eventually
# grow support for attaching one of these to a breakout as a single unit;
# until then they're consumed only by the BoM / fuse-schedule output.


class FuseBlock:
    """Holds a set of ``Fuse``s in numbered positions (e.g. an ATO block).

    Subclass and declare ``Fuse`` class attributes for a declarative style::

        class AvionicsFuseBlock(FuseBlock):
            G5    = Fuse("G5",    amps=5)
            GAD27 = Fuse("GAD27", amps=2)

    Or use the imperative style for one-offs::

        fb = FuseBlock("FB1", label="Main Panel Block")
        fb.place(1, some_fuse)
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name, val in vars(cls).items():
            if isinstance(val, Fuse) and not val.name:
                val.name = attr_name

    def __init__(self, id: str | None = None, label: str = ""):
        self.id = id or type(self).__name__
        self.label = label or self.id
        self.positions: dict[int | str, Fuse] = {}
        for cls in reversed(type(self).__mro__):
            if not (isinstance(cls, type) and issubclass(cls, FuseBlock)):
                continue
            for attr_name, val in vars(cls).items():
                if isinstance(val, Fuse):
                    fuse = copy.copy(val)
                    setattr(self, attr_name, fuse)
                    self.positions[attr_name] = fuse

    def place(self, position: int | str, fuse: "Fuse") -> "Fuse":
        self.positions[position] = fuse
        return fuse


@dataclass
class CircuitBreakerBank:
    """A row of ``CircuitBreaker``s sharing a ``BusBar`` feed rail."""

    id: str
    label: str = ""
    bus: "BusBar | None" = None
    positions: dict[int | str, "CircuitBreaker"] = field(default_factory=dict)

    def place(self, position: int | str, breaker: "CircuitBreaker") -> "CircuitBreaker":
        self.positions[position] = breaker
        return breaker


# ── splices ────────────────────────────────────────────────────────────────


@dataclass
class SpliceNode:
    id: str
    label: str = ""
    _connections: list[WireSegment] = field(default_factory=list, repr=False)

    def connect(
        self,
        other: WireEndpoint,
        wire_id: str = "",
        gauge: int | str = 22,
        color: WireColor = "",
        **kwargs,
    ) -> WireSegment:
        seg = WireSegment(wire_id=wire_id, gauge=gauge, color=color, end_a=self, end_b=other, **kwargs)
        if _active_shield_stack:
            sg = _active_shield_stack[-1]
            sg.segments.append(seg)
            seg.shielded = True
            seg.shield_group = sg
        self._connections.append(seg)
        if isinstance(other, (Pin, SpliceNode)):
            other._connections.append(seg)
        return seg

    def __rshift__(self, other: WireEndpoint) -> "WireBuilder":
        return WireBuilder(self.connect(other))


# ── shields ────────────────────────────────────────────────────────────────

_lgnd_counter = itertools.count()


def _resolve_drain(value: "WireEndpoint | bool | None") -> "WireEndpoint | None":
    """Normalize a drain specification.

    ``True``  → new open-triangle GroundSymbol (local ground).
    ``False`` → ``None`` (floating, no drain).
    ``None``  → ``None`` (floating, no drain).
    Any ``WireEndpoint`` → passed through unchanged.
    """
    if value is True:
        return GroundSymbol(id=f"_lgnd_{next(_lgnd_counter)}", label="GND", filled=False)
    if value is False:
        return None
    return value  # type: ignore[return-value]


@dataclass
class ShieldGroup:
    """A set of wires that share a common shield (e.g. a shielded twisted pair)."""

    label: str
    pins: list["Pin"]  # class-level pins whose connections are in this shield
    segments: list["WireSegment"] = field(default_factory=list)  # connection-level segments
    drain: "WireEndpoint | None" = None  # drain at source/near end (None = floating)
    drain_remote: "WireEndpoint | None" = None  # drain at remote end (None = floating)
    single_oval: bool = False  # draw only the left/near oval (e.g. CAN bus)
    cable_only: bool = False  # group pins for layout but skip oval/palette (twisted pairs, etc.)


_active_shield_stack: list[ShieldGroup] = []


class Shield:
    """Connection-level shield context manager.

    Wraps ``connect()`` calls to group the resulting wire segments under a single
    shield foil. Supports optional drain terminals on either or both ends.

    Usage::

        with Shield(drain=gnd) as oat_shield:
            gsu25.J252.oat_probe_power.connect(oat_probe.oat_probe_power)
            gsu25.J252.oat_probe_high.connect(oat_probe.oat_probe_high)
    """

    def __init__(
        self,
        drain: "WireEndpoint | bool | None" = None,
        drain_remote: "WireEndpoint | bool | None" = None,
        label: str = "",
    ) -> None:
        self._sg = ShieldGroup(
            label=label, pins=[], drain=_resolve_drain(drain), drain_remote=_resolve_drain(drain_remote)
        )

    def __enter__(self) -> "Shield":
        _active_shield_stack.append(self._sg)
        return self

    def __exit__(self, *_) -> None:
        _active_shield_stack.pop()

    @property
    def group(self) -> ShieldGroup:
        return self._sg


# ── wires ──────────────────────────────────────────────────────────────────


@dataclass
class WireSegment:
    wire_id: str
    gauge: int | str
    color: str
    end_a: WireEndpoint
    end_b: WireEndpoint
    shielded: bool = False
    notes: str = ""
    shield_group: "ShieldGroup | None" = field(default=None, repr=False)

    @property
    def label(self) -> str:
        return "".join(str(p) for p in [self.wire_id, self.gauge, self.color] if p).strip()


# ── pins ───────────────────────────────────────────────────────────────────


@dataclass
class Pin:
    number: int | str
    signal_name: str = ""
    _attr_name: str = field(default="", repr=False)
    _connector_class: type | None = field(default=None, repr=False)
    _component_class: type | None = field(default=None, repr=False)
    _connector: object | None = field(default=None, repr=False)
    _component: object | None = field(default=None, repr=False)
    _connections: list[WireSegment] = field(default_factory=list, repr=False)
    shield_group: "ShieldGroup | None" = field(default=None, repr=False)
    _can_terminated: bool = field(default=False, repr=False)

    def local_ground(self, label: str = "GND") -> None:
        sym = GroundSymbol(id=f"lgnd_{id(self)}", label=label, filled=False)
        self.connect(sym)

    def connect(
        self,
        other: WireEndpoint,
        wire_id: str = "",
        gauge: int | str = 22,
        color: WireColor = "",
        *,
        shielded: bool = False,
        notes: str = "",
    ) -> WireSegment:
        seg = WireSegment(
            wire_id=wire_id,
            gauge=gauge,
            color=color,
            end_a=self,
            end_b=other,
            shielded=shielded,
            notes=notes,
        )
        if _active_shield_stack:
            sg = _active_shield_stack[-1]
            sg.segments.append(seg)
            seg.shielded = True
            seg.shield_group = sg
        self._connections.append(seg)
        if isinstance(other, (Pin, SpliceNode)):
            other._connections.append(seg)
        return seg

    def __rshift__(self, other: "WireEndpoint") -> "WireBuilder":
        return WireBuilder(self.connect(other))


WireEndpoint = Pin | SpliceNode | Terminal


class WireBuilder:
    """Fluent modifier returned by ``pin >> other``."""

    def __init__(self, segment: WireSegment) -> None:
        self._seg = segment

    def gauge(self, value: int | str) -> "WireBuilder":
        self._seg.gauge = value
        return self

    def color(self, value: WireColor) -> "WireBuilder":
        self._seg.color = value
        return self

    def wire_id(self, value: str) -> "WireBuilder":
        self._seg.wire_id = value
        return self

    def notes(self, value: str) -> "WireBuilder":
        self._seg.notes = value
        return self


# ── connectors / components ────────────────────────────────────────────────


def _default_signal_name(attr_name: str) -> str:
    return attr_name.replace("_", " ").title()


class Connector:
    _component_class: type | None = None
    _connector_name: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name, val in vars(cls).items():
            if isinstance(val, Pin) and not val._attr_name:
                val._attr_name = attr_name
                val._connector_class = cls
                if not val.signal_name:
                    val.signal_name = _default_signal_name(attr_name)

    def __init__(self):
        self._pins: dict[int | str, Pin] = {}
        for cls in reversed(type(self).__mro__):
            if not (isinstance(cls, type) and issubclass(cls, Connector)):
                continue
            for attr_name, val in vars(cls).items():
                if isinstance(val, Pin):
                    pin = copy.copy(val)
                    pin._connections = []
                    pin._connector = self
                    setattr(self, attr_name, pin)
                    self._pins[pin.number] = pin

    def __getitem__(self, number: int | str) -> Pin:
        return self._pins[number]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Component:
    render: bool = True  # set False on a subclass or instance to hide from schematic

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name, val in vars(cls).items():
            if isinstance(val, type) and issubclass(val, Connector) and val is not Connector:
                val._component_class = cls
                val._connector_name = attr_name
                # Walk MRO so pins inherited from Connector base classes (e.g. a
                # shared _BaseJ281) pick up component/connector tagging too.
                tagged: set[str] = set()
                for c in val.__mro__:
                    if not (isinstance(c, type) and issubclass(c, Connector)):
                        continue
                    for pin_name, pin_val in vars(c).items():
                        if isinstance(pin_val, Pin) and pin_name not in tagged:
                            tagged.add(pin_name)
                            pin_val._component_class = cls
                            pin_val._connector_class = val
                            pin_val._attr_name = pin_name
                            if not pin_val.signal_name:
                                pin_val.signal_name = _default_signal_name(pin_name)
            elif isinstance(val, Pin) and not val._attr_name:
                val._attr_name = attr_name
                val._component_class = cls
                if not val.signal_name:
                    val.signal_name = _default_signal_name(attr_name)

    def __init__(self, label: str | None = None, *, render: bool | None = None):
        self.label = label or type(self).__name__
        if render is not None:
            self.render = render
        self._connectors: dict[str, Connector] = {}
        self._direct_pins: dict[str, Pin] = {}
        for cls in reversed(type(self).__mro__):
            if not (isinstance(cls, type) and issubclass(cls, Component)):
                continue
            for attr_name, val in vars(cls).items():
                if isinstance(val, type) and issubclass(val, Connector) and val is not Connector:
                    conn = val()
                    conn._component = self
                    for pin_val in vars(conn).values():
                        if isinstance(pin_val, Pin):
                            pin_val._component = self
                    setattr(self, attr_name, conn)
                    self._connectors[attr_name] = conn
                elif isinstance(val, Pin):
                    pin = copy.copy(val)
                    pin._connections = []
                    pin._component = self
                    setattr(self, attr_name, pin)
                    self._direct_pins[attr_name] = pin

    def __getitem__(self, number: int | str) -> Pin:
        return self._direct_pins[number]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
