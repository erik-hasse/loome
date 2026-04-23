"""Bill-of-materials and fuse-schedule generation.

Pure-data collectors + text renderers (markdown, CSV). No SVG dependency.

The fuse schedule walks out from each `Fuse` / `CircuitBreaker` through splices
and bus bars to identify the protected loads. The BoM is a straight inventory
of wires (with synthetic IDs for unnamed segments), connectors, and terminals.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from .model import (
    BusBar,
    CircuitBreaker,
    Fuse,
    GroundSymbol,
    OffPageReference,
    Pin,
    SpliceNode,
    Terminal,
    WireSegment,
)

if TYPE_CHECKING:
    from .harness import Harness


LoadKind = Literal["pin", "busbar", "ground", "offpage", "terminal"]


# ── data ────────────────────────────────────────────────────────────────────


@dataclass
class LoadEndpoint:
    kind: LoadKind
    label: str


@dataclass
class FuseScheduleEntry:
    device: Fuse | CircuitBreaker
    location: str
    wire: WireSegment | None
    wire_length: float | None
    loads: list[LoadEndpoint] = field(default_factory=list)


@dataclass
class BomWireRow:
    wire_id: str
    gauge: int | str
    color: str
    length: float | None
    from_label: str
    to_label: str


@dataclass
class GaugeTotals:
    count: int
    total_length: float
    unresolved: int


@dataclass
class Bom:
    wires: list[BomWireRow]
    gauge_totals: dict[str, GaugeTotals]
    connectors: list[tuple[str, str, int]]
    terminals_by_type: dict[str, list[str]]


# ── endpoint labels ────────────────────────────────────────────────────────


def _pin_label(pin: Pin) -> str:
    owner = pin._component.label if pin._component is not None else _class_owner_label(pin)
    conn = pin._connector_class._connector_name if pin._connector_class is not None else ""
    sig = pin.signal_name or f"pin {pin.number}"
    return f"{owner}.{conn}.{sig}" if conn else f"{owner}.{sig}"


def _class_owner_label(pin: Pin) -> str:
    return pin._component_class.__name__ if pin._component_class is not None else "?"


def _terminal_kind(t: Terminal) -> LoadKind:
    if isinstance(t, BusBar):
        return "busbar"
    if isinstance(t, GroundSymbol):
        return "ground"
    if isinstance(t, OffPageReference):
        return "offpage"
    return "terminal"


def _endpoint_label(ep) -> str:
    if isinstance(ep, Pin):
        return _pin_label(ep)
    if isinstance(ep, SpliceNode):
        return ep.label or ep.id
    if isinstance(ep, Terminal):
        return ep.display_name()
    return repr(ep)


# ── class-pin expansion ────────────────────────────────────────────────────


def _connector_owns_class_pin(conn, pin: Pin) -> bool:
    """True when *conn*'s class MRO contains the exact class-level *pin*."""
    for c in type(conn).__mro__:
        if isinstance(c, type) and vars(c).get(pin._attr_name) is pin:
            return True
    return False


def _expand_pin_load(pin: Pin, harness: "Harness") -> list[LoadEndpoint]:
    """Turn a pin (possibly class-level) into one load endpoint per instance.

    Class-level wiring like ``GSA28.J281.power.connect(ap_fuse)`` appears in
    ``harness.segments()`` as a single segment whose ``end_a`` is the class
    pin. For the schedule we want a row per servo instance — unless that
    instance has its own instance-level override for the same pin.
    """
    if pin._component is not None:
        return [LoadEndpoint(kind="pin", label=_pin_label(pin))]

    results: list[LoadEndpoint] = []
    for comp in harness.components:
        for conn in comp._connectors.values():
            if not _connector_owns_class_pin(conn, pin):
                continue
            inst_pin = getattr(conn, pin._attr_name, None)
            if isinstance(inst_pin, Pin) and not inst_pin._connections:
                results.append(LoadEndpoint(kind="pin", label=_pin_label(inst_pin)))
        direct = comp._direct_pins.get(pin._attr_name)
        if direct is not None and vars(type(comp)).get(pin._attr_name) is pin and not direct._connections:
            results.append(LoadEndpoint(kind="pin", label=_pin_label(direct)))

    if results:
        return results
    # Fall back to the class-level description.
    conn_name = pin._connector_class._connector_name if pin._connector_class is not None else ""
    sig = pin.signal_name or f"pin {pin.number}"
    owner = _class_owner_label(pin)
    label = f"[class] {owner}.{conn_name}.{sig}" if conn_name else f"[class] {owner}.{sig}"
    return [LoadEndpoint(kind="pin", label=label)]


