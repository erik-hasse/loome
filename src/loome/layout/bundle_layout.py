"""Abstract tree layout for a `Bundle`.

Topology-first, not to scale. Trunk runs horizontally through the deepest
chain from the root; everything else is a branch offset perpendicular to its
parent's trunk position. Attachment boxes stack below each breakout with a
pin schedule showing resolved wire lengths.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .._internal.attachments import describe_attachment_target
from .._internal.endpoints import other_endpoint
from ..bundles import Attachment, Breakout, Bundle
from ..harness import Harness
from ..model import Component, Connector, Pin, SpliceNode, Terminal
from .geometry import Rect

MARGIN = 24
MIN_TRUNK_SPACING_X = 220  # minimum horizontal distance between adjacent trunk breakouts
MIN_BRANCH_OFFSET_Y = 80  # minimum vertical distance between a breakout and a clear neighbor
COL_PAD = 40  # extra horizontal padding between adjacent columns of attachment boxes
BREAKOUT_DOT_R = 5
ATTACHMENT_BOX_W = 180
ATTACHMENT_HEADER_H = 20
ATTACHMENT_PIN_ROW_H = 16
ATTACHMENT_BOX_GAP = 12  # vertical gap between stacked attachment boxes
LEG_SEGMENT_LEN = 40  # visual length of the leg from trunk to attachment box


@dataclass
class PinScheduleRow:
    pin: Pin
    wire_label: str
    length: float | None


@dataclass
class AttachmentBox:
    attachment: Attachment
    rect: Rect
    header: str
    rows: list[PinScheduleRow]
    leg_x1: float
    leg_y1: float
    leg_x2: float
    leg_y2: float


@dataclass
class BreakoutNode:
    breakout: Breakout
    x: float
    y: float
    on_trunk: bool
    parent_edge_label: str = ""  # e.g. "24 in"


@dataclass
class BundleLayout:
    bundle: Bundle
    canvas_width: float
    canvas_height: float
    trunk_y: float
    nodes: dict[int, BreakoutNode]
    attachment_boxes: list[AttachmentBox] = field(default_factory=list)
    edges: list[tuple[BreakoutNode, BreakoutNode, str]] = field(default_factory=list)


def _children_of(bundle: Bundle, node: Breakout) -> list[Breakout]:
    return [bk for bk in bundle.breakouts if bk.parent is node]


def _trunk_path(bundle: Bundle) -> list[Breakout]:
    """Pick the chain from root with the largest cumulative trunk length."""
    if bundle.root is None:
        return []

    def _longest(node: Breakout) -> tuple[float, list[Breakout]]:
        kids = _children_of(bundle, node)
        if not kids:
            return 0.0, [node]
        best_len = -1.0
        best_chain: list[Breakout] = [node]
        for kid in kids:
            sub_len, sub_chain = _longest(kid)
            total = kid.length_from_parent + sub_len
            if total > best_len:
                best_len = total
                best_chain = [node, *sub_chain]
        return best_len, best_chain

    _, chain = _longest(bundle.root)
    return chain


def _describe_attachment_target(attachment: Attachment) -> str:
    return describe_attachment_target(attachment.target)


def _pin_schedule_rows(
    attachment: Attachment,
    harness: Harness,
) -> list[PinScheduleRow]:
    """List only wires that actually traverse this attachment out into the bundle.

    Filters out wires whose length cannot be resolved (one end unattached, or on
    a different bundle) and self-loops where the other endpoint lands on the
    same attachment (straps / jumpers within a single connector).
    """
    target = attachment.target
    pins: list[Pin] = []
    if isinstance(target, Connector):
        for name, val in vars(type(target)).items():
            if isinstance(val, Pin):
                inst_pin = getattr(target, name, val)
                pins.append(inst_pin if isinstance(inst_pin, Pin) else val)
    elif isinstance(target, Component):
        pins.extend(target._direct_pins.values())

    rows: list[PinScheduleRow] = []
    seen_segs: set[int] = set()
    for pin in pins:
        segs: list = list(pin._connections)
        if not segs:
            cls_pin = None
            if pin._connector_class is not None:
                cls_pin = vars(pin._connector_class).get(_pin_attr_name(pin))
            elif pin._component_class is not None:
                cls_pin = vars(pin._component_class).get(_pin_attr_name(pin))
            if isinstance(cls_pin, Pin):
                segs = list(cls_pin._connections)

        for seg in segs:
            if id(seg) in seen_segs:
                continue
            seen_segs.add(id(seg))
            length = harness.resolved_length(seg)
            if length is None:
                continue
            other = other_endpoint(seg, pin, _class_pin_of(pin))
            if _is_local_wire(harness, attachment, other):
                continue
            rows.append(PinScheduleRow(pin=pin, wire_label=seg.label or "", length=length))

    if isinstance(target, (Terminal, SpliceNode)):
        for seg in getattr(target, "_connections", []):
            if id(seg) in seen_segs:
                continue
            seen_segs.add(id(seg))
            length = harness.resolved_length(seg)
            if length is None:
                continue
            other = other_endpoint(seg, target)
            if _is_local_wire(harness, attachment, other):
                continue
            rows.append(PinScheduleRow(pin=None, wire_label=seg.label or "", length=length))

    return rows


def _class_pin_of(pin: Pin) -> Pin | None:
    owner_cls = pin._connector_class or pin._component_class
    if owner_cls is None:
        return None
    for val in vars(owner_cls).values():
        if isinstance(val, Pin) and val.number == pin.number and val.signal_name == pin.signal_name:
            return val
    return None


def _attachment_for_endpoint(harness: Harness, endpoint) -> Attachment | None:
    for bundle in harness.bundles:
        att = bundle.attachment_for(endpoint)
        if att is not None:
            return att
    return None


def _is_local_wire(harness: Harness, attachment: Attachment, remote_endpoint) -> bool:
    """True when the other endpoint shares a breakout with this attachment.

    Covers both jumpers/straps within a single connector (same attachment) and
    local routing between distinct attachments clustered at one breakout — in
    both cases the wire doesn't traverse the trunk and doesn't belong in the
    bundle schedule.
    """
    other_att = _attachment_for_endpoint(harness, remote_endpoint)
    if other_att is None:
        return False
    return other_att.breakout is attachment.breakout


def _pin_attr_name(pin: Pin) -> str:
    owner_cls = pin._connector_class or pin._component_class
    if owner_cls is None:
        return ""
    for name, val in vars(owner_cls).items():
        if val is pin:
            return name
    return ""


def _format_length(length: float | None, unit: str) -> str:
    # Kept for callers that still pass raw unit strings; prefer Harness.format_length.
    if length is None:
        return "—"
    if float(length).is_integer():
        return f"{int(length)} {unit}"
    return f"{length:g} {unit}"


def _bk_stack_height(bk: Breakout, harness: Harness) -> float:
    """Total pixel height of a breakout's attachment stack (including leg + gaps)."""
    h = LEG_SEGMENT_LEN
    for att in bk.attachments:
        rows = _pin_schedule_rows(att, harness)
        body_h = max(ATTACHMENT_PIN_ROW_H, len(rows) * ATTACHMENT_PIN_ROW_H)
        h += ATTACHMENT_HEADER_H + body_h + 6 + ATTACHMENT_BOX_GAP
    return h


