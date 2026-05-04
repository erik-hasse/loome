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

from natsort import natsort_keygen

from .disconnects import DisconnectPin
from .model import (
    BusBar,
    CircuitBreaker,
    Fuse,
    GroundSymbol,
    OffPageReference,
    Pin,
    ShieldGroup,
    SpliceNode,
    Terminal,
    WireSegment,
)
from .wire_ids import _is_local_segment, _resolve_system

if TYPE_CHECKING:
    from .harness import Harness


_natsort_key = natsort_keygen()

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
    system: str = ""


@dataclass
class GaugeTotals:
    count: int
    total_length: float
    unresolved: int


@dataclass
class SystemTotals:
    wires: int = 0
    cables: int = 0
    conductors: int = 0
    total_length: float = 0.0
    unresolved: int = 0


@dataclass
class BomShieldedRow:
    cable_id: str
    conductors: int
    gauge: int | str
    color: str
    length: float | None
    from_label: str
    to_label: str
    has_drain: bool
    system: str = ""


@dataclass
class DisconnectPinRow:
    pin: str
    signal_name: str
    wire_id: str
    gauge: int | str
    color: str
    from_label: str
    to_label: str


@dataclass
class DisconnectEntry:
    id: str
    label: str
    part_number: str
    pins: list[DisconnectPinRow]


@dataclass
class Bom:
    wires: list[BomWireRow]
    gauge_totals: dict[str, GaugeTotals]
    connectors: list[tuple[str, str, int]]
    terminals_by_type: dict[str, list[str]]
    disconnects: list[DisconnectEntry] = field(default_factory=list)
    shielded_cables: list[BomShieldedRow] = field(default_factory=list)
    system_totals: dict[str, SystemTotals] = field(default_factory=dict)


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


def _disconnect_pin_label(dpin: DisconnectPin) -> str:
    disc = dpin._disconnect
    base = f"{disc.id}:{dpin.number}" if disc is not None else f"DC?:{dpin.number}"
    return f"{base} ({dpin.signal_name})" if dpin.signal_name else base


# ── class-pin expansion ────────────────────────────────────────────────────


def _connector_owns_class_pin(conn, pin: Pin) -> bool:
    """True when *conn*'s class MRO contains the exact class-level *pin*."""
    for c in type(conn).__mro__:
        if isinstance(c, type) and vars(c).get(pin._attr_name) is pin:
            return True
    return False


