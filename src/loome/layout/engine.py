from __future__ import annotations

from dataclasses import dataclass

from ..harness import Harness
from ..model import Pin, SpliceNode, Terminal
from .geometry import Rect

MARGIN = 20
SECTION_GAP = 14
COMPONENT_HEADER_H = 28
CONNECTOR_HEADER_H = 22
PIN_ROW_H = 22
GROUP_GAP = 14  # vertical gap inserted between pin groups with different remote targets
FIRST_GROUP_PAD = 12  # extra top padding before the first group when it needs a label above it
CONNECTOR_BOTTOM_PAD = 6  # breathing room after last pin row in a connector (before next header)
SECTION_BOTTOM_PAD = 6  # breathing room between last pin row and section border bottom
DRAIN_STUB_H = 16  # extra bottom padding when a shield group has a drain terminal
DRAIN_GROUP_GAP = 8  # extra gap after a pin group that ends with a drained shield
PIN_NUM_W = 36
PIN_NAME_W = 160
WIRE_AREA_W = 300
CANVAS_W = MARGIN * 2 + PIN_NUM_W + PIN_NAME_W + WIRE_AREA_W  # 536


@dataclass
class PinRowInfo:
    pin: Pin
    class_pin: Pin
    rect: Rect
    wire_start_x: float
    wire_end_x: float


@dataclass
class PinGroup:
    """Consecutive pin rows that share the same remote target."""

    rows: list[PinRowInfo]
    target_key: tuple  # ('component', ...) | ('terminal', ...) | ('unconnected',)
    first_in_section: bool = False  # True when no gap precedes this group (label needs room)


@dataclass
class LayoutResult:
    section_rects: dict[int, Rect]
    connector_rects: dict[int, Rect]
    pin_rows: dict[int, PinRowInfo]
    pin_groups: list[PinGroup]
    canvas_width: float
    canvas_height: float


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


def _pin_shield_order(class_pin: Pin, inst_pin: Pin | None = None) -> int:
    """Sort key for shield palette ordering within a group (0=W, 1=WB, 2=WO, 999=unshielded).

    For source pins (end_a), returns their position in their own shield group.
    For remote pins (end_b), returns the source pin's position so ordering follows
    the physical wire color after palette propagation.
    """
    use = _effective_pin(class_pin, inst_pin)
    for seg in use._connections:
        if seg.end_b is use or seg.end_b is class_pin:
            src = seg.end_a  # this pin is end_b → source is end_a
        else:
            src = class_pin  # this pin is end_a → it is the source
        if isinstance(src, Pin) and src.shield_group is not None:
            for idx, p in enumerate(src.shield_group.pins):
                if p is src:
                    return idx
    # Fallback: direct shield group position (handles unconnected shielded pins)
    sg = class_pin.shield_group
    if sg is not None:
        for idx, p in enumerate(sg.pins):
            if p is class_pin:
                return idx
    return 999


def _sort_pin_attrs(
    pin_attrs: list[str],
    get_class_pin,
    get_inst_pin,
) -> list[str]:
    """Sort pin attribute names by (group order, shield palette order, original index).

    Preserves the encounter order of target groups while sorting pins within each
    group by W→WB→WO palette order.
    """
    group_order: dict[tuple, int] = {}
    keyed: list[tuple] = []
    for orig_idx, attr_name in enumerate(pin_attrs):
        cp = get_class_pin(attr_name)
        ip = get_inst_pin(attr_name)
        if cp is None:
            keyed.append((999, 999, orig_idx, attr_name))
            continue
        tk = _pin_target_key(cp, ip)
        if tk not in group_order:
            group_order[tk] = len(group_order)
        keyed.append((group_order[tk], _pin_shield_order(cp, ip), orig_idx, attr_name))
    keyed.sort(key=lambda x: x[:3])
    return [x[3] for x in keyed]


def _pin_target_key(class_pin: Pin, inst_pin: Pin | None = None) -> tuple:
    """Return a stable grouping key based on where this pin's first connection leads.

    Prefers instance-pin connections (wired at instance level) over class-pin connections.
    """
    use = _effective_pin(class_pin, inst_pin)
    if not use._connections:
        return ("unconnected",)
    seg = use._connections[0]
    remote = seg.end_b if seg.end_a is use else seg.end_a
    if isinstance(remote, Pin):
        # Jumper: both pins live in the same connector (or same direct-pin component)
        if inst_pin is not None:
            if inst_pin._connector is not None and inst_pin._connector is remote._connector:
                return ("jumper",)
            if (
                inst_pin._component is not None
                and inst_pin._component is remote._component
                and inst_pin._connector is None
                and remote._connector is None
            ):
                return ("jumper",)
        # Prefer instance identity so multiple instances of the same class get separate groups.
        comp_key = id(remote._component) if remote._component is not None else id(remote._component_class)
        return ("component", comp_key, id(remote._connector_class))
    elif isinstance(remote, Terminal):
        return ("terminal", id(remote))
    return ("other", id(remote))


