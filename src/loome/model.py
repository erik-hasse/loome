from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass, field


@dataclass
class ShieldGroup:
    """A set of wires that share a common shield (e.g. a shielded twisted pair)."""

    label: str
    pins: list["Pin"]  # class-level pins whose connections are in this shield


@dataclass
class WireSegment:
    wire_id: str
    gauge: int | str
    color: str
    end_a: WireEndpoint
    end_b: WireEndpoint
    length_mm: float | None = None
    shielded: bool = False
    notes: str = ""

    @property
    def label(self) -> str:
        return "".join(str(p) for p in [self.wire_id, self.gauge, self.color] if p).strip()


class Namespace(dict):
    def __init__(self):
        super().__init__()
        self._shield_stack: list[ShieldGroup] = []

    def __setitem__(self, key, value):
        if self._shield_stack and isinstance(value, Pin):
            sg = self._shield_stack[-1]
            value.shield_group = sg
            sg.pins.append(value)
        super().__setitem__(key, value)


class SupportsShield(type):
    @classmethod
    def __prepare__(cls, name, bases):
        return Namespace()


class Shielded:
    def __enter__(self):
        frame = inspect.currentframe().f_back
        ns: Namespace = frame.f_locals
        sg = ShieldGroup(label="", pins=[])
        ns._shield_stack.append(sg)

    def __exit__(self, exc_type, exc, tb):
        frame = inspect.currentframe().f_back
        ns: Namespace = frame.f_locals
        ns._shield_stack.pop()


@dataclass
class Pin:
    number: int | str
    signal_name: str = ""
    _attr_name: str = field(default="", repr=False)
    _connector_class: type | None = field(default=None, repr=False)
    _component_class: type | None = field(default=None, repr=False)
    _connector: object | None = field(default=None, repr=False)
    _connections: list[WireSegment] = field(default_factory=list, repr=False)
    shield_group: "ShieldGroup | None" = field(default=None, repr=False)

    def shielded_with(self, *others: "Pin", label: str = "") -> "ShieldGroup":
        """Group this pin's wire with others into a single shield."""
        return ShieldGroup(label=label, pins=[self, *others])

    def connect(
        self,
        other: WireEndpoint,
        wire_id: str = "",
        gauge: int | str = 22,
        color: str = "",
        *,
        length_mm: float | None = None,
        shielded: bool = False,
        notes: str = "",
    ) -> WireSegment:
        seg = WireSegment(
            wire_id=wire_id,
            gauge=gauge,
            color=color,
            end_a=self,
            end_b=other,
            length_mm=length_mm,
            shielded=shielded,
            notes=notes,
        )
        self._connections.append(seg)
        if isinstance(other, Pin):
            other._connections.append(seg)
        elif isinstance(other, SpliceNode):
            other._connections.append(seg)
        return seg


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
        color: str = "",
        **kwargs,
    ) -> WireSegment:
        seg = WireSegment(wire_id=wire_id, gauge=gauge, color=color, end_a=self, end_b=other, **kwargs)
        self._connections.append(seg)
        if isinstance(other, Pin):
            other._connections.append(seg)
        elif isinstance(other, SpliceNode):
            other._connections.append(seg)
        return seg


@dataclass
class GroundSymbol:
    id: str
    label: str = "GND"


@dataclass
class OffPageReference:
    id: str
    label: str = ""


@dataclass
class Fuse:
    id: str
    name: str
    amps: int | float


@dataclass
class CircuitBreaker:
    id: str
    name: str
    amps: int | float


WireEndpoint = Pin | SpliceNode | GroundSymbol | OffPageReference | Fuse | CircuitBreaker


class Connector(metaclass=SupportsShield):
    _component_class: type | None = None
    _connector_name: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name, val in vars(cls).items():
            if isinstance(val, Pin) and not val._attr_name:
                val._attr_name = attr_name
                val._connector_class = cls
                if not val.signal_name:
                    val.signal_name = attr_name.replace("_", " ").title()

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


