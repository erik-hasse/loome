from __future__ import annotations

from dataclasses import dataclass, field

from ..harness import Harness
from ..model import Component, Connector, Pin, SpliceNode, WireSegment
from .geometry import Rect
from .ordering import (
    _shield_ids as _pin_shield_ids,
)
from .ordering import (
    pin_sort_keys as _sort_pin_attrs,
)
from .ordering import (
    pin_target_key as _pin_target_key,
)
from .ordering import (
    segment_target_key as _segment_target_key,
)
from .ordering import (
    sort_legs as _sort_legs,
)

MARGIN = 20
SECTION_GAP = 14
COMPONENT_HEADER_H = 28
CONNECTOR_HEADER_H = 22
PIN_ROW_H = 22
GROUP_GAP = 14  # vertical gap inserted between pin groups with different remote targets
COMPONENT_GAP_EXTRA = 12  # added on top of GROUP_GAP when groups target different remote components
FIRST_GROUP_PAD = 12  # extra top padding before the first group when it needs a label above it
SHIELD_HEADER_PAD = 20  # gap when shield-mates cross to a different remote component (room for header label)
CONNECTOR_BOTTOM_PAD = 6  # breathing room after last pin row in a connector (before next header)
SECTION_BOTTOM_PAD = 6  # breathing room between last pin row and section border bottom
DRAIN_STUB_H = 16  # extra bottom padding when a shield group has a drain terminal
DRAIN_GROUP_GAP = 22  # minimum clearance after a pin group that ends with a drained shield (drain stem + triangle)
PIN_NUM_W = 36
PIN_NAME_W = 160  # default; layout() may widen based on actual pin names
REMOTE_BOX_W = 140  # default; layout() may widen based on actual remote names
REMOTE_BOX_PIN_NUM_W = 26
REMOTE_BOX_X_OFFSET = 340  # offset of remote box from wire_start_x
REMOTE_BOX_RIGHT_PAD = 20  # gap between remote box and section right edge
PIN_NAME_CHAR_W = 6.2  # 10px monospace
REMOTE_NAME_CHAR_W = 5.6  # 9px monospace
PIN_NAME_PAD = 14
REMOTE_NAME_PAD = 10
WIRE_AREA_W = 500  # default; layout() recomputes from REMOTE_BOX_W
CANVAS_W = MARGIN * 2 + PIN_NUM_W + PIN_NAME_W + WIRE_AREA_W


@dataclass
class PinRowInfo:
    pin: Pin
    class_pin: Pin
    rect: Rect
    wire_start_x: float
    wire_end_x: float
    # The specific outgoing segment this row draws. Set when a pin has more
    # than one direct connection (each leg gets its own row). None for
    # single-connection pins and for pins routed through a SpliceNode (which
    # are still drawn as one tall row with the existing fan-out renderer).
    segment: WireSegment | None = None
    # True for sub-rows after the primary row of a multi-connection pin.
    # Continuation rows skip the pin number / signal name when drawn.
    is_continuation: bool = False
    # Set on the primary row only: the additional sub-rows that share this
    # pin. Renderer walks these to draw the bullet + drop-down branches.
    continuation_rows: list["PinRowInfo"] = field(default_factory=list)
    # Back-reference set on continuation rows pointing to their primary.
    primary_row: "PinRowInfo | None" = None


@dataclass
class PinGroup:
    """Consecutive pin rows that share the same remote target."""

    rows: list[PinRowInfo]
    target_key: tuple  # ('component', ...) | ('terminal', ...) | ('unconnected',)
    first_in_section: bool = False  # True when no gap precedes this group (label needs room)


@dataclass
class _RowCtx:
    """Per-row context fed into ``_row_separator`` to decide the gap before this row.

    Lives only during ``layout()``. The row this describes is the *next* one to
    be emitted; the gap is `_row_separator(prev_ctx, this_ctx)`.
    """

    target_key: tuple
    shield_ids: frozenset[int]
    is_drained: bool
    is_first_leg_of_pin: bool  # False for continuation legs of a multi-direct pin


