from __future__ import annotations

from dataclasses import dataclass

from ..model import CircuitBreaker, Fuse, GroundSymbol, Harness, OffPageReference, Pin
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


def _pin_target_key(class_pin: Pin, inst_pin: Pin | None = None) -> tuple:
    """Return a stable grouping key based on where this pin's first connection leads.

    Prefers instance-pin connections (wired at instance level) over class-pin connections.
    """
    use = inst_pin if (inst_pin is not None and inst_pin._connections) else class_pin
    if not use._connections:
        return ("unconnected",)
    seg = use._connections[0]
    remote = seg.end_b if seg.end_a is use else seg.end_a
    if isinstance(remote, Pin):
        return ("component", id(remote._component_class), id(remote._connector_class))
    elif isinstance(remote, (GroundSymbol, OffPageReference, Fuse, CircuitBreaker)):
        return ("terminal", id(remote))
    return ("other", id(remote))


def layout(harness: Harness) -> LayoutResult:
    section_rects: dict[int, Rect] = {}
    connector_rects: dict[int, Rect] = {}
    pin_rows: dict[int, PinRowInfo] = {}
    pin_groups: list[PinGroup] = []

    y = MARGIN
    inner_x = MARGIN
    inner_w = CANVAS_W - MARGIN * 2  # 496

    for comp in harness.components:
        section_start_y = y
        y += COMPONENT_HEADER_H

        # ── direct pins (no connector header) ──────────────────────────────
        comp_cls = type(comp)
        direct_pin_attrs = [attr for attr, val in vars(comp_cls).items() if isinstance(val, Pin)]
        prev_key: tuple | None = None
        current_group: PinGroup | None = None

        for attr_name in direct_pin_attrs:
            inst_pin = comp._direct_pins.get(attr_name)
            if inst_pin is None:
                continue
            class_pin = vars(comp_cls).get(attr_name, inst_pin)
            key = _pin_target_key(class_pin, inst_pin)

            if prev_key is None:
                current_group = PinGroup(rows=[], target_key=key, first_in_section=True)
                pin_groups.append(current_group)
                if key[0] == "component":
                    y += FIRST_GROUP_PAD
            elif key != prev_key:
                y += GROUP_GAP
                current_group = PinGroup(rows=[], target_key=key)
                pin_groups.append(current_group)
            prev_key = key

            row_rect = Rect(inner_x, y, inner_w, PIN_ROW_H)
            row_info = PinRowInfo(
                pin=inst_pin,
                class_pin=class_pin,
                rect=row_rect,
                wire_start_x=inner_x + PIN_NUM_W + PIN_NAME_W,
                wire_end_x=inner_x + inner_w,
            )
            pin_rows[id(inst_pin)] = row_info
            current_group.rows.append(row_info)
            y += PIN_ROW_H

        # ── connectors ─────────────────────────────────────────────────────
        for conn_name, conn in comp._connectors.items():
            conn_cls = type(conn)
            conn_start_y = y
            y += CONNECTOR_HEADER_H

            prev_key = None
            current_group = None

            pin_attrs = [attr for attr, val in vars(conn_cls).items() if isinstance(val, Pin)]
            for attr_name in pin_attrs:
                inst_pin = getattr(conn, attr_name, None)
                if inst_pin is None or not isinstance(inst_pin, Pin):
                    continue
                class_pin = vars(conn_cls).get(attr_name, inst_pin)
                key = _pin_target_key(class_pin, inst_pin)

                if prev_key is None:
                    current_group = PinGroup(rows=[], target_key=key, first_in_section=True)
                    pin_groups.append(current_group)
                    if key[0] == "component":
                        y += FIRST_GROUP_PAD
                elif key != prev_key:
                    y += GROUP_GAP
                    current_group = PinGroup(rows=[], target_key=key)
                    pin_groups.append(current_group)
                prev_key = key

                row_rect = Rect(inner_x, y, inner_w, PIN_ROW_H)
                row_info = PinRowInfo(
                    pin=inst_pin,
                    class_pin=class_pin,
                    rect=row_rect,
                    wire_start_x=inner_x + PIN_NUM_W + PIN_NAME_W,
                    wire_end_x=inner_x + inner_w,
                )
                pin_rows[id(inst_pin)] = row_info
                current_group.rows.append(row_info)
                y += PIN_ROW_H

            y += CONNECTOR_BOTTOM_PAD
            conn_rect = Rect(inner_x, conn_start_y, inner_w, y - conn_start_y)
            connector_rects[id(conn)] = conn_rect

        section_rect = Rect(inner_x, section_start_y, inner_w, y - section_start_y + SECTION_BOTTOM_PAD)
        section_rects[id(comp)] = section_rect
        y += SECTION_BOTTOM_PAD + SECTION_GAP

    canvas_height = y + MARGIN

    return LayoutResult(
        section_rects=section_rects,
        connector_rects=connector_rects,
        pin_rows=pin_rows,
        pin_groups=pin_groups,
        canvas_width=CANVAS_W,
        canvas_height=canvas_height,
    )
