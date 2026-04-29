from __future__ import annotations

from pathlib import Path

import svgwrite

from ..harness import Harness
from ..layout.engine import MARGIN, LayoutResult, PinRowInfo
from ..model import Component, Pin, ShieldGroup, SpliceNode, Terminal
from .colors import _SHIELD_PALETTE, _wire_attrs
from .primitives import (
    _CAN_TERM_BOX_CX,
    _CAN_TERM_SHIELD_SHIFT,
    _JUMPER_STUB_X,
    _MONO_CHAR_W,
    _TERM_SYMBOL_W,
    _draw_can_term_box,
    _draw_connector_header,
    _draw_section_bg,
    _draw_shield_ovals,
    _remote_label,
)
from .wires import _draw_bullet_and_drop, _draw_pin_row, _draw_remote_box


def _compute_min_term_cx(layout: LayoutResult, harness: Harness) -> float:
    """Return the smallest terminal-symbol cx across all terminal connections.

    Scans both direct pin→terminal connections and pin→splice→terminal paths
    so all symbols align to the same column regardless of how they're reached.
    """
    min_cx = float("inf")

    def _check(label_text: str, wire_end_x: float) -> None:
        nonlocal min_cx
        cx = wire_end_x - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W
        min_cx = min(min_cx, cx)

    for group in layout.pin_groups:
        if group.target_key[0] != "terminal":
            continue
        for row in group.rows:
            use_pin = row.pin if row.pin._connections else row.class_pin
            if not use_pin._connections:
                continue
            seg = use_pin._connections[0]
            remote = (
                seg.end_b if (seg.end_a is use_pin or seg.end_a is row.pin or seg.end_a is row.class_pin) else seg.end_a
            )
            if not isinstance(remote, Terminal):
                continue
            _check(_remote_label(remote, row.class_pin, harness), row.wire_end_x)

    if layout.pin_rows:
        wire_end_x = next(iter(layout.pin_rows.values())).wire_end_x
        for splice in harness.splice_nodes:
            for seg in splice._connections:
                remote = seg.end_b if seg.end_a is splice else seg.end_a
                if isinstance(remote, Terminal):
                    _check(remote.display_name(), wire_end_x)

    return min_cx if min_cx != float("inf") else 0


def _drain_label(endpoint) -> str:
    if isinstance(endpoint, Terminal):
        return endpoint.display_name()
    if isinstance(endpoint, Pin):
        return endpoint.signal_name or str(endpoint.number)
    return ""


def _split_contiguous(rows: list[PinRowInfo]) -> list[list[PinRowInfo]]:
    """Partition rows into vertically-contiguous runs.

    The layout engine inserts GROUP_GAP (14px) between pin groups that target
    different remotes; within a group, adjacent rows abut at 0px. Splitting on
    any gap > 1px keeps same-group rows together and breaks on group boundaries
    so a shield spanning multiple groups draws one oval per run instead of a
    single oval that swallows the rows in between.
    """
    ordered = sorted(rows, key=lambda r: r.rect.y)
    runs: list[list[PinRowInfo]] = []
    for r in ordered:
        if not runs:
            runs.append([r])
            continue
        last = runs[-1][-1]
        gap = r.rect.y - (last.rect.y + last.rect.h)
        # Same shield group → keep in one run regardless of small layout gaps
        # (header room between shield-mates targeting different components).
        same_shield = (
            r.segment is not None
            and last.segment is not None
            and r.segment.shield_group is not None
            and r.segment.shield_group is last.segment.shield_group
        )
        if gap <= 1.0 or (same_shield and gap <= 30.0):
            runs[-1].append(r)
        else:
            runs.append([r])
    return runs


def _drain_run_index(runs: list[list[PinRowInfo]], drain_endpoint) -> int:
    """Return the index of the run that should carry the drain triangle.

    If the drain is a Pin, place the triangle on the run containing that pin.
    Otherwise (Terminal / GroundSymbol / None), place it on the last run so the
    triangle hangs below the bottom of the shield bundle.
    """
    if isinstance(drain_endpoint, Pin):
        for i, run in enumerate(runs):
            for ri in run:
                if ri.pin is drain_endpoint or ri.class_pin is drain_endpoint:
                    return i
    return len(runs) - 1 if runs else 0