def _row_separator(prev: _RowCtx | None, new: _RowCtx) -> int:
    """Return the vertical gap to insert before a row described by ``new``.

    Single source of truth for inter-row spacing. Rules (in priority order):

    - First row in a section/connector: ``FIRST_GROUP_PAD`` if the row's target
      is a component (its remote box needs a label above it), else 0.
    - Continuation leg of a multi-direct pin: 0, plus ``COMPONENT_GAP_EXTRA``
      if this leg targets a different remote component (header room).
    - Same target as previous: 0 unless leaving a drained shield.
    - Different target with overlapping shield (shield-mates): keep close, but
      add ``SHIELD_HEADER_PAD`` if the remote component changes.
    - Different target without shield overlap: ``GROUP_GAP``, plus
      ``COMPONENT_GAP_EXTRA`` if the remote component also changes.

    Drained-shield boundary: when leaving a drained shield's last row, the
    drain triangle hangs ~``DRAIN_GROUP_GAP`` below it. We use ``max`` (not
    sum) with whatever group/component gap applies, so the spacing stays
    consistent instead of stacking.
    """
    if prev is None:
        return FIRST_GROUP_PAD if new.target_key[0] == "component" else 0

    leaving_drain = prev.is_drained and prev.shield_ids and not (prev.shield_ids & new.shield_ids)
    drain_floor = DRAIN_GROUP_GAP if leaving_drain else 0

    if not new.is_first_leg_of_pin:
        # Continuation leg of the same pin.
        comp_extra = COMPONENT_GAP_EXTRA if _components_differ(prev.target_key, new.target_key) else 0
        return max(drain_floor, comp_extra)

    if prev.target_key == new.target_key:
        return drain_floor

    shield_overlap = bool(prev.shield_ids & new.shield_ids)
    comp_extra = COMPONENT_GAP_EXTRA if _components_differ(prev.target_key, new.target_key) else 0
    if shield_overlap:
        # Shield-mates: keep close so a single oval can wrap them; insert header
        # room when the remote component changes OR when we're entering a component
        # group from a non-component group (e.g. terminal→component in a mixed
        # connection-level shield — the remote box still needs a label above it).
        needs_header = comp_extra or (new.target_key[0] == "component" and prev.target_key[0] != "component")
        return max(drain_floor, SHIELD_HEADER_PAD if needs_header else 0)
    return max(drain_floor, GROUP_GAP) + comp_extra


@dataclass
class LayoutResult:
    section_rects: dict[int, Rect]
    connector_rects: dict[int, Rect]
    pin_rows: dict[int, PinRowInfo]  # id(inst_pin) → primary row
    all_rows: list[PinRowInfo]  # every row in y order, including continuations
    pin_groups: list[PinGroup]
    canvas_width: float
    canvas_height: float
    pin_name_w: float = PIN_NAME_W
    remote_box_w: float = REMOTE_BOX_W
    wire_area_w: float = WIRE_AREA_W


def _effective_pin(class_pin: Pin, inst_pin: Pin | None) -> Pin:
    """Return inst_pin if it has connections, else class_pin."""
    return inst_pin if (inst_pin is not None and inst_pin._connections) else class_pin


def _pin_is_connected(class_pin: Pin, inst_pin: Pin | None = None) -> bool:
    """Return True if this pin has at least one connection at either level."""
    return bool(_effective_pin(class_pin, inst_pin)._connections)


def _pin_display_rows(class_pin: Pin, inst_pin: Pin | None = None) -> int:
    """Number of visual sub-rows this pin needs (> 1 when it connects through a splice)."""
    use = _effective_pin(class_pin, inst_pin)
    if not use._connections:
        return 1
    total = 0
    for seg in use._connections:
        remote = seg.end_b if seg.end_a is use else seg.end_a
        if isinstance(remote, SpliceNode):
            outward = [s for s in remote._connections if s is not seg]
            total += max(len(outward), 1)
        else:
            total += 1
    return max(total, 1)


def _has_splice_connection(class_pin: Pin, inst_pin: Pin | None = None) -> bool:
    """True if any of this pin's connections terminates at a SpliceNode."""
    use = _effective_pin(class_pin, inst_pin)
    for seg in use._connections:
        remote = seg.end_b if seg.end_a is use else seg.end_a
        if isinstance(remote, SpliceNode):
            return True
    return False


