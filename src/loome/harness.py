from __future__ import annotations

from dataclasses import dataclass, field

from .model import (
    CircuitBreaker,
    Component,
    Connector,
    Fuse,
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
    components: list[Component] = field(default_factory=list)
    splice_nodes: list[SpliceNode] = field(default_factory=list)
    terminals: list[Terminal] = field(default_factory=list)
    shield_groups: list[ShieldGroup] = field(default_factory=list)

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

    def _collect_shield_groups(self, comp: Component) -> None:
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
