"""Semantic validation — "is this harness wired correctly", separate from the
bundle-topology/length checks in :meth:`Harness.validate_bundles`.

The headline check is **required pins**: a pin can be marked ``required=True`` or
``required=<predicate>`` (see :class:`loome.model.Pin`). A predicate receives a
:class:`ValidationContext` and returns whether the pin is required *given the
rest of the harness* — so one component's presence or wiring can make another
component's pin required (config-module groups, a nav source that mandates an
ARINC input, reversion pins that only matter with a second display, …).

``run_checks`` returns a flat list of :class:`Issue`. ``unconnected_report`` is
kept separate: unconnected pins are a normal state mid-build, so they are an
informational checklist, never a failure.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ._internal.endpoints import pin_label
from .model import Component, Connector, Pin
from .ports import Port

if TYPE_CHECKING:
    from .harness import Harness

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Issue:
    severity: Severity
    code: str
    message: str

    def format(self) -> str:
        return f"{self.severity}: {self.message}"


# ── pin traversal ────────────────────────────────────────────────────────────


def _connector_pins(conn: Connector) -> Iterator[tuple[str, Pin, Pin]]:
    """Yield ``(attr_name, instance_pin, class_pin)`` for every pin on *conn*.

    Walking the MRO catches pins inherited from shared base connectors and the
    ``<port>_<pin>`` pins injected by composite ports. The class pin is returned
    alongside the instance pin because Port auto-connections (CAN → off-page ref)
    live on the class template, not the per-instance copy.
    """
    seen: set[str] = set()
    for c in type(conn).__mro__:
        if not (isinstance(c, type) and issubclass(c, Connector)):
            continue
        for name, val in vars(c).items():
            if isinstance(val, Pin) and name not in seen:
                seen.add(name)
                inst = getattr(conn, name, None)
                yield name, (inst if isinstance(inst, Pin) else val), val


def _direct_pins(comp: Component) -> Iterator[tuple[str, Pin, Pin]]:
    seen: set[str] = set()
    for c in type(comp).__mro__:
        if not (isinstance(c, type) and issubclass(c, Component)):
            continue
        for name, val in vars(c).items():
            if isinstance(val, Pin) and name not in seen:
                seen.add(name)
                inst = getattr(comp, name, None)
                yield name, (inst if isinstance(inst, Pin) else val), val


def _component_pins(comp: Component) -> Iterator[tuple[str, Pin, Pin]]:
    for conn in comp._connectors.values():
        yield from _connector_pins(conn)
    yield from _direct_pins(comp)


def _connected(inst_pin: Pin, class_pin: Pin) -> bool:
    """A pin is wired if its instance copy or its class template has segments.

    The class template carries port auto-connections (e.g. CAN high/low to the
    shared off-page reference), so CAN pins read as connected without a spec
    author touching them.
    """
    return bool(getattr(inst_pin, "_connections", None)) or bool(getattr(class_pin, "_connections", None))


# ── validation context ───────────────────────────────────────────────────────


class ValidationContext:
    """Passed to a pin's ``required`` predicate. Exposes the harness so a
    predicate can decide requiredness from the presence or wiring of *other*
    components/pins."""

    def __init__(self, harness: "Harness", pin: Pin) -> None:
        self.harness = harness
        self.pin = pin

    def has_component(self, *types_or_names: type | str) -> bool:
        """True if the harness contains a component of any given type or label/class name."""
        for comp in self.harness.components:
            for t in types_or_names:
                if isinstance(t, type) and isinstance(comp, t):
                    return True
                if isinstance(t, str) and (comp.label == t or type(comp).__name__ == t):
                    return True
        return False

    def components(self, cls: type) -> list[Component]:
        """All harness components that are instances of *cls* (subclasses included)."""
        return [c for c in self.harness.components if isinstance(c, cls)]

    def sibling(self, attr_name: str) -> Pin | None:
        """The instance pin named *attr_name* on the same connector as ``self.pin``."""
        conn = self.pin._connector
        pin = getattr(conn, attr_name, None) if conn is not None else None
        return pin if isinstance(pin, Pin) else None

    def any_connected(self, *attr_globs: str) -> bool:
        """True if any *sibling* pin (same connector) matching a glob is wired.

        Handy for all-or-nothing groups: ``required=lambda ctx:
        ctx.any_connected("config_module_*")`` makes every config pin required
        as soon as one of them is wired.
        """
        conn = self.pin._connector
        if conn is None:
            return False
        for name, inst, cls in _connector_pins(conn):
            if inst is self.pin:
                continue
            if any(fnmatch.fnmatch(name, g) for g in attr_globs) and _connected(inst, cls):
                return True
        return False


def require(target, when: "bool | object" = True):
    """Declare that a pin or composite port must be wired.

    Use this in a spec to add *architecture-specific* requiredness that isn't
    intrinsic to the box — e.g. "on this panel, the EIS serial link is the
    required backup for the CAN data path". ``when`` is either a ``bool`` or a
    predicate ``fn(ctx) -> bool`` (see :class:`ValidationContext`), so the
    requirement can depend on what else is in the harness::

        require(eis.J241.rs232, when=lambda ctx: ctx.has_component("MFD"))

    For a composite port the requirement rides on its primary conductor, so
    ``loome validate`` reports one issue per unwired port. Returns *target* so
    it can be used inline. Accepts a ``Pin`` or any :class:`loome.ports.Port`.
    """
    if isinstance(target, Pin):
        target.required = when
    elif isinstance(target, Port):
        pins = target._inner_pins()
        if pins:
            pins[0].required = when
    else:
        raise TypeError(f"require() expects a Pin or Port, got {type(target).__name__}")
    return target


# ── requirement vocabulary (spec authoring) ──────────────────────────────────
#
# A small functional vocabulary for the ``when=`` argument of ``require()`` and
# friends. Each returns a predicate ``fn(ctx) -> bool``; combinators compose
# them. This keeps real panel rules readable, e.g.::
#
#     require(eis.J241.rs232, when=present("MFD"))
#     require(gtx.P3251.rs232_3, when=all_of(present(GTX45R), any_of(present("GTN"), present("GPS"))))


def _as_pred(when: "bool | object"):
    """Coerce a bool or predicate into a predicate ``fn(ctx) -> bool``."""
    if callable(when):
        return when
    return lambda ctx: bool(when)


def _target_wired(target) -> bool:
    """Is a Pin or Port connected to anything (instance-level)?"""
    if isinstance(target, Port):
        return any(bool(getattr(p, "_connections", None)) for p in target._inner_pins())
    return bool(getattr(target, "_connections", None))


def present(*types_or_names: type | str):
    """Predicate: the harness contains a component of any given type or label/name."""
    return lambda ctx: ctx.has_component(*types_or_names)


def absent(*types_or_names: type | str):
    """Predicate: the harness contains no component of the given types/names."""
    return lambda ctx: not ctx.has_component(*types_or_names)


def wired(target):
    """Predicate: *target* (a Pin or Port) is connected to something."""
    return lambda ctx: _target_wired(target)


def all_of(*conditions):
    """Predicate that is true when every condition (bool or predicate) is true."""
    preds = [_as_pred(c) for c in conditions]
    return lambda ctx: all(p(ctx) for p in preds)


def any_of(*conditions):
    """Predicate that is true when any condition (bool or predicate) is true."""
    preds = [_as_pred(c) for c in conditions]
    return lambda ctx: any(p(ctx) for p in preds)


def not_(condition):
    """Predicate that negates a condition (bool or predicate)."""
    pred = _as_pred(condition)
    return lambda ctx: not pred(ctx)


def require_all(*targets, when: "bool | object" = True):
    """Every target must be wired (optionally only when *when* holds).

    Sugar for calling :func:`require` on each target. Returns the targets.
    """
    for target in targets:
        require(target, when=when)
    return targets


def require_any(*targets, when: "bool | object" = True):
    """At least one of the targets must be wired (when *when* holds).

    Each target becomes required only while *when* holds **and** no sibling in
    the group is wired — so wiring any one satisfies the whole group. If the
    group is entirely unwired, every candidate is flagged (pointing at each
    place the requirement could be met). Returns the targets.
    """
    when_pred = _as_pred(when)
    group = list(targets)
    for target in group:
        others = [o for o in group if o is not target]
        require(
            target,
            when=lambda ctx, others=others: when_pred(ctx) and not any(_target_wired(o) for o in others),
        )
    return targets


def _is_required(inst_pin: Pin, harness: "Harness") -> bool:
    req = inst_pin.required
    if callable(req):
        return bool(req(ValidationContext(harness, inst_pin)))
    return bool(req)


# ── checks ───────────────────────────────────────────────────────────────────


def check_required_pins(harness: "Harness") -> list[Issue]:
    issues: list[Issue] = []
    for comp in harness.components:
        for _name, inst, cls in _component_pins(comp):
            if _is_required(inst, harness) and not _connected(inst, cls):
                issues.append(Issue("error", "required-pin", f"{pin_label(inst)} is required but not connected"))
    return issues


def check_duplicate_labels(harness: "Harness") -> list[Issue]:
    counts: dict[str, int] = {}
    for comp in harness.components:
        counts[comp.label] = counts.get(comp.label, 0) + 1
    return [
        Issue("warning", "duplicate-label", f"{n} components share the label {label!r}")
        for label, n in counts.items()
        if n > 1
    ]


def check_can_buses(harness: "Harness") -> list[Issue]:
    issues: list[Issue] = []
    for bus in harness.can_buses:
        if len(bus.devices) < 2:
            issues.append(
                Issue("warning", "can-bus", f"CAN bus {bus.name!r} has {len(bus.devices)} device(s); need at least 2")
            )
    return issues


def run_checks(harness: "Harness") -> list[Issue]:
    """All semantic checks, most-severe first."""
    issues = [
        *check_required_pins(harness),
        *check_duplicate_labels(harness),
        *check_can_buses(harness),
    ]
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(issues, key=lambda i: order.get(i.severity, 9))


def unconnected_report(harness: "Harness") -> dict[str, list[tuple[str, str]]]:
    """Per-component list of ``(pin_number, signal_name)`` for pins with no wire.

    Informational build checklist, keyed by component label. Skips components
    with ``render=False`` (probes, sensors, config modules — endpoints that
    aren't panel boxes you crimp into a harness).
    """
    report: dict[str, list[tuple[str, str]]] = {}
    for comp in harness.components:
        if not comp.render:
            continue
        floating: list[tuple[str, str]] = []
        for _name, inst, cls in _component_pins(comp):
            if not _connected(inst, cls):
                floating.append((str(inst.number), inst.signal_name))
        if floating:
            report[comp.label] = floating
    return report