def _pin_outgoing_segments(class_pin: Pin, inst_pin: Pin | None = None) -> list[WireSegment]:
    """Return the segments outgoing from this pin (preferring instance over class).

    Multi-leg pins are reordered per the rules in ``ordering.sort_legs``: terminal
    legs first (so the terminal wire takes the primary row), then by remote
    connector, then by remote pin number.
    """
    use = _effective_pin(class_pin, inst_pin)
    segments = list(use._connections)
    if len(segments) <= 1:
        return segments
    return _sort_legs(segments, use)


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


def _class_pin_map(cls, base_cls) -> dict[str, Pin]:
    return dict(_iter_class_pins(cls, base_cls))


def _components_differ(k1: tuple | None, k2: tuple | None) -> bool:
    """True when both keys are component-targets pointing at different components."""
    if k1 is None or k2 is None:
        return False
    if len(k1) < 2 or len(k2) < 2:
        return False
    return k1[0] == "component" and k2[0] == "component" and k1[1] != k2[1]


def _collect_displayed_signal_names(harness: Harness, show_unconnected: bool) -> tuple[list[str], list[str]]:
    """Return (local_names, remote_names) — signal names of pins that will render.

    Local names are pins that own a row; remote names are pins on the other end
    of segments (rendered inside remote boxes). Used to size the local pin-name
    column and the remote box width before laying out rows.
    """
    local: list[str] = []
    remote: list[str] = []

    def _walk(comp):
        comp_cls = type(comp)
        for attr_name, cp in _iter_class_pins(comp_cls, Component):
            ip = comp._direct_pins.get(attr_name)
            if not show_unconnected and not _pin_is_connected(cp, ip):
                continue
            local.append((ip or cp).signal_name)
            for seg in _pin_outgoing_segments(cp, ip):
                rp = seg.end_b if seg.end_a is (ip or cp) else seg.end_a
                if isinstance(rp, Pin):
                    remote.append(rp.signal_name)
        for conn in comp._connectors.values():
            for attr_name, cp in _iter_class_pins(type(conn), Connector):
                ip = getattr(conn, attr_name, None)
                if not isinstance(ip, Pin):
                    ip = None
                if not show_unconnected and not _pin_is_connected(cp, ip):
                    continue
                local.append((ip or cp).signal_name)
                for seg in _pin_outgoing_segments(cp, ip):
                    rp = seg.end_b if seg.end_a is (ip or cp) else seg.end_a
                    if isinstance(rp, Pin):
                        remote.append(rp.signal_name)

    for comp in harness.components:
        if comp.render:
            _walk(comp)
    return local, remote