def _subtree_span_y(bundle: Bundle, bk: Breakout, direction: int, harness: Harness) -> float:
    """How far from this breakout the subtree extends in the given (+/-) direction.

    Ignores horizontal spread; only measures vertical reach for branch placement.
    """
    own = _bk_stack_height(bk, harness)
    kids = _children_of(bundle, bk)
    child_reach = 0.0
    for kid in kids:
        child_reach = max(child_reach, MIN_BRANCH_OFFSET_Y + _subtree_span_y(bundle, kid, direction, harness))
    return own + child_reach


def _subtree_width(bundle: Bundle, bk: Breakout, harness: Harness, trunk_ids: set[int]) -> float:
    """Horizontal width occupied by a branch subtree rooted at bk.

    Trunk descendants don't count (they're placed on the trunk line). Leaves
    return ATTACHMENT_BOX_W + padding. Internal branch nodes sum their
    branch-children's widths (trunk-children ignored).
    """
    kids = [k for k in _children_of(bundle, bk) if id(k) not in trunk_ids]
    if not kids:
        return ATTACHMENT_BOX_W + COL_PAD
    total = 0.0
    for kid in kids:
        total += _subtree_width(bundle, kid, harness, trunk_ids)
    return max(total, ATTACHMENT_BOX_W + COL_PAD)


