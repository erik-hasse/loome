from __future__ import annotations

from dataclasses import dataclass, field

from .bundles import Bundle
from .buses import CanBusLine
from .model import (
    CircuitBreaker,
    CircuitBreakerBank,
    Component,
    Connector,
    Fuse,
    FuseBlock,
    GroundSymbol,
    OffPageReference,
    Pin,
    Shield,
    ShieldGroup,
    SpliceNode,
    Terminal,
    WireSegment,
)


@dataclass
class Harness:
    """A collection of components, splices, and terminals wired together.

    ``add()`` is the explicit path; ``autodetect(namespace)`` scans a spec-file
    namespace for harness objects and follows wire connections to collect any
    endpoints that weren't assigned to named variables. ``segments()`` returns
    every wire in the harness, deduplicated across class-level and
    instance-level connections.
    """

    name: str
    length_unit: str = "in"
    components: list[Component] = field(default_factory=list)
    splice_nodes: list[SpliceNode] = field(default_factory=list)
    terminals: list[Terminal] = field(default_factory=list)
    shield_groups: list[ShieldGroup] = field(default_factory=list)
    bundles: list[Bundle] = field(default_factory=list)
    can_buses: list[CanBusLine] = field(default_factory=list)
    fuse_blocks: list[FuseBlock] = field(default_factory=list)
    cb_banks: list[CircuitBreakerBank] = field(default_factory=list)

    # Convenience filtered views (kept as properties so tests and callers
    # can still query by concrete type without pattern-matching the list).
    @property
    def off_page_refs(self) -> list[OffPageReference]:
        return [t for t in self.terminals if isinstance(t, OffPageReference)]

    @property
    def ground_symbols(self) -> list[GroundSymbol]:
        return [t for t in self.terminals if isinstance(t, GroundSymbol)]

    @property
    def fuses(self) -> list[Fuse]:
        return [t for t in self.terminals if isinstance(t, Fuse)]

    @property
    def circuit_breakers(self) -> list[CircuitBreaker]:
        return [t for t in self.terminals if isinstance(t, CircuitBreaker)]

    def location_for(self, device: Fuse | CircuitBreaker) -> str:
        """Return ``"block_id:position"`` for a placed fuse/CB, or ``""``."""
        if isinstance(device, Fuse):
            for block in self.fuse_blocks:
                for pos, f in block.positions.items():
                    if f is device:
                        return f"{block.id}:{pos}"
        elif isinstance(device, CircuitBreaker):
            for bank in self.cb_banks:
                for pos, cb in bank.positions.items():
                    if cb is device:
                        return f"{bank.id}:{pos}"
        return ""

    def add(self, *items) -> None:
        for item in items:
            if isinstance(item, Component):
                self.components.append(item)
                self._collect_shield_groups(item)
            elif isinstance(item, SpliceNode):
                self.splice_nodes.append(item)
            elif isinstance(item, Terminal):
                self.terminals.append(item)
            elif isinstance(item, ShieldGroup):
                self.shield_groups.append(item)
            elif isinstance(item, Shield):
                self.shield_groups.append(item.group)
            elif isinstance(item, Bundle):
                self.bundles.append(item)
            elif isinstance(item, CanBusLine):
                self.can_buses.append(item)
            elif isinstance(item, FuseBlock):
                self.fuse_blocks.append(item)
            elif isinstance(item, CircuitBreakerBank):
                self.cb_banks.append(item)

    def autodetect(self, namespace: dict) -> None:
        """Populate the harness from a spec-file namespace.

        Scans *namespace* for instances of all harness types, then follows wire
        connections to catch any endpoints not directly assigned to variables.
        Skips objects already added (safe to call after manual harness.add()).
        """
        seen: set[int] = {id(obj) for obj in (*self.components, *self.splice_nodes, *self.terminals)}

        def _register(obj) -> None:
            if id(obj) in seen:
                return
            seen.add(id(obj))
            self.add(obj)

        # ── Step 1: namespace scan ──────────────────────────────────────────
        for val in namespace.values():
            if isinstance(val, (Component, SpliceNode, Terminal, ShieldGroup)):
                _register(val)
            elif isinstance(val, Shield):
                if id(val.group) not in seen:
                    seen.add(id(val.group))
                    self.shield_groups.append(val.group)
            elif isinstance(val, Bundle):
                if val not in self.bundles:
                    self.bundles.append(val)
            elif isinstance(val, CanBusLine):
                if val not in self.can_buses:
                    self.can_buses.append(val)
            elif isinstance(val, FuseBlock):
                if val not in self.fuse_blocks:
                    self.fuse_blocks.append(val)
            elif isinstance(val, CircuitBreakerBank):
                if val not in self.cb_banks:
                    self.cb_banks.append(val)

        # ── Step 2: connection traversal ────────────────────────────────────
        # Build frontier from all instance pins of known components/splices
        # and from class-level pins of Component subclasses in the namespace.
        frontier: list = []

        for comp in list(self.components):
            frontier.extend(comp._direct_pins.values())
            for conn in comp._connectors.values():
                frontier.extend(p for p in vars(conn).values() if isinstance(p, Pin))

        for splice in list(self.splice_nodes):
            frontier.append(splice)

        for val in namespace.values():
            if isinstance(val, type) and issubclass(val, Component) and val is not Component:
                for av in vars(val).values():
                    if isinstance(av, Pin):
                        frontier.append(av)
                    elif isinstance(av, type) and issubclass(av, Connector) and av is not Connector:
                        frontier.extend(pv for pv in vars(av).values() if isinstance(pv, Pin))

        visited: set[int] = set()
        while frontier:
            item = frontier.pop()
            if id(item) in visited:
                continue
            visited.add(id(item))

            for seg in getattr(item, "_connections", []):
                sg = getattr(seg, "shield_group", None)
                if sg is not None and id(sg) not in seen:
                    seen.add(id(sg))
                    self.shield_groups.append(sg)
                for ep in (seg.end_a, seg.end_b):
                    if id(ep) in seen:
                        continue
                    _register(ep)
                    if isinstance(ep, Component):
                        frontier.extend(ep._direct_pins.values())
                        for conn in ep._connectors.values():
                            frontier.extend(p for p in vars(conn).values() if isinstance(p, Pin))
                    elif isinstance(ep, SpliceNode):
                        frontier.append(ep)

        # ── Step 3: freeze bundles ──────────────────────────────────────────
        for bundle in self.bundles:
            bundle.freeze()

    def format_length(self, length: float | None) -> str:
        """Render a numeric length in this harness's display unit, or '—' for None."""
        if length is None:
            return "—"
        if float(length).is_integer():
            return f"{int(length)} {self.length_unit}"
        return f"{length:g} {self.length_unit}"

    def format_wire_length(self, seg: WireSegment) -> str:
        """Format the physical length(s) of this wire for inline display.

        Returns an empty string for wires that don't belong in the bundle
        (unresolved ends, self-loops/straps). For a CAN-bus pin the wire has
        one length per adjacent bus device; those are joined with ``/``.
        """
        for bus in self.can_buses:
            for ep in (seg.end_a, seg.end_b):
                if isinstance(ep, Pin) and bus.covers_pin(ep):
                    pairs = bus.stub_lengths_for(ep, self)
                    if not pairs:
                        return ""
                    if len(pairs) == 1:
                        return self.format_length(pairs[0][0])
                    return " / ".join(
                        f"{self.format_length(length)}→{_connector_short_label(n)}" for length, n in pairs
                    )

        length = self.resolved_length(seg)
        if length is None:
            return ""
        att_a = self._attachment_for(seg.end_a)
        att_b = self._attachment_for(seg.end_b)
        if att_a is not None and att_a is att_b:
            return ""  # strap / jumper: both ends on same attachment
        return self.format_length(length)

    def resolved_length(self, seg: WireSegment) -> float | None:
        """Return the physical length of a wire from bundle state, or None.

        For a CAN pin in a known CanBusLine, returns the stub length to the
        bus tap. Otherwise returns leg_a + trunk_distance + leg_b when both
        endpoints resolve inside the same bundle; None otherwise.
        """
        for bus in self.can_buses:
            for ep in (seg.end_a, seg.end_b):
                if isinstance(ep, Pin) and bus.covers_pin(ep):
                    return bus.segment_length_for(ep, self)

        att_a = self._attachment_for(seg.end_a)
        att_b = self._attachment_for(seg.end_b)
        if att_a is None or att_b is None:
            return None
        if att_a.breakout.bundle is not att_b.breakout.bundle:
            return None
        bundle = att_a.breakout.bundle
        return att_a.leg_length + bundle.distance(att_a.breakout, att_b.breakout) + att_b.leg_length

    def validate_bundles(self) -> list[str]:
        """Return warnings about bundle coverage; empty list if everything resolves."""
        warnings: list[str] = []
        for seg in self.segments():
            att_a = self._attachment_for(seg.end_a)
            att_b = self._attachment_for(seg.end_b)
            can_a = any(isinstance(seg.end_a, Pin) and bus.covers_pin(seg.end_a) for bus in self.can_buses)
            can_b = any(isinstance(seg.end_b, Pin) and bus.covers_pin(seg.end_b) for bus in self.can_buses)
            if can_a or can_b:
                continue
            if att_a is None and att_b is None:
                continue  # both unattached — not a bundle concern
            if att_a is None or att_b is None:
                warnings.append(
                    f"wire {_describe_endpoint(seg.end_a)} ↔ {_describe_endpoint(seg.end_b)}: one end unattached"
                )
                continue
            if att_a.breakout.bundle is not att_b.breakout.bundle:
                warnings.append(
                    f"wire {_describe_endpoint(seg.end_a)} ↔ {_describe_endpoint(seg.end_b)}: "
                    f"endpoints on different bundles ({att_a.breakout.bundle.name!r} vs "
                    f"{att_b.breakout.bundle.name!r})"
                )
        for bus in self.can_buses:
            for dev in bus.devices:
                if self._attachment_for(dev) is None:
                    warnings.append(f"CAN bus {bus.name!r}: device {type(dev).__name__} not attached to any bundle")

        covered: set[int] = {id(dev) for bus in self.can_buses for dev in bus.devices}
        for comp in self.components:
            for conn_name, conn in comp._connectors.items():
                if id(conn) in covered:
                    continue
                if _connector_has_can_pins(conn):
                    warnings.append(f"CAN-capable connector {comp.label}.{conn_name} not listed in any CanBusLine")
        return warnings

    def _attachment_for(self, endpoint):
        for bundle in self.bundles:
            att = bundle.attachment_for(endpoint)
            if att is not None:
                return att
        return None

    def _collect_shield_groups(self, comp: Component) -> None:
        existing_ids = {id(sg) for sg in self.shield_groups}

        def _add(pin: Pin) -> None:
            sg = pin.shield_group
            if sg is not None and id(sg) not in existing_ids:
                existing_ids.add(id(sg))
                self.shield_groups.append(sg)

        def _walk_pins(cls, base_cls):
            seen: set[str] = set()
            for c in cls.__mro__:
                if not (isinstance(c, type) and issubclass(c, base_cls)):
                    continue
                for name, val in vars(c).items():
                    if isinstance(val, Pin) and name not in seen:
                        seen.add(name)
                        _add(val)

        for conn in comp._connectors.values():
            _walk_pins(type(conn), Connector)

        _walk_pins(type(comp), Component)

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

        def _iter_class_pins(cls, base_cls):
            """Walk MRO most-derived first, yielding (attr_name, class_pin) once per name."""
            emitted: set[str] = set()
            for c in cls.__mro__:
                if not (isinstance(c, type) and issubclass(c, base_cls)):
                    continue
                for attr_name, val in vars(c).items():
                    if isinstance(val, Pin) and attr_name not in emitted:
                        emitted.add(attr_name)
                        yield attr_name, val

        for comp in self.components:
            for attr_name, class_pin in _iter_class_pins(type(comp), Component):
                inst_pin = getattr(comp, attr_name, None)
                if isinstance(inst_pin, Pin) and inst_pin._connections:
                    _collect(inst_pin)
                else:
                    _collect(class_pin)

            for conn_name, conn in comp._connectors.items():
                for attr_name, class_pin in _iter_class_pins(type(conn), Connector):
                    inst_pin = getattr(conn, attr_name, None)
                    if isinstance(inst_pin, Pin) and inst_pin._connections:
                        _collect(inst_pin)  # instance-level overrides
                    else:
                        _collect(class_pin)  # fall back to class-level

        for splice in self.splice_nodes:
            _collect(splice)

        return result


def _connector_has_can_pins(conn: Connector) -> bool:
    """True when any pin on *conn* (including inherited) is a CAN Bus pin."""
    seen: set[str] = set()
    for c in type(conn).__mro__:
        if not (isinstance(c, type) and issubclass(c, Connector)):
            continue
        for name, val in vars(c).items():
            if name in seen:
                continue
            seen.add(name)
            if isinstance(val, Pin) and val.shield_group is not None and val.shield_group.single_oval:
                return True
    return False


def _connector_short_label(conn: Connector) -> str:
    comp = getattr(conn, "_component", None)
    if isinstance(comp, Component):
        return comp.label
    return type(conn).__name__


def _describe_endpoint(ep) -> str:
    if isinstance(ep, Pin):
        owner = ep._component.label if ep._component is not None else "?"
        conn = ep._connector_class._connector_name if ep._connector_class is not None else ""
        pin = ep.signal_name or str(ep.number)
        return f"{owner}{'.' + conn if conn else ''}.{pin}"
    if isinstance(ep, (Terminal, SpliceNode)):
        return ep.id
    return repr(ep)