def _expand_pin_load(pin: Pin, harness: "Harness") -> list[LoadEndpoint]:
    """Turn a pin (possibly class-level) into one load endpoint per instance.

    Class-level wiring like ``GSA28.J281.aircraft_power_2.connect(ap_fuse)`` appears in
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


def _segments_for_shield(sg: ShieldGroup, all_segments: list[WireSegment]) -> list[WireSegment]:
    """Resolve the conductor segments belonging to one ShieldGroup.

    Connection-level shields (`Shield` context manager) populate `sg.segments`
    directly. Port shields (RS232, GPIO, …) attach `pin.shield_group = sg` to
    each port pin instead, where each port instance has its own ShieldGroup —
    the two endpoints of a port-to-port segment thus carry different SGs. Use
    `end_a.shield_group is sg` only so each cable is reported exactly once
    (the remote SG sees the segment as end_b and contributes nothing).
    """
    if sg.segments:
        return list(sg.segments)
    found: list[WireSegment] = []
    for seg in all_segments:
        a = seg.end_a
        if isinstance(a, Pin) and getattr(a, "shield_group", None) is sg:
            found.append(seg)
    return found


def _bucket_by_instance_pair(segments: list[WireSegment]) -> list[list[WireSegment]]:
    """Group segments by (component_a, component_b) so each device-pair is one cable."""
    buckets: dict[tuple[int, int], list[WireSegment]] = {}
    order: list[tuple[int, int]] = []
    for seg in segments:
        a_comp = seg.end_a._component if isinstance(seg.end_a, Pin) else None
        b_comp = seg.end_b._component if isinstance(seg.end_b, Pin) else None
        key = (id(a_comp), id(b_comp))
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(seg)
    return [buckets[k] for k in order]


def _dominant(values: list, mixed: str = "mixed"):
    nonempty = [v for v in values if v != "" and v is not None]
    if not nonempty:
        return ""
    first = nonempty[0]
    if all(v == first for v in nonempty):
        return first
    return mixed


def _component_label(seg: WireSegment) -> str:
    for ep in (seg.end_b, seg.end_a):
        if isinstance(ep, Pin) and ep._component is not None:
            return ep._component.label
    return ""


def _connector_label(conn) -> str:
    comp = getattr(conn, "_component", None)
    name = getattr(conn, "_connector_name", "")
    if comp is not None:
        return f"{comp.label}.{name}" if name else comp.label
    return name or repr(conn)


def _can_pin_gauge(devices, all_segments: list[WireSegment]) -> int | str:
    """Pick a gauge for a CAN cable from any segment that touches any CAN pin
    on any of the given devices."""
    pin_ids: set[int] = set()
    for dev in devices:
        for pv in vars(dev).values():
            if isinstance(pv, Pin) and pv.shield_group is not None and pv.shield_group.single_oval:
                pin_ids.add(id(pv))
        for c in type(dev).__mro__:
            if isinstance(c, type) and hasattr(c, "__mro__"):
                for pv in vars(c).values():
                    if isinstance(pv, Pin) and pv.shield_group is not None and pv.shield_group.single_oval:
                        pin_ids.add(id(pv))
    for seg in all_segments:
        if (isinstance(seg.end_a, Pin) and id(seg.end_a) in pin_ids) or (
            isinstance(seg.end_b, Pin) and id(seg.end_b) in pin_ids
        ):
            return seg.gauge
    return ""


def _segment_system(seg: WireSegment, harness: "Harness") -> str:
    return _resolve_system(seg, harness.default_system) or ""


def _shield_system(segs: list[WireSegment], harness: "Harness") -> str:
    for s in segs:
        sys = _resolve_system(s, None)
        if sys:
            return sys
    return harness.default_system or ""


def build_bom(harness: "Harness") -> Bom:
    wires: list[BomWireRow] = []
    gauge_totals: dict[str, GaugeTotals] = {}
    disconnect_segs: dict[int, list[tuple[WireSegment, str, float | None, float | None]]] = {}

    all_segments = harness.segments()

    shielded_cables: list[BomShieldedRow] = []
    shielded_seg_ids: set[int] = set()
    sg_to_rows: dict[int, list[BomShieldedRow]] = {}
    sc_counter = 0

    # Mark every segment touching a CAN-bus pin (shield_group.single_oval=True)
    # as shielded so it disappears from the per-conductor Wires section, whether
    # or not the port appears on a CanBusLine. CAN pins auto-connect to a shared
    # off-page ref; that plumbing isn't a real wire.
    for seg in all_segments:
        for ep in (seg.end_a, seg.end_b):
            if isinstance(ep, Pin) and ep.shield_group is not None and ep.shield_group.single_oval:
                shielded_seg_ids.add(id(seg))
                break
    can_disc_cables: dict[tuple[int, int], list[BomShieldedRow]] = {}
    can_disc_base_ids: dict[tuple[int, int], list[str]] = {}
    for cbl in harness.can_buses:
        gauge = _can_pin_gauge(cbl.devices, all_segments)
        resolved = {(id(a), id(b)): dist for a, b, dist in cbl.segments(harness)}
        # Map adjacent (low_dev, high_dev) pair → CAN disconnect on this bus.
        # `_resolve_can_disconnect` records the disconnect's pins on the
        # low-side device's CAN Low pin and the high-side device's CAN High
        # pin; walk those to identify which adjacent pair the disconnect splits.
        pair_disc: dict[tuple[int, int], object] = {}
        for disc in harness.disconnects:
            if not any(p._can_bus is cbl for p in disc._pins.values()):
                continue
            low_dev = high_dev = None
            for dev in cbl.devices:
                for pv in vars(dev).values():
                    if not isinstance(pv, Pin) or pv.shield_group is None or not pv.shield_group.single_oval:
                        continue
                    if not any(dp._disconnect is disc for dp in pv.disconnect_pins):
                        continue
                    if pv.signal_name == "CAN Low":
                        low_dev = dev
                    elif pv.signal_name == "CAN High":
                        high_dev = dev
            if low_dev is not None and high_dev is not None:
                pair_disc[(id(low_dev), id(high_dev))] = disc

        can_pair_ids = getattr(harness, "_can_pair_ids", {}) or {}
        for i, (dev_a, dev_b) in enumerate(zip(cbl.devices, cbl.devices[1:]), start=1):
            length = resolved.get((id(dev_a), id(dev_b)))
            base_id = can_pair_ids.get((id(cbl), id(dev_a), id(dev_b))) or f"{cbl.name}-{i}"
            disc = pair_disc.get((id(dev_a), id(dev_b)))
            from_lbl = _connector_label(dev_a)
            to_lbl = _connector_label(dev_b)
            comp_a = getattr(dev_a, "_component", None)
            comp_b = getattr(dev_b, "_component", None)
            pair_segs = [
                s
                for s in all_segments
                if id(s) in shielded_seg_ids
                and isinstance(s.end_a, Pin)
                and isinstance(s.end_b, Pin)
                and {id(s.end_a._component), id(s.end_b._component)} == {id(comp_a), id(comp_b)}
            ]
            cable_sys = (
                _shield_system(pair_segs, harness)
                or getattr(comp_a, "_system", None)
                or getattr(comp_b, "_system", None)
                or harness.default_system
                or cbl.name
                or ""
            )
            if disc is None:
                shielded_cables.append(
                    BomShieldedRow(
                        cable_id=base_id,
                        conductors=2,
                        gauge=gauge,
                        color="W",
                        length=length,
                        from_label=from_lbl,
                        to_label=to_lbl,
                        has_drain=True,
                        system=cable_sys,
                    )
                )
            else:
                disc_label = disc.label or disc.id
                row_a = BomShieldedRow(
                    cable_id=f"{base_id}A",
                    conductors=2,
                    gauge=gauge,
                    color="W",
                    length=None,
                    from_label=from_lbl,
                    to_label=disc_label,
                    has_drain=True,
                    system=cable_sys,
                )
                row_b = BomShieldedRow(
                    cable_id=f"{base_id}B",
                    conductors=2,
                    gauge=gauge,
                    color="W",
                    length=None,
                    from_label=disc_label,
                    to_label=to_lbl,
                    has_drain=True,
                    system=cable_sys,
                )
                shielded_cables.extend([row_a, row_b])
                can_disc_cables.setdefault((id(disc), id(cbl)), []).extend([row_a, row_b])
                can_disc_base_ids.setdefault((id(disc), id(cbl)), []).append(base_id)

    seen_sgs: set[int] = set()
    for sg in harness.shield_groups:
        if id(sg) in seen_sgs:
            continue
        seen_sgs.add(id(sg))
        if sg.single_oval:
            continue
        segs = _segments_for_shield(sg, all_segments)
        if not segs:
            continue
        buckets = _bucket_by_instance_pair(segs)
        rows_for_sg: list[BomShieldedRow] = []
        # The wire_id is assigned to the ShieldGroup (and its members) by
        # wire_ids.assign_wire_ids; fall back to the legacy synthetic id only
        # if no assignment ran (e.g. tests that bypass the CLI).
        canonical_id = getattr(sg, "wire_id", "") or (sg.label.strip() if sg.label else "")
        for bucket in buckets:
            for seg in bucket:
                shielded_seg_ids.add(id(seg))
            if canonical_id:
                cable_id = canonical_id
                if len(buckets) > 1:
                    cable_id = f"{canonical_id}@{_component_label(bucket[0])}"
            else:
                sc_counter += 1
                cable_id = f"SC-{sc_counter}"
            gauges = [s.gauge for s in bucket]
            colors = [s.color for s in bucket]
            row = BomShieldedRow(
                cable_id=cable_id,
                conductors=len(bucket),
                gauge=_dominant(gauges),
                color=_dominant(colors) or "W",
                length=harness.resolved_length(bucket[0]),
                from_label=_endpoint_label(bucket[0].end_a),
                to_label=_endpoint_label(bucket[0].end_b),
                has_drain=sg.drain is not None or sg.drain_remote is not None,
                system=_shield_system(bucket, harness),
            )
            shielded_cables.append(row)
            rows_for_sg.append(row)
        sg_to_rows[id(sg)] = rows_for_sg

    for seg in all_segments:
        if id(seg) in shielded_seg_ids:
            continue
        if _is_local_segment(seg):
            continue
        wid = seg.wire_id or f"{seg.gauge}{seg.effective_color or '-'}-?"
        color = seg.effective_color
        seg_sys = _segment_system(seg, harness)

        if seg.disconnect_pin is not None and seg.disconnect_pin._can_bus is None:
            sides = harness.resolved_sides(seg) or (None, None)
            len_a, len_b = sides
            disc_label = _disconnect_pin_label(seg.disconnect_pin)
            row_pairs = [
                (f"{wid}A", len_a, _endpoint_label(seg.end_a), disc_label),
                (f"{wid}B", len_b, disc_label, _endpoint_label(seg.end_b)),
            ]
            for row_wid, length, from_label, to_label in row_pairs:
                totals = gauge_totals.setdefault(str(seg.gauge), GaugeTotals(0, 0.0, 0))
                totals.count += 1
                if length is None:
                    totals.unresolved += 1
                else:
                    totals.total_length += length
                wires.append(
                    BomWireRow(
                        wire_id=row_wid,
                        gauge=seg.gauge,
                        color=color,
                        length=length,
                        from_label=from_label,
                        to_label=to_label,
                        system=seg_sys,
                    )
                )
            disc = seg.disconnect_pin._disconnect
            if disc is not None:
                disconnect_segs.setdefault(id(disc), []).append((seg, wid, len_a, len_b))
            continue

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
                color=color,
                length=length,
                from_label=_endpoint_label(seg.end_a),
                to_label=_endpoint_label(seg.end_b),
                system=seg_sys,
            )
        )

    wires.sort(key=lambda r: (_gauge_sort_key(r.gauge), r.color, _natsort_key(r.wire_id)))

    system_totals: dict[str, SystemTotals] = {}
    for w in wires:
        s = system_totals.setdefault(w.system or "—", SystemTotals())
        s.wires += 1
        s.conductors += 1
        if w.length is None:
            s.unresolved += 1
        else:
            s.total_length += w.length
    for c in shielded_cables:
        s = system_totals.setdefault(c.system or "—", SystemTotals())
        s.cables += 1
        s.conductors += c.conductors
        if c.length is None:
            s.unresolved += 1
        else:
            s.total_length += c.length

    connectors: list[tuple[str, str, int]] = []
    for comp in harness.components:
        for conn_name, conn in comp._connectors.items():
            connectors.append((comp.label, conn_name, len(getattr(conn, "_pins", {}))))

    terminals_by_type: dict[str, list[str]] = {}
    for t in harness.terminals:
        terminals_by_type.setdefault(type(t).__name__, []).append(t.id)

    disconnects: list[DisconnectEntry] = []
    for disc in harness.disconnects:
        rows: list[DisconnectPinRow] = []
        for pin_num, pin in disc._pins.items():
            wid = ""
            gauge: int | str = ""
            color = ""
            from_label = ""
            to_label = ""
            if pin._can_bus is not None:
                cables = can_disc_cables.get((id(disc), id(pin._can_bus)), [])
                base_ids = can_disc_base_ids.get((id(disc), id(pin._can_bus)), [])
                if cables:
                    wid = ", ".join(base_ids) if base_ids else ", ".join(r.cable_id for r in cables)
                    from_label = cables[0].from_label
                    to_label = cables[-1].to_label
                else:
                    from_label = f"CAN bus {pin._can_bus.name!r}"
                    to_label = f"{len(pin._segments)} stub(s)"
                if pin._segments:
                    gauge = pin._segments[0].gauge
                    color = pin._segments[0].color
            elif pin._shield_group is not None and pin._shield_group.single_oval:
                # CAN-bus shield: look up the cables on this disconnect's bus.
                bus = next(
                    (p._can_bus for p in disc._pins.values() if p._can_bus is not None and p._shield_group is None),
                    None,
                )
                cables = can_disc_cables.get((id(disc), id(bus)), []) if bus is not None else []
                base_ids = can_disc_base_ids.get((id(disc), id(bus)), []) if bus is not None else []
                if cables:
                    wid = ", ".join(base_ids) if base_ids else ", ".join(r.cable_id for r in cables)
                    from_label = cables[0].from_label
                    to_label = cables[-1].to_label
                    gauge = "drain"
                else:
                    from_label = "(shield foil)"
                    to_label = "(shield foil)"
            elif pin._shield_group is not None:
                sc_rows = sg_to_rows.get(id(pin._shield_group), [])
                if sc_rows:
                    canonical = getattr(pin._shield_group, "wire_id", "") or (
                        pin._shield_group.label.strip() if pin._shield_group.label else ""
                    )
                    wid = canonical or ", ".join(r.cable_id for r in sc_rows)
                    seen_from: list[str] = []
                    seen_to: list[str] = []
                    for r in sc_rows:
                        if r.from_label not in seen_from:
                            seen_from.append(r.from_label)
                        if r.to_label not in seen_to:
                            seen_to.append(r.to_label)
                    from_label = ", ".join(seen_from)
                    to_label = ", ".join(seen_to)
                    gauge = "drain"
                else:
                    from_label = "(shield foil)"
                    to_label = "(shield foil)"
            else:
                seg = pin._segment
                if seg is not None:
                    for matched_seg, matched_wid, _la, _lb in disconnect_segs.get(id(disc), []):
                        if matched_seg is seg:
                            wid = matched_wid
                            break
                    if not wid:
                        # Conductor inside a shielded group: use the group's
                        # canonical id so the row isn't blank.
                        wid = seg.wire_id or (
                            getattr(seg.shield_group, "wire_id", "") if seg.shield_group is not None else ""
                        )
                    gauge = seg.gauge
                    color = seg.color
                    from_label = _endpoint_label(seg.end_a)
                    to_label = _endpoint_label(seg.end_b)
            rows.append(
                DisconnectPinRow(
                    pin=str(pin_num),
                    signal_name=pin.signal_name,
                    wire_id=wid,
                    gauge=gauge,
                    color=color,
                    from_label=from_label,
                    to_label=to_label,
                )
            )
        rows.sort(key=lambda r: _natsort_key(r.pin))
        disconnects.append(
            DisconnectEntry(
                id=disc.id,
                label=disc.label,
                part_number=disc.part_number,
                pins=rows,
            )
        )

    return Bom(
        wires=wires,
        gauge_totals=gauge_totals,
        connectors=connectors,
        terminals_by_type=terminals_by_type,
        disconnects=disconnects,
        shielded_cables=shielded_cables,
        system_totals=system_totals,
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


def _shield_label(r: BomShieldedRow) -> str:
    return "foil+drain" if r.has_drain else "foil"


def _bom_combined_rows(bom: Bom, harness: "Harness") -> list[list[str]]:
    rows: list[tuple[str, str, list[str]]] = []
    for r in bom.wires:
        rows.append(
            (
                r.system or "",
                r.wire_id,
                [
                    r.wire_id,
                    "1",
                    str(r.gauge),
                    r.color or "",
                    harness.format_length(r.length),
                    "",
                    r.from_label,
                    r.to_label,
                ],
            )
        )
    for r in bom.shielded_cables:
        rows.append(
            (
                r.system or "",
                r.cable_id,
                [
                    r.cable_id,
                    str(r.conductors),
                    str(r.gauge),
                    r.color or "",
                    harness.format_length(r.length),
                    _shield_label(r),
                    r.from_label,
                    r.to_label,
                ],
            )
        )
    rows.sort(key=lambda t: (t[0], _natsort_key(t[1])))
    return [r[2] for r in rows]


_COMBINED_HEADERS = ["ID", "Cond.", "Gauge", "Color", "Length", "Shield", "From", "To"]


def _bom_gauge_rows(bom: Bom, harness: "Harness") -> list[list[str]]:
    return [
        [g, str(t.count), harness.format_length(t.total_length if t.count > t.unresolved else None), str(t.unresolved)]
        for g, t in sorted(bom.gauge_totals.items(), key=lambda kv: _gauge_sort_key(kv[0]))
    ]


def _bom_system_rows(bom: Bom, harness: "Harness") -> list[list[str]]:
    rows = []
    for sys_code, t in sorted(bom.system_totals.items()):
        items = t.wires + t.cables
        length = harness.format_length(t.total_length) if t.total_length and t.unresolved < items else "—"
        rows.append([sys_code, str(t.wires), str(t.cables), str(t.conductors), length, str(t.unresolved)])
    return rows


def _bom_summary_rows(bom: Bom, harness: "Harness") -> list[list[str]]:
    total_wires = len(bom.wires)
    total_cables = len(bom.shielded_cables)
    total_conductors = total_wires + sum(c.conductors for c in bom.shielded_cables)
    total_pins = sum(p for _, _, p in bom.connectors)
    total_terminals = sum(len(ids) for ids in bom.terminals_by_type.values())
    return [
        ["Components", str(len(harness.components))],
        ["Connectors", str(len(bom.connectors))],
        ["Connector pins", str(total_pins)],
        ["Wires", str(total_wires)],
        ["Shielded cables", str(total_cables)],
        ["Total conductors", str(total_conductors)],
        ["Terminals", str(total_terminals)],
        ["Disconnects", str(len(bom.disconnects))],
        ["Systems", str(len(bom.system_totals))],
    ]


def _bom_connector_rows(bom: Bom) -> list[list[str]]:
    return [[c, n, str(p)] for c, n, p in bom.connectors]


def _bom_terminal_rows(bom: Bom) -> list[list[str]]:
    return [[t, str(len(ids)), ", ".join(ids)] for t, ids in sorted(bom.terminals_by_type.items())]


def _bom_disconnect_pin_rows(entry: DisconnectEntry) -> list[list[str]]:
    return [[r.pin, r.signal_name, r.wire_id, str(r.gauge), r.color, r.from_label, r.to_label] for r in entry.pins]


def render_bom_md(bom: Bom, harness: "Harness") -> str:
    parts: list[str] = [f"# Bill of Materials — {harness.name}", ""]

    parts += ["## Wires & cables", ""]
    parts.append(_md_table(_COMBINED_HEADERS, _bom_combined_rows(bom, harness)))

    parts += ["", "## Summary", ""]
    parts.append(_md_table(["Metric", "Count"], _bom_summary_rows(bom, harness)))

    if bom.system_totals:
        parts += ["", "## Totals by system", ""]
        parts.append(
            _md_table(
                ["System", "Wires", "Cables", "Conductors", "Total Length", "Unresolved"],
                _bom_system_rows(bom, harness),
            )
        )

    parts += ["", "## Totals by gauge", ""]
    parts.append(_md_table(["Gauge", "Count", "Total Length", "Unresolved"], _bom_gauge_rows(bom, harness)))

    parts += ["", "## Connectors", ""]
    parts.append(_md_table(["Component", "Connector", "Pins"], _bom_connector_rows(bom)))

    parts += ["", "## Terminals", ""]
    parts.append(_md_table(["Type", "Count", "IDs"], _bom_terminal_rows(bom)))

    if bom.disconnects:
        parts += ["", "## Disconnects", ""]
        for entry in bom.disconnects:
            header = f"### {entry.id}"
            if entry.label:
                header += f" — {entry.label}"
            if entry.part_number:
                header += f"  ({entry.part_number})"
            parts += [header, ""]
            parts.append(
                _md_table(
                    ["Pin", "Signal", "Wire ID", "Gauge", "Color", "From", "To"],
                    _bom_disconnect_pin_rows(entry),
                )
            )
            parts.append("")

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
    _csv_section(buf, "Wires & cables", _COMBINED_HEADERS, _bom_combined_rows(bom, harness))
    buf.write("\n")
    _csv_section(buf, "Summary", ["Metric", "Count"], _bom_summary_rows(bom, harness))
    if bom.system_totals:
        buf.write("\n")
        _csv_section(
            buf,
            "Totals by system",
            ["System", "Wires", "Cables", "Conductors", "Total Length", "Unresolved"],
            _bom_system_rows(bom, harness),
        )
    buf.write("\n")
    _csv_section(
        buf, "Totals by gauge", ["Gauge", "Count", "Total Length", "Unresolved"], _bom_gauge_rows(bom, harness)
    )
    buf.write("\n")
    _csv_section(buf, "Connectors", ["Component", "Connector", "Pins"], _bom_connector_rows(bom))
    buf.write("\n")
    _csv_section(buf, "Terminals", ["Type", "Count", "IDs"], _bom_terminal_rows(bom))
    for entry in bom.disconnects:
        buf.write("\n")
        title = f"Disconnect {entry.id}"
        if entry.label:
            title += f" — {entry.label}"
        if entry.part_number:
            title += f" ({entry.part_number})"
        _csv_section(
            buf,
            title,
            ["Pin", "Signal", "Wire ID", "Gauge", "Color", "From", "To"],
            _bom_disconnect_pin_rows(entry),
        )
    return buf.getvalue()
