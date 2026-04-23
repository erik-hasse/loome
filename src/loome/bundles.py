"""Physical bundle topology: breakouts, attachments, derived wire lengths.

A `Bundle` is a tree of `Breakout` nodes joined by trunk edges (each edge has
a length). Component connectors, direct-pin components, terminals, and splice
nodes are attached to breakouts with a `leg_length` — the stub that exits the
trunk to reach that endpoint.

Once a bundle is `freeze()`d, `Harness.resolved_length(seg)` can compute any
wire's total length as `leg_a + distance(bk_a, bk_b) + leg_b`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Component, Connector, Pin, SpliceNode, Terminal

AttachmentTarget = Connector | Component | Terminal | SpliceNode


@dataclass
class Attachment:
    breakout: "Breakout"
    target: AttachmentTarget
    leg_length: float


@dataclass
class Breakout:
    id: str
    bundle: "Bundle"
    parent: "Breakout | None" = None
    length_from_parent: float = 0.0
    attachments: list[Attachment] = field(default_factory=list)

    def attach(self, target: AttachmentTarget, leg_length: float) -> Attachment:
        att = Attachment(breakout=self, target=target, leg_length=leg_length)
        self.attachments.append(att)
        return att

    def path_to_root(self) -> list["Breakout"]:
        path: list[Breakout] = []
        node: Breakout | None = self
        while node is not None:
            path.append(node)
            node = node.parent
        return path


@dataclass
class Bundle:
    name: str
    _breakouts: list[Breakout] = field(default_factory=list)
    _root: Breakout | None = None
    _frozen: bool = False
    _attachment_by_target: dict[int, Attachment] = field(default_factory=dict)

    @property
    def root(self) -> Breakout | None:
        return self._root

    @property
    def breakouts(self) -> list[Breakout]:
        return list(self._breakouts)

    def breakout(
        self,
        id: str,
        *,
        after: Breakout | None = None,
        length: float = 0.0,
    ) -> Breakout:
        if self._frozen:
            raise RuntimeError(f"Bundle {self.name!r} is frozen; cannot add more breakouts")
        if after is None and self._root is not None:
            raise ValueError(
                f"Bundle {self.name!r} already has a root ({self._root.id!r}); pass after=<parent> for breakout {id!r}"
            )
        if after is not None and after.bundle is not self:
            raise ValueError(f"Breakout {after.id!r} belongs to a different bundle")
        bk = Breakout(id=id, bundle=self, parent=after, length_from_parent=length)
        self._breakouts.append(bk)
        if after is None:
            self._root = bk
        return bk

    def freeze(self) -> None:
        if self._frozen:
            return
        if self._root is None:
            raise ValueError(f"Bundle {self.name!r} has no root breakout")

        # Reachability check: every breakout must be connected to the root.
        reachable: set[int] = set()
        stack: list[Breakout] = [self._root]
        while stack:
            node = stack.pop()
            if id(node) in reachable:
                raise ValueError(f"Bundle {self.name!r} contains a cycle at breakout {node.id!r}")
            reachable.add(id(node))
            for child in self._children_of(node):
                stack.append(child)
        orphaned = [bk.id for bk in self._breakouts if id(bk) not in reachable]
        if orphaned:
            raise ValueError(f"Bundle {self.name!r} has orphan breakouts: {orphaned!r}")

        # Build target→attachment index; reject double-attached targets.
        for bk in self._breakouts:
            for att in bk.attachments:
                key = id(att.target)
                if key in self._attachment_by_target:
                    prev = self._attachment_by_target[key]
                    raise ValueError(
                        f"Target {_describe_target(att.target)!r} attached twice in bundle "
                        f"{self.name!r}: breakouts {prev.breakout.id!r} and {bk.id!r}"
                    )
                self._attachment_by_target[key] = att

        self._frozen = True

    def distance(self, a: Breakout, b: Breakout) -> float:
        if a.bundle is not self or b.bundle is not self:
            raise ValueError("distance() requires two breakouts from this bundle")
        if a is b:
            return 0.0
        path_a = a.path_to_root()
        ancestors_a = {id(n): i for i, n in enumerate(path_a)}  # node_id → depth
        depth_b = 0
        node_b: Breakout | None = b
        while node_b is not None and id(node_b) not in ancestors_a:
            depth_b += node_b.length_from_parent
            node_b = node_b.parent
        if node_b is None:
            raise ValueError(f"Breakouts {a.id!r} and {b.id!r} have no common ancestor")
        depth_a = sum(bk.length_from_parent for bk in path_a[: ancestors_a[id(node_b)]])
        return depth_a + depth_b

    def attachment_for(self, endpoint: object) -> Attachment | None:
        """Return the Attachment covering this endpoint, or None.

        Pins defer to their owning connector (or direct-pin component). When a
        pin is class-level (no connector/component instance), fall back to any
        attached instance of its connector/component class — resolving to a
        unique match, or None if zero or ambiguous. This is what lets
        class-level ``GSU25.J252.x.connect(GMU11.J441.y)`` wires find their
        physical endpoints via the attached instances.
        """
        if not self._frozen:
            raise RuntimeError(f"Bundle {self.name!r} must be frozen before lookup")

        keys: list[int] = []
        if isinstance(endpoint, Pin):
            if endpoint._connector is not None:
                keys.append(id(endpoint._connector))
            if endpoint._component is not None:
                keys.append(id(endpoint._component))
        else:
            keys.append(id(endpoint))

        for k in keys:
            att = self._attachment_by_target.get(k)
            if att is not None:
                return att

        # Class-pin fallback only when no instance owner exists; an instance
        # pin that failed the direct lookup is genuinely unattached.
        if isinstance(endpoint, Pin) and endpoint._connector is None and endpoint._component is None:
            cls = endpoint._connector_class or endpoint._component_class
            if cls is not None:
                candidates = [att for att in self._attachment_by_target.values() if isinstance(att.target, cls)]
                if len(candidates) == 1:
                    return candidates[0]
        return None

    def _children_of(self, node: Breakout) -> list[Breakout]:
        return [bk for bk in self._breakouts if bk.parent is node]


def _describe_target(target: AttachmentTarget) -> str:
    if isinstance(target, Component):
        return target.label
    if isinstance(target, Connector):
        comp = getattr(target, "_component", None)
        if comp is not None and isinstance(comp, Component):
            cls = type(target)
            return f"{comp.label}.{cls._connector_name}" if cls._connector_name else comp.label
        return type(target).__name__
    if isinstance(target, (Terminal, SpliceNode)):
        return target.id
    return repr(target)