def layout(harness: Harness, show_unconnected: bool = False) -> LayoutResult:
    section_rects: dict[int, Rect] = {}
    connector_rects: dict[int, Rect] = {}
    pin_rows: dict[int, PinRowInfo] = {}
    all_rows: list[PinRowInfo] = []
    pin_groups: list[PinGroup] = []

    local_names, remote_names = _collect_displayed_signal_names(harness, show_unconnected)
    max_local = max((len(n) for n in local_names), default=0)
    max_remote = max((len(n) for n in remote_names), default=0)
    pin_name_w = max(PIN_NAME_W, int(max_local * PIN_NAME_CHAR_W) + PIN_NAME_PAD)
    remote_box_w = max(
        REMOTE_BOX_W,
        REMOTE_BOX_PIN_NUM_W + int(max_remote * REMOTE_NAME_CHAR_W) + REMOTE_NAME_PAD,
    )
    wire_area_w = REMOTE_BOX_X_OFFSET + remote_box_w + REMOTE_BOX_RIGHT_PAD
    canvas_w = MARGIN * 2 + PIN_NUM_W + pin_name_w + wire_area_w
    inner_w_local = canvas_w - MARGIN * 2

    # Pre-compute set of pin ids (class or instance) that belong to a drained shield.
    # Used to inject extra gap after groups that end at such a pin.
    drained_pin_ids: set[int] = set()
    for sg in harness.shield_groups:
        if sg.drain is None and sg.drain_remote is None:
            continue
        for p in sg.pins:
            drained_pin_ids.add(id(p))
        for seg in sg.segments:
            for ep in (seg.end_a, seg.end_b):
                if isinstance(ep, Pin):
                    drained_pin_ids.add(id(ep))

    y = MARGIN
    inner_x = MARGIN
    inner_w = inner_w_local
    wire_start_x = inner_x + PIN_NUM_W + pin_name_w
    wire_end_x = inner_x + inner_w

    def _emit_pin(
        class_pin: Pin,
        inst_pin: Pin,
        prev_ctx: _RowCtx | None,
        current_group: PinGroup | None,
    ) -> tuple[_RowCtx, PinGroup]:
        """Emit row(s) for one pin, advancing ``y`` and creating PinGroups as needed.

        Returns ``(prev_ctx, current_group)`` updated for the next pin.
        """
        nonlocal y
        is_drained = id(class_pin) in drained_pin_ids or id(inst_pin) in drained_pin_ids
        pin_shields = frozenset(_pin_shield_ids(class_pin, inst_pin))
        segments = _pin_outgoing_segments(class_pin, inst_pin)

        if not segments or _has_splice_connection(class_pin, inst_pin) or len(segments) == 1:
            seg0 = segments[0] if len(segments) == 1 else None
            seg_shields = frozenset({id(seg0.shield_group)}) if (seg0 and seg0.shield_group) else pin_shields
            key = _pin_target_key(class_pin, inst_pin)
            ctx = _RowCtx(
                target_key=key,
                shield_ids=seg_shields,
                is_drained=is_drained,
                is_first_leg_of_pin=True,
            )
            y += _row_separator(prev_ctx, ctx)
            if current_group is None or current_group.target_key != key:
                current_group = PinGroup(rows=[], target_key=key, first_in_section=(prev_ctx is None))
                pin_groups.append(current_group)
            row_h = _pin_display_rows(class_pin, inst_pin) * PIN_ROW_H
            row_info = PinRowInfo(
                pin=inst_pin,
                class_pin=class_pin,
                rect=Rect(inner_x, y, inner_w, row_h),
                wire_start_x=wire_start_x,
                wire_end_x=wire_end_x,
                segment=seg0,
            )
            pin_rows[id(inst_pin)] = row_info
            all_rows.append(row_info)
            current_group.rows.append(row_info)
            y += row_h
            return ctx, current_group

        # Multi-direct: one PIN_ROW_H sub-row per leg, each with its own ctx.
        primary: PinRowInfo | None = None
        ctx: _RowCtx | None = None
        for i, seg in enumerate(segments):
            leg_key = _segment_target_key(seg, inst_pin, inst_pin)
            seg_shields = frozenset({id(seg.shield_group)}) if seg.shield_group else frozenset()
            ctx = _RowCtx(
                target_key=leg_key,
                shield_ids=seg_shields,
                is_drained=is_drained,
                is_first_leg_of_pin=(i == 0),
            )
            y += _row_separator(prev_ctx, ctx)
            if current_group is None or current_group.target_key != leg_key:
                current_group = PinGroup(rows=[], target_key=leg_key, first_in_section=(prev_ctx is None))
                pin_groups.append(current_group)
            sub = PinRowInfo(
                pin=inst_pin,
                class_pin=class_pin,
                rect=Rect(inner_x, y, inner_w, PIN_ROW_H),
                wire_start_x=wire_start_x,
                wire_end_x=wire_end_x,
                segment=seg,
                is_continuation=(i > 0),
            )
            if i == 0:
                primary = sub
                pin_rows[id(inst_pin)] = sub
            else:
                assert primary is not None
                primary.continuation_rows.append(sub)
                sub.primary_row = primary
            all_rows.append(sub)
            current_group.rows.append(sub)
            y += PIN_ROW_H
            prev_ctx = ctx
        assert ctx is not None and current_group is not None
        return ctx, current_group

    for comp in harness.components:
        if not comp.render:
            continue
        section_start_y = y
        y += COMPONENT_HEADER_H

        # ── direct pins (no connector header) ──────────────────────────────
        comp_cls = type(comp)
        direct_class_pins = _class_pin_map(comp_cls, Component)
        direct_pin_attrs = _sort_pin_attrs(
            list(direct_class_pins.keys()),
            get_class_pin=direct_class_pins.get,
            get_inst_pin=comp._direct_pins.get,
        )
        prev_ctx: _RowCtx | None = None
        current_group: PinGroup | None = None

        for attr_name in direct_pin_attrs:
            inst_pin = comp._direct_pins.get(attr_name)
            if inst_pin is None:
                continue
            class_pin = direct_class_pins.get(attr_name, inst_pin)
            if not show_unconnected and not _pin_is_connected(class_pin, inst_pin):
                continue
            prev_ctx, current_group = _emit_pin(class_pin, inst_pin, prev_ctx, current_group)

        # ── connectors ─────────────────────────────────────────────────────
        last_conn_drain_extra = 0
        for conn_name, conn in comp._connectors.items():
            conn_cls = type(conn)
            conn_class_pins = _class_pin_map(conn_cls, Connector)
            conn_start_y = y
            y += CONNECTOR_HEADER_H

            prev_ctx = None  # restart spacing inside each connector
            current_group = None

            pin_attrs = _sort_pin_attrs(
                list(conn_class_pins.keys()),
                get_class_pin=conn_class_pins.get,
                get_inst_pin=lambda a: getattr(conn, a, None) if isinstance(getattr(conn, a, None), Pin) else None,
            )
            for attr_name in pin_attrs:
                inst_pin = getattr(conn, attr_name, None)
                if inst_pin is None or not isinstance(inst_pin, Pin):
                    continue
                class_pin = conn_class_pins.get(attr_name, inst_pin)
                if not show_unconnected and not _pin_is_connected(class_pin, inst_pin):
                    continue
                prev_ctx, current_group = _emit_pin(class_pin, inst_pin, prev_ctx, current_group)

            if current_group is None:
                # No pins emitted for this connector — skip rendering it entirely.
                y = conn_start_y
                continue
            conn_drain_extra = (
                DRAIN_STUB_H
                if any(
                    id(ri.class_pin) in drained_pin_ids or id(ri.pin) in drained_pin_ids for ri in current_group.rows
                )
                else 0
            )
            last_conn_drain_extra = conn_drain_extra
            y += CONNECTOR_BOTTOM_PAD + conn_drain_extra
            conn_rect = Rect(inner_x, conn_start_y, inner_w, y - conn_start_y)
            connector_rects[id(conn)] = conn_rect

        # Direct-pin components: add drain stub height when last group is drained.
        # Connector components: skip SECTION_BOTTOM_PAD when the last connector already
        # reserved drain space (CONNECTOR_BOTTOM_PAD + DRAIN_STUB_H) to avoid triple-stacking.
        if not comp._connectors:
            extra = (
                DRAIN_STUB_H
                if (
                    current_group is not None
                    and any(
                        id(ri.class_pin) in drained_pin_ids or id(ri.pin) in drained_pin_ids
                        for ri in current_group.rows
                    )
                )
                else 0
            )
            section_bottom_pad = SECTION_BOTTOM_PAD
        else:
            extra = 0
            section_bottom_pad = 0 if last_conn_drain_extra > 0 else SECTION_BOTTOM_PAD
        section_rect = Rect(inner_x, section_start_y, inner_w, y - section_start_y + section_bottom_pad + extra)
        section_rects[id(comp)] = section_rect
        y += section_bottom_pad + extra + SECTION_GAP

    canvas_height = y + MARGIN

    return LayoutResult(
        section_rects=section_rects,
        connector_rects=connector_rects,
        pin_rows=pin_rows,
        all_rows=all_rows,
        pin_groups=pin_groups,
        canvas_width=canvas_w,
        canvas_height=canvas_height,
        pin_name_w=pin_name_w,
        remote_box_w=remote_box_w,
        wire_area_w=wire_area_w,
    )