def layout(harness: Harness, show_unconnected: bool = False) -> LayoutResult:
    section_rects: dict[int, Rect] = {}
    connector_rects: dict[int, Rect] = {}
    pin_rows: dict[int, PinRowInfo] = {}
    pin_groups: list[PinGroup] = []

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

    def _group_drain_extra(group: PinGroup | None) -> int:
        if group is None:
            return 0
        return (
            DRAIN_GROUP_GAP
            if any(id(ri.class_pin) in drained_pin_ids or id(ri.pin) in drained_pin_ids for ri in group.rows)
            else 0
        )

    y = MARGIN
    inner_x = MARGIN
    inner_w = CANVAS_W - MARGIN * 2  # 496

    for comp in harness.components:
        section_start_y = y
        y += COMPONENT_HEADER_H

        # ── direct pins (no connector header) ──────────────────────────────
        comp_cls = type(comp)
        direct_pin_attrs = _sort_pin_attrs(
            [attr for attr, val in vars(comp_cls).items() if isinstance(val, Pin)],
            get_class_pin=lambda a: vars(comp_cls).get(a),
            get_inst_pin=comp._direct_pins.get,
        )
        prev_key: tuple | None = None
        current_group: PinGroup | None = None

        for attr_name in direct_pin_attrs:
            inst_pin = comp._direct_pins.get(attr_name)
            if inst_pin is None:
                continue
            class_pin = vars(comp_cls).get(attr_name, inst_pin)
            if not show_unconnected and not _pin_is_connected(class_pin, inst_pin):
                continue
            key = _pin_target_key(class_pin, inst_pin)

            if prev_key is None:
                current_group = PinGroup(rows=[], target_key=key, first_in_section=True)
                pin_groups.append(current_group)
                if key[0] == "component":
                    y += FIRST_GROUP_PAD
            elif key != prev_key:
                y += GROUP_GAP + _group_drain_extra(current_group)
                current_group = PinGroup(rows=[], target_key=key)
                pin_groups.append(current_group)
            prev_key = key

            row_h = _pin_display_rows(class_pin, inst_pin) * PIN_ROW_H
            row_rect = Rect(inner_x, y, inner_w, row_h)
            row_info = PinRowInfo(
                pin=inst_pin,
                class_pin=class_pin,
                rect=row_rect,
                wire_start_x=inner_x + PIN_NUM_W + PIN_NAME_W,
                wire_end_x=inner_x + inner_w,
            )
            pin_rows[id(inst_pin)] = row_info
            current_group.rows.append(row_info)
            y += row_h

        # ── connectors ─────────────────────────────────────────────────────
        last_conn_drain_extra = 0
        for conn_name, conn in comp._connectors.items():
            conn_cls = type(conn)
            conn_start_y = y
            y += CONNECTOR_HEADER_H

            prev_key = None
            current_group = None

            pin_attrs = _sort_pin_attrs(
                [attr for attr, val in vars(conn_cls).items() if isinstance(val, Pin)],
                get_class_pin=lambda a: vars(conn_cls).get(a),
                get_inst_pin=lambda a: getattr(conn, a, None) if isinstance(getattr(conn, a, None), Pin) else None,
            )
            for attr_name in pin_attrs:
                inst_pin = getattr(conn, attr_name, None)
                if inst_pin is None or not isinstance(inst_pin, Pin):
                    continue
                class_pin = vars(conn_cls).get(attr_name, inst_pin)
                if not show_unconnected and not _pin_is_connected(class_pin, inst_pin):
                    continue
                key = _pin_target_key(class_pin, inst_pin)

                if prev_key is None:
                    current_group = PinGroup(rows=[], target_key=key, first_in_section=True)
                    pin_groups.append(current_group)
                    if key[0] == "component":
                        y += FIRST_GROUP_PAD
                elif key != prev_key:
                    y += GROUP_GAP + _group_drain_extra(current_group)
                    current_group = PinGroup(rows=[], target_key=key)
                    pin_groups.append(current_group)
                prev_key = key

                row_h = _pin_display_rows(class_pin, inst_pin) * PIN_ROW_H
                row_rect = Rect(inner_x, y, inner_w, row_h)
                row_info = PinRowInfo(
                    pin=inst_pin,
                    class_pin=class_pin,
                    rect=row_rect,
                    wire_start_x=inner_x + PIN_NUM_W + PIN_NAME_W,
                    wire_end_x=inner_x + inner_w,
                )
                pin_rows[id(inst_pin)] = row_info
                current_group.rows.append(row_info)
                y += row_h

            conn_drain_extra = (
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
        pin_groups=pin_groups,
        canvas_width=CANVAS_W,
        canvas_height=canvas_height,
    )