def layout_bundle(bundle: Bundle, harness: Harness) -> BundleLayout:
    if bundle.root is None:
        return BundleLayout(
            bundle=bundle,
            canvas_width=MARGIN * 2,
            canvas_height=MARGIN * 2,
            trunk_y=MARGIN,
            nodes={},
        )

    trunk_chain = _trunk_path(bundle)
    trunk_ids = {id(bk) for bk in trunk_chain}

    # Decide each trunk breakout's attachment direction (above vs below) up-front
    # so branch-stacks and attachment-stacks never compete for the same space.
    trunk_directions: dict[int, int] = {}
    for i, bk in enumerate(trunk_chain):
        kids = _children_of(bundle, bk)
        has_branch_kid = any(id(k) not in trunk_ids for k in kids)
        if has_branch_kid:
            # Branches alternate above/below the trunk based on trunk index;
            # the attachment stack must take the opposite side.
            branch_dir = -1 if i % 2 == 0 else 1
            trunk_directions[id(bk)] = -branch_dir
        else:
            trunk_directions[id(bk)] = 1 if i % 2 == 0 else -1

    # Step 1: decide trunk spacing so each trunk breakout's subtree fits in its
    # column without horizontally overlapping its neighbors.
    col_widths: list[float] = []
    for bk in trunk_chain:
        branch_kids = [k for k in _children_of(bundle, bk) if id(k) not in trunk_ids]
        branch_width = sum(_subtree_width(bundle, k, harness, trunk_ids) for k in branch_kids)
        col_widths.append(max(MIN_TRUNK_SPACING_X, branch_width, ATTACHMENT_BOX_W + COL_PAD))

    # Step 2: decide trunk_y so the deepest above-trunk content clears the top.
    max_above = 0.0
    for bk in trunk_chain:
        if trunk_directions[id(bk)] == -1:
            max_above = max(max_above, _bk_stack_height(bk, harness))
        i = trunk_chain.index(bk)
        branch_dir = -1 if i % 2 == 0 else 1
        for kid in _children_of(bundle, bk):
            if id(kid) in trunk_ids:
                continue
            if branch_dir == -1:
                max_above = max(max_above, MIN_BRANCH_OFFSET_Y + _subtree_span_y(bundle, kid, -1, harness))

    trunk_y = MARGIN + max_above + 16

    # Step 3: place trunk nodes using per-column spacing.
    nodes: dict[int, BreakoutNode] = {}
    x_cursor = MARGIN + col_widths[0] / 2
    for i, bk in enumerate(trunk_chain):
        if i > 0:
            x_cursor += (col_widths[i - 1] + col_widths[i]) / 2
        nodes[id(bk)] = BreakoutNode(
            breakout=bk,
            x=x_cursor,
            y=trunk_y,
            on_trunk=True,
            parent_edge_label=_format_length(bk.length_from_parent, harness.length_unit)
            if bk.parent is not None
            else "",
        )

    # Step 4: recursively place branch nodes perpendicular to parent, with
    # vertical offset sized to clear the parent's attachment stack (if stacked
    # on the same side) and horizontal spread sized to fit each kid's subtree.
    def _place_branch(parent: Breakout, direction: int) -> None:
        kids = [bk for bk in _children_of(bundle, parent) if id(bk) not in trunk_ids]
        if not kids:
            return
        parent_node = nodes[id(parent)]
        parent_stack_same_side = (
            _bk_stack_height(parent, harness) if trunk_directions.get(id(parent)) == direction else 0
        )
        base_offset = max(
            MIN_BRANCH_OFFSET_Y,
            parent_stack_same_side + MIN_BRANCH_OFFSET_Y,
        )
        widths = [_subtree_width(bundle, k, harness, trunk_ids) for k in kids]
        total_w = sum(widths)
        # Distribute children across [-total_w/2, +total_w/2] from parent's x.
        cursor = parent_node.x - total_w / 2
        for kid, w in zip(kids, widths):
            kx = cursor + w / 2
            cursor += w
            ky = parent_node.y + direction * base_offset
            nodes[id(kid)] = BreakoutNode(
                breakout=kid,
                x=kx,
                y=ky,
                on_trunk=False,
                parent_edge_label=_format_length(kid.length_from_parent, harness.length_unit),
            )
            _place_branch(kid, direction)

    for i, bk in enumerate(trunk_chain):
        direction = -1 if i % 2 == 0 else 1
        _place_branch(bk, direction)

    # Step 3: compute edges.
    edges: list[tuple[BreakoutNode, BreakoutNode, str]] = []
    for bk in bundle.breakouts:
        if bk.parent is None:
            continue
        parent_node = nodes.get(id(bk.parent))
        child_node = nodes.get(id(bk))
        if parent_node is None or child_node is None:
            continue
        edges.append((parent_node, child_node, child_node.parent_edge_label))

    # Step 4: build attachment boxes. Only the first box in a stack has a
    # leg reaching the trunk; subsequent boxes chain via a short connector
    # across the gap so the line never crosses through a previous box.
    attachment_boxes: list[AttachmentBox] = []
    for bk in bundle.breakouts:
        node = nodes[id(bk)]
        if node.on_trunk:
            direction = trunk_directions[id(bk)]
        else:
            direction = -1 if node.y < trunk_y else 1
        cursor_y = node.y + direction * LEG_SEGMENT_LEN
        prev_box_y1: float | None = None
        prev_box_y2: float | None = None
        for att in bk.attachments:
            rows = _pin_schedule_rows(att, harness)
            header_h = ATTACHMENT_HEADER_H
            body_h = max(ATTACHMENT_PIN_ROW_H, len(rows) * ATTACHMENT_PIN_ROW_H)
            box_h = header_h + body_h + 6
            box_x = node.x - ATTACHMENT_BOX_W / 2
            if direction == 1:
                box_y = cursor_y
                if prev_box_y2 is None:
                    leg_y1, leg_y2 = node.y, box_y
                else:
                    leg_y1, leg_y2 = prev_box_y2, box_y
                cursor_y = box_y + box_h + ATTACHMENT_BOX_GAP
                prev_box_y1, prev_box_y2 = box_y, box_y + box_h
            else:
                box_y = cursor_y - box_h
                if prev_box_y1 is None:
                    leg_y1, leg_y2 = node.y, box_y + box_h
                else:
                    leg_y1, leg_y2 = box_y + box_h, prev_box_y1
                cursor_y = box_y - ATTACHMENT_BOX_GAP
                prev_box_y1, prev_box_y2 = box_y, box_y + box_h
            rect = Rect(box_x, box_y, ATTACHMENT_BOX_W, box_h)
            header = _describe_attachment_target(att)
            leg_label_length = _format_length(att.leg_length, harness.length_unit)
            attachment_boxes.append(
                AttachmentBox(
                    attachment=att,
                    rect=rect,
                    header=f"{header}  (leg {leg_label_length})",
                    rows=rows,
                    leg_x1=node.x,
                    leg_y1=leg_y1,
                    leg_x2=node.x,
                    leg_y2=leg_y2,
                )
            )

    # Step 5: compute canvas bounds.
    min_x = min((n.x for n in nodes.values()), default=MARGIN)
    max_x = max((n.x for n in nodes.values()), default=MARGIN)
    min_y = min((n.y for n in nodes.values()), default=trunk_y)
    max_y = max((n.y for n in nodes.values()), default=trunk_y)
    for box in attachment_boxes:
        min_x = min(min_x, box.rect.x)
        max_x = max(max_x, box.rect.x2)
        min_y = min(min_y, box.rect.y)
        max_y = max(max_y, box.rect.y2)

    # Pad and translate so the min coordinates are MARGIN.
    dx = MARGIN - min_x
    dy = MARGIN - min_y
    for node in nodes.values():
        node.x += dx
        node.y += dy
    trunk_y += dy
    for box in attachment_boxes:
        box.rect.x += dx
        box.rect.y += dy
        box.leg_x1 += dx
        box.leg_y1 += dy
        box.leg_x2 += dx
        box.leg_y2 += dy

    canvas_w = (max_x - min_x) + MARGIN * 2
    canvas_h = (max_y - min_y) + MARGIN * 2

    return BundleLayout(
        bundle=bundle,
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        trunk_y=trunk_y,
        nodes=nodes,
        attachment_boxes=attachment_boxes,
        edges=edges,
    )