def render(
    harness: Harness,
    layout: LayoutResult,
    output_path: str | Path,
    colored: bool = True,
    component: Component | None = None,
) -> None:
    """Render the harness schematic to an SVG file.

    When *component* is provided only that component's section is drawn and the
    SVG canvas is sized to fit it — useful for per-component output.
    """
    # Build shield palette lookup: pin id → (stroke, dasharray or None)
    # Step 1a: assign canonical W→WB→WO entries from each shield group's pin order
    # (class-body shields defined via ShieldGroup.pins).
    pin_shield_palette: dict[int, tuple[str, str | None]] = {}
    for sg in harness.shield_groups:
        if sg.cable_only:
            continue
        for idx, p in enumerate(sg.pins):
            pin_shield_palette[id(p)] = _SHIELD_PALETTE[min(idx, len(_SHIELD_PALETTE) - 1)]

    # Step 1b: connection-level shields (``with Shield(...)``) derive color
    # directly from seg.shield_group in _wire_attrs — no pin_shield_palette
    # entries needed.  However, we still propagate remote-pin entries so
    # class-body pins that cross-connect to Shield()-shielded remotes pick
    # up a palette color.

    # Step 2: propagate source palette to remote pins so cross-connected wires
    # (e.g. RS-232 TX↔RX) show the same color at both ends.  The pin that
    # initiated connect() is end_a; its palette entry wins.
    for sg in harness.shield_groups:
        for p in sg.pins:
            src = pin_shield_palette.get(id(p))
            if src is None:
                continue
            for seg in p._connections:
                remote = seg.end_b if seg.end_a is p else seg.end_a
                if isinstance(remote, Pin) and id(remote) not in pin_shield_palette:
                    pin_shield_palette[id(remote)] = src

    # Step 3: propagate palette entries from class pins to their instance-pin
    # copies.  Connections are made on instance pins (which are copy.copy'd
    # from the class pin), so wire segment endpoints carry instance-pin ids.
    # Without this step non-CAN shielded wires fail the palette lookup.
    for ri in layout.all_rows:
        class_entry = pin_shield_palette.get(id(ri.class_pin))
        if class_entry is not None and id(ri.pin) not in pin_shield_palette:
            pin_shield_palette[id(ri.pin)] = class_entry

    # Build pin→row lookups (primary row only — for legacy lookup paths).
    class_pin_to_row: dict[int, object] = {}
    inst_pin_to_row: dict[int, object] = {}
    class_pin_to_rows: dict[int, list] = {}
    inst_pin_to_rows: dict[int, list] = {}
    segment_to_rows: dict[int, list] = {}
    for ri in layout.all_rows:
        # Primary row "wins" for the by-pin lookups (continuations don't
        # overwrite). class_pin_to_rows / inst_pin_to_rows list every row.
        if not ri.is_continuation:
            class_pin_to_row.setdefault(id(ri.class_pin), ri)
            inst_pin_to_row.setdefault(id(ri.pin), ri)
        class_pin_to_rows.setdefault(id(ri.class_pin), []).append(ri)
        inst_pin_to_rows.setdefault(id(ri.pin), []).append(ri)
        if ri.segment is not None:
            segment_to_rows.setdefault(id(ri.segment), []).append(ri)

    def _find_row(pin: Pin):
        return class_pin_to_row.get(id(pin)) or inst_pin_to_row.get(id(pin))

    # Per-row shield lookup: each row knows its own shield based on its segment.
    # Falls back to class-body shield membership for rows whose segment is None
    # (single-connection or splice-fan rows still use the existing pin-keyed flow).
    shield_by_row_id: dict[int, ShieldGroup] = {}
    for ri in layout.all_rows:
        seg = ri.segment
        if seg is not None and seg.shield_group is not None and not seg.shield_group.cable_only:
            shield_by_row_id[id(ri)] = seg.shield_group

    # Legacy pin-keyed shield lookup for splice-fan / single-connection rows.
    shield_by_pin: dict[int, ShieldGroup] = {}
    for sg in harness.shield_groups:
        if sg.cable_only:
            continue
        for p in sg.pins:
            shield_by_pin[id(p)] = sg
            for seg in p._connections:
                remote = seg.end_b if seg.end_a is p else seg.end_a
                if isinstance(remote, Pin):
                    shield_by_pin[id(remote)] = sg
                    row = inst_pin_to_row.get(id(remote))
                    if row:
                        shield_by_pin[id(row.class_pin)] = sg
        for seg in sg.segments:
            for ep in (seg.end_a, seg.end_b):
                if isinstance(ep, Pin):
                    shield_by_pin[id(ep)] = sg
                    row = inst_pin_to_row.get(id(ep))
                    if row:
                        shield_by_pin[id(row.class_pin)] = sg
                elif isinstance(ep, SpliceNode):
                    # A shielded segment that terminates at a splice visually extends
                    # through the splice to the upstream pin row — mark that pin so
                    # the row's wire renders with shield ovals.
                    for other_seg in ep._connections:
                        if other_seg is seg:
                            continue
                        other_ep = other_seg.end_b if other_seg.end_a is ep else other_seg.end_a
                        if isinstance(other_ep, Pin):
                            shield_by_pin[id(other_ep)] = sg
                            row = inst_pin_to_row.get(id(other_ep))
                            if row:
                                shield_by_pin[id(row.class_pin)] = sg

    min_term_cx = _compute_min_term_cx(layout, harness)

    if component is not None:
        sect_rect = layout.section_rects[id(component)]
        vb_y = sect_rect.y - MARGIN
        vb_h = sect_rect.h + 2 * MARGIN
        dwg = svgwrite.Drawing(
            str(output_path),
            size=(layout.canvas_width, vb_h),
            profile="full",
            viewBox=f"0 {vb_y} {layout.canvas_width} {vb_h}",
        )
        components_to_render = [component]
    else:
        dwg = svgwrite.Drawing(str(output_path), size=(layout.canvas_width, layout.canvas_height), profile="full")
        components_to_render = [c for c in harness.components if c.render]

    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))

    jumper_stubs: dict[int, list] = {}  # id(seg) -> [seg, wire_x, [cy, ...]]

    for comp in components_to_render:
        sect_rect = layout.section_rects[id(comp)]
        _draw_section_bg(dwg, sect_rect, comp.label)

        def _resolve_shield(ri):
            return shield_by_row_id.get(id(ri)) or shield_by_pin.get(id(ri.class_pin))

        def _draw_row_and_continuations(primary):
            sh = _resolve_shield(primary)
            _draw_pin_row(dwg, primary, harness, sh, min_term_cx, colored, pin_shield_palette, jumper_stubs)
            for cont in primary.continuation_rows:
                csh = _resolve_shield(cont)
                _draw_pin_row(dwg, cont, harness, csh, min_term_cx, colored, pin_shield_palette, jumper_stubs)
            # Bullet + vertical drop on top of all row backgrounds and leg wires.
            _draw_bullet_and_drop(dwg, primary, colored=colored, pin_shield_palette=pin_shield_palette)

        for attr_name, inst_pin in comp._direct_pins.items():
            row_info = layout.pin_rows.get(id(inst_pin))
            if row_info is None:
                continue
            _draw_row_and_continuations(row_info)

        for conn_name, conn in comp._connectors.items():
            conn_rect = layout.connector_rects.get(id(conn))
            if conn_rect is None:
                continue
            _draw_connector_header(dwg, conn_rect, conn_name)

            for attr_name, inst_pin in vars(conn).items():
                if not isinstance(inst_pin, Pin):
                    continue
                row_info = layout.pin_rows.get(id(inst_pin))
                if row_info is None:
                    continue
                _draw_row_and_continuations(row_info)

        dwg.add(
            dwg.rect(
                insert=(sect_rect.x, sect_rect.y),
                size=(sect_rect.w, sect_rect.h),
                rx=6,
                ry=6,
                fill="none",
                stroke="#334155",
                stroke_width=2,
            )
        )

    # ── shield ovals ────────────────────────────────────────────────────────
    for sg in harness.shield_groups:
        if sg.cable_only:
            continue
        dl = _drain_label(sg.drain) if sg.drain is not None else ""
        dl_remote = _drain_label(sg.drain_remote) if sg.drain_remote is not None else ""

        if sg.segments:
            # Connection-level shield: collect rows per segment so per-leg
            # shields don't accidentally pull in sibling legs of a multi-
            # connection pin.
            src_rows_by_inst: dict[int, list] = {}
            rem_rows_by_inst: dict[int, list] = {}

            def _add_row(target: dict, ri):
                if ri is None:
                    return
                inst_key = id(ri.pin._component) if ri.pin._component is not None else id(ri.pin)
                bucket = target.setdefault(inst_key, [])
                if ri not in bucket:
                    bucket.append(ri)

            for seg in sg.segments:
                seg_rows = segment_to_rows.get(id(seg), [])
                for ep, target in ((seg.end_a, src_rows_by_inst), (seg.end_b, rem_rows_by_inst)):
                    if isinstance(ep, Pin):
                        # Per-leg layout: pick the row whose pin matches this
                        # endpoint AND whose segment is this seg. Falls back to
                        # the pin's primary row when no per-leg row exists.
                        matched = [ri for ri in seg_rows if ri.pin is ep or ri.class_pin is ep]
                        if matched:
                            for ri in matched:
                                _add_row(target, ri)
                        else:
                            row = _find_row(ep)
                            if row is not None:
                                _add_row(target, row)
                    elif isinstance(ep, SpliceNode):
                        # Splice indirection: pull the splice's upstream pin
                        # row in (the wire visually extends through the splice).
                        for other_seg in ep._connections:
                            if other_seg is seg:
                                continue
                            other_ep = other_seg.end_b if other_seg.end_a is ep else other_seg.end_a
                            if isinstance(other_ep, Pin):
                                # Prefer the row whose segment is the splice's upstream wire.
                                up_rows = [
                                    ri for ri in inst_pin_to_rows.get(id(other_ep), []) if ri.segment is other_seg
                                ]
                                if up_rows:
                                    for ri in up_rows:
                                        _add_row(target, ri)
                                else:
                                    for ri in inst_pin_to_rows.get(id(other_ep), []):
                                        _add_row(target, ri)
            for inst_rows in src_rows_by_inst.values():
                runs = _split_contiguous(inst_rows)
                left_run = _drain_run_index(runs, sg.drain)
                right_run = _drain_run_index(runs, sg.drain_remote)
                for i, run in enumerate(runs):
                    _draw_shield_ovals(
                        dwg,
                        run,
                        sg.label,
                        drain_label=dl if i == left_run else "",
                        drain_remote_label=dl_remote if i == right_run else "",
                    )
            for inst_rows in rem_rows_by_inst.values():
                runs = _split_contiguous(inst_rows)
                # On remote view: LEFT oval is local (near remote pins) so it
                # shows drain_remote; RIGHT oval is far (toward source) so it
                # shows drain.
                left_run = _drain_run_index(runs, sg.drain_remote)
                right_run = _drain_run_index(runs, sg.drain)
                for i, run in enumerate(runs):
                    _draw_shield_ovals(
                        dwg,
                        run,
                        sg.label,
                        drain_label=dl_remote if i == left_run else "",
                        drain_remote_label=dl if i == right_run else "",
                    )
        else:
            # Class-body shield: group rows from sg.pins by component instance.
            #
            # Two filters prevent spurious ovals:
            # 1. Skip a row if all of its instance-pin connections are already
            #    covered by a connection-level (with Shield()) shield group.
            #    This prevents double-drawing when a port pin (e.g. RS-232 TX)
            #    is wired inside an explicit Shield() block.
            # 2. After grouping by instance, only draw if ≥2 distinct class-body
            #    shield members are connected.  A single connected pin indicates
            #    direct property access (e.g. gpio.signal) rather than a full
            #    port connect(), which should not render a shield oval.
            source_by_inst: dict[int, list] = {}
            for p in sg.pins:
                for ri in class_pin_to_rows.get(id(p), []):
                    if not ri.pin._connections and not p._connections:
                        continue
                    # Filter 1: skip if all connections are in a different connection-level shield.
                    if ri.pin._connections and all(
                        seg.shield_group is not None
                        and seg.shield_group is not sg
                        and seg.shield_group.segments  # non-empty → connection-level
                        for seg in ri.pin._connections
                    ):
                        continue
                    inst_key = id(ri.pin._component) if ri.pin._component is not None else id(ri.pin)
                    source_by_inst.setdefault(inst_key, []).append(ri)

            # Collect the inst_keys that actually draw ovals (for remote-oval gating below).
            drawing_inst_keys: set[int] = set()
            for inst_key, inst_rows in source_by_inst.items():
                # Filter 2: require ≥2 shield-member class pins per instance.
                if len({id(ri.class_pin) for ri in inst_rows}) < 2:
                    continue
                drawing_inst_keys.add(inst_key)
                runs = _split_contiguous(inst_rows)
                left_run = _drain_run_index(runs, sg.drain)
                right_run = _drain_run_index(runs, sg.drain_remote)
                term_shift = _CAN_TERM_SHIELD_SHIFT if any(ri.pin._can_terminated for ri in inst_rows) else 0
                for i, run in enumerate(runs):
                    _draw_shield_ovals(
                        dwg,
                        run,
                        sg.label,
                        drain_label=dl if i == left_run else "",
                        drain_remote_label=dl_remote if i == right_run else "",
                        single_oval=sg.single_oval,
                        x_offset=term_shift,
                    )

            # Restrict remote ovals to instance pins whose source oval was drawn.
            included_inst_pins: set[int] = {
                id(ri.pin)
                for inst_key, inst_rows in source_by_inst.items()
                if inst_key in drawing_inst_keys
                for ri in inst_rows
            }

            # Remote ovals only for pins whose remote endpoint has no ShieldGroup of its own.
            # When both sides define shielded pins (e.g. RS-232 helpers on both connectors),
            # each component renders its own ovals; cross-rendering would double-draw and
            # overwrite drain markers.
            remote_rows_by_source: dict[int, list] = {}

            def _add_remote_for_source(src_pin: Pin, source_key: int) -> None:
                for seg in src_pin._connections:
                    remote = seg.end_b if seg.end_a is src_pin else seg.end_a
                    if not isinstance(remote, Pin):
                        continue
                    if remote.shield_group is not None:
                        continue
                    row = _find_row(remote)
                    if row is not None:
                        remote_rows_by_source.setdefault(source_key, []).append(row)

            for p in sg.pins:
                _add_remote_for_source(p, id(sg))
                for ri in class_pin_to_rows.get(id(p), []):
                    if id(ri.pin) not in included_inst_pins:
                        continue
                    source_key = id(ri.pin._component) if ri.pin._component is not None else id(ri.pin)
                    _add_remote_for_source(ri.pin, source_key)

            for rows in remote_rows_by_source.values():
                runs = _split_contiguous(rows)
                # Remote-side rows: LEFT oval is local (drain_remote),
                # RIGHT oval points back toward source (drain).
                left_run = _drain_run_index(runs, sg.drain_remote)
                right_run = _drain_run_index(runs, sg.drain)
                for i, run in enumerate(runs):
                    _draw_shield_ovals(
                        dwg,
                        run,
                        sg.label,
                        drain_label=dl_remote if i == left_run else "",
                        drain_remote_label=dl if i == right_run else "",
                        single_oval=sg.single_oval,
                    )

    # ── jumper vertical bars ─────────────────────────────────────────────────
    for entry in jumper_stubs.values():
        seg, wx, cys = entry
        if len(cys) == 2:
            attrs = _wire_attrs(seg, pin_shield_palette, colored)
            bar_x = wx + _JUMPER_STUB_X
            dwg.add(dwg.line(start=(bar_x, min(cys)), end=(bar_x, max(cys)), **attrs))

    # ── remote component boxes ───────────────────────────────────────────────
    for group in layout.pin_groups:
        if group.target_key[0] == "component":
            _draw_remote_box(dwg, group, harness, layout.remote_box_w)

    # ── CAN TERM boxes ───────────────────────────────────────────────────────
    for comp in components_to_render:
        for conn in comp._connectors.values():
            term_rows = []
            for inst_pin in vars(conn).values():
                if isinstance(inst_pin, Pin) and inst_pin._can_terminated:
                    row = inst_pin_to_row.get(id(inst_pin))
                    if row is not None:
                        term_rows.append(row)
            if len(term_rows) >= 2:
                wx = term_rows[0].wire_start_x
                y_top = min(r.rect.y for r in term_rows)
                y_bot = max(r.rect.y + r.rect.h for r in term_rows)
                _draw_can_term_box(dwg, wx + _CAN_TERM_BOX_CX, y_top, y_bot)

    dwg.save()
