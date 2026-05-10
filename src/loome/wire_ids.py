"""Stable, auto-generated wire IDs persisted in a sidecar YAML.

Wire IDs follow the format ``XXXGGCCNN`` (and ``XXXGGCCNNS`` for the two halves
of a wire crossing a disconnect):

  XXX  1-4 letter system code (from ``System(...)`` context or component default)
  GG   gauge zero-padded to 2 digits
  CC   2-letter color code, padded with ``_`` if the source code is 1 letter,
       or literally ``SH`` for shielded cables
  NN   counter unique within the system, zero-padded to 2 digits
  S    'A' (end_a side) / 'B' (end_b side) suffix on disconnect-split rows

Identity across edits is by canonicalized endpoint *fingerprint*: a sorted,
joined description of the wire's two endpoints (or, for a shielded cable, of
the group's member set). The sidecar (``<spec>.wires.yaml``) records
``fingerprint -> id``; on load we re-fingerprint each segment, look up its ID,
and only mint a new one for segments whose fingerprint isn't already on file.
Entries whose fingerprint no longer matches anything are kept in an ``orphans``
section so a rename can be recovered by hand.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from ._internal.endpoints import is_local_segment as _is_local_segment
from ._internal.endpoints import segment_fingerprint
from ._internal.shields import (
    is_single_oval_pin,
    segment_touches_single_oval_shield,
    segments_for_shield,
)
from ._internal.systems import DEFAULT_SYSTEM
from ._internal.systems import require_system as _require_system
from ._internal.systems import resolve_system as _resolve_system
from .model import (
    Pin,
    ShieldGroup,
    WireSegment,
)

if TYPE_CHECKING:
    from .harness import Harness


@dataclass
class _Entry:
    id: str
    fingerprint: str
    system: str
    kind: str  # "segment" or "shield"


@dataclass(frozen=True)
class WireIdEntry:
    id: str
    fingerprint: str
    system: str
    kind: str
    run_key: str


@dataclass
class WireIdAssignment:
    entries: list[WireIdEntry]
    orphans: list[WireIdEntry]
    sidecar_path: Path | None
    changed: bool = False


class WireIdCheckError(RuntimeError):
    """Raised when ``check=True`` detects that the sidecar would change."""


# ── fingerprints ────────────────────────────────────────────────────────────


def fingerprint_segment(seg: WireSegment) -> str:
    return segment_fingerprint(seg)


def fingerprint_shield(sg: ShieldGroup, members: list[WireSegment]) -> str:
    label = sg.label.strip() if sg.label else ""
    member_fps = sorted({fingerprint_segment(s) for s in members})
    body = "|".join(member_fps)
    if label:
        return f"shield:{label}:{body}"
    return f"shield:{body}"


# ── system resolution ──────────────────────────────────────────────────────


def _resolve_shield_system(sg: ShieldGroup, members: list[WireSegment], default: str | None) -> str:
    explicit: set[str] = set()
    for s in members:
        sys = _resolve_system(s, None)
        if sys is not None:
            explicit.add(sys)
    if len(explicit) > 1:
        raise ValueError(
            f"Shielded cable {fingerprint_shield(sg, members)} spans multiple systems: {sorted(explicit)}. "
            "Pick one explicitly."
        )
    if explicit:
        return next(iter(explicit))
    if default is None:
        raise ValueError(
            f"Shielded cable {fingerprint_shield(sg, members)} has no system and harness.default_system is None."
        )
    return default


# ── formatting ─────────────────────────────────────────────────────────────


def _format_gauge(gauge) -> str:
    try:
        return f"{int(gauge):02d}"
    except (TypeError, ValueError):
        return str(gauge) if gauge else "00"


def _format_color(seg: WireSegment) -> str:
    return (seg.effective_color or "W")[:2]


def _format_id(system: str, gauge_str: str, color_str: str, nn: int) -> str:
    return f"{system}{gauge_str}{color_str}{nn:02d}"


# ── sidecar I/O ────────────────────────────────────────────────────────────


def _sidecar_path(spec_path: Path) -> Path:
    return spec_path.with_suffix(".wires.yaml")


def _load_sidecar(path: Path) -> tuple[dict[str, _Entry], list[_Entry]]:
    if not path.exists():
        return {}, []
    data = yaml.safe_load(path.read_text()) or {}
    by_fp: dict[str, _Entry] = {}
    for raw in data.get("wires", []) or []:
        e = _Entry(
            id=raw["id"], fingerprint=raw["fingerprint"], system=raw.get("system", ""), kind=raw.get("kind", "segment")
        )
        by_fp[e.fingerprint] = e
    orphans = [
        _Entry(
            id=raw["id"], fingerprint=raw["fingerprint"], system=raw.get("system", ""), kind=raw.get("kind", "segment")
        )
        for raw in (data.get("orphans") or [])
    ]
    return by_fp, orphans


def _write_sidecar(path: Path, wires: list[_Entry], orphans: list[_Entry]) -> None:
    path.write_text(_dump_sidecar_text(wires, orphans))


def _dump_sidecar_text(wires: list[_Entry], orphans: list[_Entry]) -> str:
    def _dump(es: list[_Entry]) -> list[dict]:
        return [{"id": e.id, "fingerprint": e.fingerprint, "system": e.system, "kind": e.kind} for e in es]

    data = {
        "version": 1,
        "wires": _dump(sorted(wires, key=lambda e: e.id)),
        "orphans": _dump(orphans),
    }
    return yaml.safe_dump(data, sort_keys=False)


def _sidecar_would_change(path: Path, wires: list[_Entry], orphans: list[_Entry]) -> bool:
    current = path.read_text() if path.exists() else ""
    return current != _dump_sidecar_text(wires, orphans)


def _run_key(kind: str, fingerprint: str) -> str:
    return hashlib.sha256(f"{kind}:{fingerprint}".encode("utf-8")).hexdigest()[:16]


def _public_entry(entry: _Entry) -> WireIdEntry:
    return WireIdEntry(
        id=entry.id,
        fingerprint=entry.fingerprint,
        system=entry.system,
        kind=entry.kind,
        run_key=_run_key(entry.kind, entry.fingerprint),
    )


def harness_builder_key(harness: "Harness", entries: list[WireIdEntry]) -> str:
    """Return a stable key for localStorage/exported builder state."""
    labels = [getattr(component, "label", type(component).__name__) for component in harness.components]
    body = "\n".join([harness.name, *sorted(labels), *sorted(entry.run_key for entry in entries)])
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


# ── shield-group → member-segments ─────────────────────────────────────────


def _members_for_shield(sg: ShieldGroup, all_segments: list[WireSegment]) -> list[WireSegment]:
    return segments_for_shield(sg, all_segments)


# ── main entry point ───────────────────────────────────────────────────────


def assign_wire_ids(
    harness: "Harness",
    spec_path: Path | None,
    *,
    persist: bool | None = None,
    check: bool = False,
) -> WireIdAssignment:
    """Assign stable wire IDs to every segment + shield group.

    Loads the sidecar at ``<spec>.wires.yaml`` (if present), preserves any
    fingerprint→id mappings, and mints new IDs for fingerprints not on file
    (per system, NN continues from max+1). Pass ``persist=True`` to write the
    resulting sidecar back.

    If ``spec_path`` is None, IDs are still assigned in-memory but no sidecar
    is written or read (useful for tests). Set ``persist=False`` to read an
    existing sidecar and assign preview IDs without writing it.
    """
    sidecar = _sidecar_path(spec_path) if spec_path else None
    if persist is None:
        persist = sidecar is not None
    by_fp, orphans = _load_sidecar(sidecar) if sidecar else ({}, [])
    default_system = getattr(harness, "default_system", DEFAULT_SYSTEM)

    next_nn: dict[str, int] = {}
    for entry in list(by_fp.values()) + orphans:
        nn = _extract_nn(entry.id)
        if nn is None:
            continue
        next_nn[entry.system] = max(next_nn.get(entry.system, 0), nn)

    used_fps: set[str] = set()
    new_wires: list[_Entry] = []

    all_segments = harness.segments()

    # Pre-compute shield-group memberships and reserve their member segments
    # so we don't double-assign a per-segment ID to a shielded conductor.
    shield_members: dict[int, list[WireSegment]] = {}
    shielded_seg_ids: set[int] = set()
    for sg in harness.shield_groups:
        if sg.single_oval:
            continue  # CAN buses are handled separately by the BOM/renderer; skip.
        members = segments_for_shield(sg, all_segments)
        if not members:
            continue
        shield_members[id(sg)] = members
        for s in members:
            shielded_seg_ids.add(id(s))

    # ── 1) assign / preserve shield-group IDs ─────────────────────────────
    seen_sg: set[int] = set()
    for sg in harness.shield_groups:
        if id(sg) in seen_sg or id(sg) not in shield_members:
            continue
        seen_sg.add(id(sg))
        members = shield_members[id(sg)]
        fp = fingerprint_shield(sg, members)
        system = _resolve_shield_system(sg, members, default_system)
        gauge = _dominant_gauge(members)
        gauge_str = _format_gauge(gauge)
        existing = by_fp.get(fp)
        explicit_label = sg.label.strip() if sg.label else ""
        if explicit_label:
            wid = explicit_label  # user-provided label acts like an override
            if existing is not None:
                used_fps.add(fp)
        elif existing is not None:
            wid = existing.id
            used_fps.add(fp)
        else:
            nn = next_nn.get(system, 0) + 1
            if nn > 99:
                raise ValueError(f"system {system!r} would exceed 99 wires; split it into multiple systems")
            next_nn[system] = nn
            wid = _format_id(system, gauge_str, "SH", nn)
        sg.wire_id = wid  # type: ignore[attr-defined]
        for seg in members:
            seg.wire_id = wid
        new_wires.append(_Entry(id=wid, fingerprint=fp, system=system, kind="shield"))

    # ── 1b) CAN bus cables: one ID per adjacent device pair ─────────────
    # CAN segments are shared at the class level (one H / one L segment for
    # the whole bus regardless of device count), so we don't assign IDs to
    # underlying segments — we just compute one ID per (bus, adjacent-pair)
    # for BOM rows and renderer labels.
    can_pair_ids: dict[tuple[int, int, int], str] = {}  # (cbl_id, dev_a_id, dev_b_id) → wire_id

    # Mark every segment touching a CAN-bus pin as "shielded" for ID purposes,
    # whether or not the port appears on a CanBusLine. CAN ports auto-connect
    # their H/L pins to a shared "To CAN Bus" off-page reference; that plumbing
    # shouldn't surface as an individual wire.
    def _is_can_pin(ep) -> bool:
        return isinstance(ep, Pin) and is_single_oval_pin(ep)

    for seg in all_segments:
        if segment_touches_single_oval_shield(seg) or _is_can_pin(seg.end_a) or _is_can_pin(seg.end_b):
            shielded_seg_ids.add(id(seg))

    for cbl in harness.can_buses:
        # CAN cables always live in their own "CAN" system regardless of the
        # devices' systems — the bus is the system.
        system = "CAN"

        # Pick a representative gauge from any segment touching the bus.
        gauge_seg = next(
            (
                s
                for s in all_segments
                if (isinstance(s.end_a, Pin) and id(s.end_a) in cbl._pin_ids)
                or (isinstance(s.end_b, Pin) and id(s.end_b) in cbl._pin_ids)
            ),
            None,
        )
        gauge_str = _format_gauge(gauge_seg.gauge if gauge_seg is not None else 22)

        for dev_a, dev_b in zip(cbl.devices, cbl.devices[1:]):
            label_a = getattr(dev_a, "_component", None)
            label_a = label_a.label if label_a is not None else type(dev_a).__name__
            label_b = getattr(dev_b, "_component", None)
            label_b = label_b.label if label_b is not None else type(dev_b).__name__
            fp = f"canbus:{cbl.name}:{label_a}->{label_b}"

            existing = by_fp.get(fp)
            if existing is not None:
                wid = existing.id
                used_fps.add(fp)
            else:
                nn = next_nn.get(system, 0) + 1
                if nn > 99:
                    raise ValueError(f"system {system!r} would exceed 99 wires; split it into multiple systems")
                next_nn[system] = nn
                wid = _format_id(system, gauge_str, "SH", nn)
            can_pair_ids[(id(cbl), id(dev_a), id(dev_b))] = wid
            new_wires.append(_Entry(id=wid, fingerprint=fp, system=system, kind="canbus"))

    # Stash on harness for BOM / renderer consumption.
    harness._can_pair_ids = can_pair_ids  # type: ignore[attr-defined]

    # ── 2) assign / preserve per-segment IDs ──────────────────────────────
    for seg in all_segments:
        if id(seg) in shielded_seg_ids:
            continue  # already inherits the shield-group ID
        if _is_local_segment(seg):
            continue  # straps, local grounds, shield drain stubs — no ID, no BOM row
        fp = fingerprint_segment(seg)
        system = _require_system(seg, default_system)
        gauge_str = _format_gauge(seg.gauge)
        color_str = _format_color(seg)
        existing = by_fp.get(fp)
        if seg.wire_id:
            wid = seg.wire_id  # user override
            if existing is not None:
                used_fps.add(fp)
        elif existing is not None:
            wid = existing.id
            used_fps.add(fp)
        else:
            nn = next_nn.get(system, 0) + 1
            if nn > 99:
                raise ValueError(f"system {system!r} would exceed 99 wires; split it into multiple systems")
            next_nn[system] = nn
            wid = _format_id(system, gauge_str, color_str, nn)
        seg.wire_id = wid
        new_wires.append(_Entry(id=wid, fingerprint=fp, system=system, kind="segment"))

    # ── 3) anything in by_fp we never matched → orphan ────────────────────
    new_orphans = list(orphans)
    new_orphan_ids = {e.id for e in new_orphans}
    for fp, entry in by_fp.items():
        if fp in used_fps:
            continue
        if entry.id in new_orphan_ids:
            continue
        new_orphans.append(entry)

    changed = False
    if sidecar is not None:
        changed = _sidecar_would_change(sidecar, new_wires, new_orphans)
        if check and changed:
            raise WireIdCheckError(f"wire ID sidecar would change: {sidecar}")
        if persist and changed:
            _write_sidecar(sidecar, new_wires, new_orphans)
    return WireIdAssignment(
        entries=[_public_entry(e) for e in new_wires],
        orphans=[_public_entry(e) for e in new_orphans],
        sidecar_path=sidecar,
        changed=changed,
    )


def _extract_nn(wire_id: str) -> int | None:
    """Pull the trailing 2-digit NN out of a wire ID like 'AVI22B_07' or 'AVI22SH03A'."""
    s = wire_id
    if s and s[-1].isalpha() and not s[-1].isdigit():
        s = s[:-1]
    if len(s) < 2 or not s[-2:].isdigit():
        return None
    try:
        return int(s[-2:])
    except ValueError:
        return None


def _dominant_gauge(segs: list[WireSegment]):
    counts: dict = {}
    for s in segs:
        counts[s.gauge] = counts.get(s.gauge, 0) + 1
    if not counts:
        return 22
    return max(counts.items(), key=lambda kv: kv[1])[0]