class Component(metaclass=SupportsShield):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr_name, val in vars(cls).items():
            if isinstance(val, type) and issubclass(val, Connector) and val is not Connector:
                val._component_class = cls
                val._connector_name = attr_name
                for pin_name, pin_val in vars(val).items():
                    if isinstance(pin_val, Pin):
                        pin_val._component_class = cls
                        pin_val._connector_class = val
                        pin_val._attr_name = pin_name
                        if not pin_val.signal_name:
                            pin_val.signal_name = pin_name.replace("_", " ").title()
            elif isinstance(val, Pin) and not val._attr_name:
                val._attr_name = attr_name
                val._component_class = cls
                if not val.signal_name:
                    val.signal_name = attr_name.replace("_", " ").title()

    def __init__(self, label: str | None = None):
        self.label = label or type(self).__name__
        self._connectors: dict[str, Connector] = {}
        self._direct_pins: dict[str, Pin] = {}
        for cls in reversed(type(self).__mro__):
            if not (isinstance(cls, type) and issubclass(cls, Component)):
                continue
            for attr_name, val in vars(cls).items():
                if isinstance(val, type) and issubclass(val, Connector) and val is not Connector:
                    conn = val()
                    conn._component = self
                    setattr(self, attr_name, conn)
                    self._connectors[attr_name] = conn
                elif isinstance(val, Pin):
                    pin = copy.copy(val)
                    pin._connections = []
                    setattr(self, attr_name, pin)
                    self._direct_pins[attr_name] = pin


def _connector_classes(comp_cls: type) -> list[type]:
    return [
        v for v in vars(comp_cls).values() if isinstance(v, type) and issubclass(v, Connector) and v is not Connector
    ]


def _class_pins(conn_cls: type) -> list[Pin]:
    return [v for v in vars(conn_cls).values() if isinstance(v, Pin)]


@dataclass
class Harness:
    name: str
    components: list[Component] = field(default_factory=list)
    splice_nodes: list[SpliceNode] = field(default_factory=list)
    off_page_refs: list[OffPageReference] = field(default_factory=list)
    ground_symbols: list[GroundSymbol] = field(default_factory=list)
    fuses: list[Fuse] = field(default_factory=list)
    circuit_breakers: list[CircuitBreaker] = field(default_factory=list)
    shield_groups: list[ShieldGroup] = field(default_factory=list)

    def add(self, *items) -> None:
        for item in items:
            if isinstance(item, Component):
                self.components.append(item)
                self._collect_shield_groups(item)
            elif isinstance(item, SpliceNode):
                self.splice_nodes.append(item)
            elif isinstance(item, OffPageReference):
                self.off_page_refs.append(item)
            elif isinstance(item, GroundSymbol):
                self.ground_symbols.append(item)
            elif isinstance(item, Fuse):
                self.fuses.append(item)
            elif isinstance(item, CircuitBreaker):
                self.circuit_breakers.append(item)
            elif isinstance(item, ShieldGroup):
                self.shield_groups.append(item)

    def _collect_shield_groups(self, comp: "Component") -> None:
        existing_ids = {id(sg) for sg in self.shield_groups}

        def _add(pin: Pin) -> None:
            sg = pin.shield_group
            if sg is not None and id(sg) not in existing_ids:
                existing_ids.add(id(sg))
                self.shield_groups.append(sg)

        for conn in comp._connectors.values():
            for val in vars(type(conn)).values():
                if isinstance(val, Pin):
                    _add(val)

        for val in vars(type(comp)).values():
            if isinstance(val, Pin):
                _add(val)

    def segments(self) -> list[WireSegment]:
        """Return all unique WireSegments.

        Instance-level connections override class-level ones for the same pin.
        This allows multi-instance components to define per-instance wiring while
        single-instance components can rely on the class-level spec.
        """
        seen: set[int] = set()
        result = []

        def _collect(pin_or_splice):
            for seg in pin_or_splice._connections:
                if id(seg) not in seen:
                    seen.add(id(seg))
                    result.append(seg)

        for comp in self.components:
            comp_cls = type(comp)
            for attr_name, class_pin in vars(comp_cls).items():
                if not isinstance(class_pin, Pin):
                    continue
                inst_pin = getattr(comp, attr_name, None)
                if isinstance(inst_pin, Pin) and inst_pin._connections:
                    _collect(inst_pin)
                else:
                    _collect(class_pin)

            for conn_name, conn in comp._connectors.items():
                conn_cls = type(conn)
                for attr_name, class_pin in vars(conn_cls).items():
                    if not isinstance(class_pin, Pin):
                        continue
                    inst_pin = getattr(conn, attr_name, None)
                    if isinstance(inst_pin, Pin) and inst_pin._connections:
                        _collect(inst_pin)  # instance-level overrides
                    else:
                        _collect(class_pin)  # fall back to class-level

        for splice in self.splice_nodes:
            _collect(splice)

        return result