# ── traversal ──────────────────────────────────────────────────────────────


def _build_endpoint_index(harness: "Harness") -> dict[int, list[WireSegment]]:
    index: dict[int, list[WireSegment]] = {}
    for seg in harness.segments():
        for ep in (seg.end_a, seg.end_b):
            index.setdefault(id(ep), []).append(seg)
    return index


def trace_loads(
    start: Fuse | CircuitBreaker,
    harness: "Harness",
    index: dict[int, list[WireSegment]] | None = None,
) -> tuple[WireSegment | None, list[LoadEndpoint]]:
    """Walk from a fuse/CB to all loads it protects.

    Returns ``(first_wire, loads)``. Splice nodes fan out transparently; bus
    bars fan out *and* are recorded as a load themselves.
    """
    idx = index if index is not None else _build_endpoint_index(harness)
    visited: set[int] = {id(start)}
    loads: list[LoadEndpoint] = []
    first_wire: WireSegment | None = None
    stack: list[tuple[WireSegment, object]] = [(s, start) for s in idx.get(id(start), [])]

    while stack:
        seg, came_from = stack.pop()
        if first_wire is None:
            first_wire = seg
        other = seg.end_b if seg.end_a is came_from else seg.end_a
        if id(other) in visited:
            continue
        visited.add(id(other))

        if isinstance(other, Pin):
            loads.extend(_expand_pin_load(other, harness))
        elif isinstance(other, SpliceNode):
            for s in idx.get(id(other), []):
                if s is not seg:
                    stack.append((s, other))
        elif isinstance(other, BusBar):
            loads.append(LoadEndpoint(kind="busbar", label=other.display_name()))
            for s in idx.get(id(other), []):
                if s is not seg:
                    stack.append((s, other))
        elif isinstance(other, Terminal):
            loads.append(LoadEndpoint(kind=_terminal_kind(other), label=other.display_name()))

    return first_wire, loads


# ── collectors ─────────────────────────────────────────────────────────────


def build_fuse_schedule(harness: "Harness") -> list[FuseScheduleEntry]:
    idx = _build_endpoint_index(harness)
    entries: list[FuseScheduleEntry] = []
    for device in [*harness.fuses, *harness.circuit_breakers]:
        wire, loads = trace_loads(device, harness, idx)
        length = harness.resolved_length(wire) if wire is not None else None
        entries.append(
            FuseScheduleEntry(
                device=device,
                location=harness.location_for(device),
                wire=wire,
                wire_length=length,
                loads=loads,
            )
        )
    return entries


def _gauge_sort_key(g) -> int:
    try:
        return -int(g)
    except (TypeError, ValueError):
        return 0


def build_bom(harness: "Harness") -> Bom:
    bucket_counters: dict[tuple[str, str], int] = {}
    wires: list[BomWireRow] = []
    gauge_totals: dict[str, GaugeTotals] = {}

    for seg in harness.segments():
        wid = seg.wire_id
        if not wid:
            key = (str(seg.gauge), seg.color)
            n = bucket_counters.get(key, 0) + 1
            bucket_counters[key] = n
            wid = f"{seg.gauge}{seg.color or '-'}-{n}"
        length = harness.resolved_length(seg)
        totals = gauge_totals.setdefault(str(seg.gauge), GaugeTotals(0, 0.0, 0))
        totals.count += 1
        if length is None:
            totals.unresolved += 1
        else:
            totals.total_length += length
        wires.append(
            BomWireRow(
                wire_id=wid,
                gauge=seg.gauge,
                color=seg.color,
                length=length,
                from_label=_endpoint_label(seg.end_a),
                to_label=_endpoint_label(seg.end_b),
            )
        )

    wires.sort(key=lambda r: (_gauge_sort_key(r.gauge), r.color, r.wire_id))

    connectors: list[tuple[str, str, int]] = []
    for comp in harness.components:
        for conn_name, conn in comp._connectors.items():
            connectors.append((comp.label, conn_name, len(getattr(conn, "_pins", {}))))

    terminals_by_type: dict[str, list[str]] = {}
    for t in harness.terminals:
        terminals_by_type.setdefault(type(t).__name__, []).append(t.id)

    return Bom(
        wires=wires,
        gauge_totals=gauge_totals,
        connectors=connectors,
        terminals_by_type=terminals_by_type,
    )


