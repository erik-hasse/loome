from __future__ import annotations

from dataclasses import dataclass, field

from .._internal.endpoints import other_endpoint
from .._internal.shields import segment_shield_for_endpoint
from ..harness import Harness
from ..layout.engine import LayoutResult, PinRowInfo
from ..model import Pin, ShieldGroup, SpliceNode, WireSegment
from .colors import _SHIELD_PALETTE

ShieldPalette = dict[int, tuple[str, str | None]]


@dataclass
class RowIndex:
    """Typed lookups over layout rows used by SVG render passes."""

    class_pin_to_row: dict[int, PinRowInfo] = field(default_factory=dict)
    inst_pin_to_row: dict[int, PinRowInfo] = field(default_factory=dict)
    class_pin_to_rows: dict[int, list[PinRowInfo]] = field(default_factory=dict)
    inst_pin_to_rows: dict[int, list[PinRowInfo]] = field(default_factory=dict)
    segment_to_rows: dict[int, list[PinRowInfo]] = field(default_factory=dict)

    @classmethod
    def from_layout(cls, layout: LayoutResult) -> "RowIndex":
        idx = cls()
        for row in layout.all_rows:
            if not row.is_continuation:
                idx.class_pin_to_row.setdefault(id(row.class_pin), row)
                idx.inst_pin_to_row.setdefault(id(row.pin), row)
            idx.class_pin_to_rows.setdefault(id(row.class_pin), []).append(row)
            idx.inst_pin_to_rows.setdefault(id(row.pin), []).append(row)
            if row.segment is not None:
                idx.segment_to_rows.setdefault(id(row.segment), []).append(row)
        return idx

    def row_for_pin(self, pin: Pin) -> PinRowInfo | None:
        return self.class_pin_to_row.get(id(pin)) or self.inst_pin_to_row.get(id(pin))

    def primary_inst_row(self, pin: Pin) -> PinRowInfo | None:
        return self.inst_pin_to_row.get(id(pin))

    def rows_for_class_pin(self, pin: Pin) -> list[PinRowInfo]:
        return self.class_pin_to_rows.get(id(pin), [])

    def rows_for_inst_pin(self, pin: Pin) -> list[PinRowInfo]:
        return self.inst_pin_to_rows.get(id(pin), [])

    def rows_for_segment(self, seg: WireSegment) -> list[PinRowInfo]:
        return self.segment_to_rows.get(id(seg), [])

    @property
    def rendered_pin_ids(self) -> set[int]:
        return set(self.inst_pin_to_row.keys())


@dataclass
class RenderContext:
    rows: RowIndex
    pin_shield_palette: ShieldPalette
    shield_by_row_id: dict[int, ShieldGroup]
    shield_by_pin: dict[int, ShieldGroup]

    def shield_for_row(self, row: PinRowInfo) -> ShieldGroup | None:
        return self.shield_by_row_id.get(id(row)) or self.shield_by_pin.get(id(row.class_pin))


def build_render_context(harness: Harness, layout: LayoutResult) -> RenderContext:
    rows = RowIndex.from_layout(layout)
    palette = _build_pin_shield_palette(harness, layout)
    return RenderContext(
        rows=rows,
        pin_shield_palette=palette,
        shield_by_row_id=_build_row_shields(layout),
        shield_by_pin=_build_pin_shields(harness, rows),
    )


def _build_pin_shield_palette(harness: Harness, layout: LayoutResult) -> ShieldPalette:
    palette: ShieldPalette = {}
    for sg in harness.shield_groups:
        if sg.cable_only:
            continue
        for idx, pin in enumerate(sg.pins):
            palette[id(pin)] = _SHIELD_PALETTE[min(idx, len(_SHIELD_PALETTE) - 1)]

    for sg in harness.shield_groups:
        for pin in sg.pins:
            src = palette.get(id(pin))
            if src is None:
                continue
            for seg in pin._connections:
                remote = other_endpoint(seg, pin)
                if isinstance(remote, Pin) and id(remote) not in palette:
                    palette[id(remote)] = src

    for row in layout.all_rows:
        class_entry = palette.get(id(row.class_pin))
        if class_entry is not None and id(row.pin) not in palette:
            palette[id(row.pin)] = class_entry
    return palette


def _build_row_shields(layout: LayoutResult) -> dict[int, ShieldGroup]:
    by_row: dict[int, ShieldGroup] = {}
    for row in layout.all_rows:
        seg = row.segment
        if seg is None:
            continue
        sg = segment_shield_for_endpoint(seg, row.pin, row.class_pin)
        if sg is not None and not sg.cable_only:
            by_row[id(row)] = sg
    return by_row


def _build_pin_shields(harness: Harness, rows: RowIndex) -> dict[int, ShieldGroup]:
    by_pin: dict[int, ShieldGroup] = {}
    for sg in harness.shield_groups:
        if sg.cable_only:
            continue
        for pin in sg.pins:
            _mark_pin_and_class_row(by_pin, rows, pin, sg)
            for seg in pin._connections:
                remote = other_endpoint(seg, pin)
                if isinstance(remote, Pin):
                    _mark_pin_and_class_row(by_pin, rows, remote, sg)
        for seg in sg.segments:
            for endpoint in (seg.end_a, seg.end_b):
                if isinstance(endpoint, Pin):
                    _mark_pin_and_class_row(by_pin, rows, endpoint, sg)
                elif isinstance(endpoint, SpliceNode):
                    _mark_splice_upstream_pins(by_pin, rows, endpoint, seg, sg)
    return by_pin


def _mark_pin_and_class_row(
    by_pin: dict[int, ShieldGroup],
    rows: RowIndex,
    pin: Pin,
    sg: ShieldGroup,
) -> None:
    by_pin[id(pin)] = sg
    row = rows.primary_inst_row(pin)
    if row is not None:
        by_pin[id(row.class_pin)] = sg


def _mark_splice_upstream_pins(
    by_pin: dict[int, ShieldGroup],
    rows: RowIndex,
    splice: SpliceNode,
    shielded_seg: WireSegment,
    sg: ShieldGroup,
) -> None:
    for other_seg in splice._connections:
        if other_seg is shielded_seg:
            continue
        other_ep = other_endpoint(other_seg, splice)
        if isinstance(other_ep, Pin):
            _mark_pin_and_class_row(by_pin, rows, other_ep, sg)