# ── markdown rendering ─────────────────────────────────────────────────────


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]

    def _fmt(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

    lines = [_fmt(headers), "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    for row in rows:
        lines.append(_fmt(row))
    return "\n".join(lines)


def _feed_label(loads: list[LoadEndpoint]) -> str:
    if not loads:
        return "—"
    return "; ".join(ld.label for ld in loads)


def render_fuse_schedule_md(entries: list[FuseScheduleEntry], harness: "Harness") -> str:
    headers = ["Type", "ID", "Name", "Amps", "Location", "Wire", "Length", "Feeds"]
    rows = [
        [
            "CB" if isinstance(e.device, CircuitBreaker) else "F",
            e.device.id,
            e.device.name or "",
            str(e.device.amps),
            e.location or "—",
            e.wire.label if e.wire is not None else "—",
            harness.format_length(e.wire_length),
            _feed_label(e.loads),
        ]
        for e in entries
    ]
    title = f"# Fuse / CB Schedule — {harness.name}\n"
    if not rows:
        return f"{title}\n_(no fuses or circuit breakers)_\n"
    return f"{title}\n{_md_table(headers, rows)}\n"


def render_bom_md(bom: Bom, harness: "Harness") -> str:
    parts: list[str] = [f"# Bill of Materials — {harness.name}", ""]

    parts += ["## Wires", ""]
    wire_rows = [
        [r.wire_id, str(r.gauge), r.color or "", harness.format_length(r.length), r.from_label, r.to_label]
        for r in bom.wires
    ]
    parts.append(_md_table(["Wire ID", "Gauge", "Color", "Length", "From", "To"], wire_rows))

    parts += ["", "## Totals by gauge", ""]
    tot_rows = [
        [
            g,
            str(t.count),
            harness.format_length(t.total_length if t.count > t.unresolved else None),
            str(t.unresolved),
        ]
        for g, t in sorted(bom.gauge_totals.items(), key=lambda kv: _gauge_sort_key(kv[0]))
    ]
    parts.append(_md_table(["Gauge", "Count", "Total Length", "Unresolved"], tot_rows))

    parts += ["", "## Connectors", ""]
    parts.append(_md_table(["Component", "Connector", "Pins"], [[c, n, str(p)] for c, n, p in bom.connectors]))

    parts += ["", "## Terminals", ""]
    term_rows = [[t, str(len(ids)), ", ".join(ids)] for t, ids in sorted(bom.terminals_by_type.items())]
    parts.append(_md_table(["Type", "Count", "IDs"], term_rows))

    return "\n".join(parts) + "\n"


# ── CSV rendering ──────────────────────────────────────────────────────────


def _csv_section(buf: io.StringIO, title: str, headers: list[str], rows: list[list[str]]) -> None:
    if title:
        buf.write(f"# {title}\n")
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)


def render_fuse_schedule_csv(entries: list[FuseScheduleEntry], harness: "Harness") -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Type", "ID", "Name", "Amps", "Location", "Wire", "Length", "Feeds"])
    for e in entries:
        writer.writerow(
            [
                "CB" if isinstance(e.device, CircuitBreaker) else "F",
                e.device.id,
                e.device.name or "",
                e.device.amps,
                e.location or "",
                e.wire.label if e.wire is not None else "",
                harness.format_length(e.wire_length) if e.wire_length is not None else "",
                "; ".join(ld.label for ld in e.loads),
            ]
        )
    return buf.getvalue()


def render_bom_csv(bom: Bom, harness: "Harness") -> str:
    buf = io.StringIO()
    _csv_section(
        buf,
        "Wires",
        ["Wire ID", "Gauge", "Color", "Length", "From", "To"],
        [
            [r.wire_id, str(r.gauge), r.color or "", harness.format_length(r.length), r.from_label, r.to_label]
            for r in bom.wires
        ],
    )
    buf.write("\n")
    _csv_section(
        buf,
        "Totals by gauge",
        ["Gauge", "Count", "Total Length", "Unresolved"],
        [
            [
                g,
                str(t.count),
                harness.format_length(t.total_length if t.count > t.unresolved else None),
                str(t.unresolved),
            ]
            for g, t in sorted(bom.gauge_totals.items(), key=lambda kv: _gauge_sort_key(kv[0]))
        ],
    )
    buf.write("\n")
    _csv_section(
        buf,
        "Connectors",
        ["Component", "Connector", "Pins"],
        [[c, n, str(p)] for c, n, p in bom.connectors],
    )
    buf.write("\n")
    _csv_section(
        buf,
        "Terminals",
        ["Type", "Count", "IDs"],
        [[t, str(len(ids)), ", ".join(ids)] for t, ids in sorted(bom.terminals_by_type.items())],
    )
    return buf.getvalue()
