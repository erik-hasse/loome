from __future__ import annotations

from pathlib import Path

import svgwrite

from ..harness import Harness
from ..layout.engine import WIRE_AREA_W, LayoutResult
from ..model import Pin, ShieldGroup, Terminal
from .colors import _SHIELD_PALETTE, _wire_attrs
from .primitives import (
    _JUMPER_STUB_X,
    _MONO_CHAR_W,
    _TERM_SYMBOL_W,
    _draw_connector_header,
    _draw_section_bg,
    _draw_shield_ovals,
    _remote_label,
)
from .wires import _draw_pin_row, _draw_remote_box


def _compute_min_term_cx(layout: LayoutResult, harness: Harness) -> float:
    """Return the smallest terminal-symbol cx across all terminal connections.

    Scans both direct pin→terminal connections and pin→splice→terminal paths
    so all symbols align to the same column regardless of how they're reached.
    """
    min_cx = float("inf")

    def _check(label_text: str, wire_start_x: float) -> None:
        nonlocal min_cx
        cx = wire_start_x + WIRE_AREA_W - 4 - len(label_text) * _MONO_CHAR_W - _TERM_SYMBOL_W
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
            _check(_remote_label(remote, row.class_pin, harness), row.wire_start_x)

    if layout.pin_rows:
        wire_start_x = next(iter(layout.pin_rows.values())).wire_start_x
        for splice in harness.splice_nodes:
            for seg in splice._connections:
                remote = seg.end_b if seg.end_a is splice else seg.end_a
                if isinstance(remote, Terminal):
                    _check(remote.display_name(), wire_start_x)

    return min_cx if min_cx != float("inf") else 0


def _drain_label(endpoint) -> str:
    if isinstance(endpoint, Terminal):
        return endpoint.display_name()
    if isinstance(endpoint, Pin):
        return endpoint.signal_name or str(endpoint.number)
    return ""


def render(harness: Harness, layout: LayoutResult, output_path: str | Path, colored: bool = True) -> None:
    # Build shield palette lookup: class pin id → (stroke, dasharray or None)
    # Step 1: assign canonical W→WB→WO entries from each shield group's pin order.
    pin_shield_palette: dict[int, tuple[str, str | None]] = {}
    for sg in harness.shield_groups:
        for idx, p in enumerate(sg.pins):
            pin_shield_palette[id(p)] = _SHIELD_PALETTE[min(idx, len(_SHIELD_PALETTE) - 1)]

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
                if isinstance(remote, Pin) and id(remote) in pin_shield_palette:
                    pin_shield_palette[id(remote)] = src

    # Build pin→row lookups
    class_pin_to_row: dict[int, object] = {}
    inst_pin_to_row: dict[int, object] = {}
    class_pin_to_rows: dict[int, list] = {}
    for ri in layout.pin_rows.values():
        class_pin_to_row[id(ri.class_pin)] = ri
        inst_pin_to_row[id(ri.pin)] = ri
        class_pin_to_rows.setdefault(id(ri.class_pin), []).append(ri)

    def _find_row(pin: Pin):
        return class_pin_to_row.get(id(pin)) or inst_pin_to_row.get(id(pin))

    # Build shield lookup: pin id → ShieldGroup (source + remote pins)
    shield_by_pin: dict[int, ShieldGroup] = {}
    for sg in harness.shield_groups:
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

    min_term_cx = _compute_min_term_cx(layout, harness)

    dwg = svgwrite.Drawing(str(output_path), size=(layout.canvas_width, layout.canvas_height), profile="full")
    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))

    jumper_stubs: dict[int, list] = {}  # id(seg) -> [seg, wire_x, [cy, ...]]

    for comp in harness.components:
        sect_rect = layout.section_rects[id(comp)]
        _draw_section_bg(dwg, sect_rect, comp.label)

        for attr_name, inst_pin in comp._direct_pins.items():
            row_info = layout.pin_rows.get(id(inst_pin))
            if row_info is None:
                continue
            shield = shield_by_pin.get(id(row_info.class_pin))
            _draw_pin_row(dwg, row_info, harness, shield, min_term_cx, colored, pin_shield_palette, jumper_stubs)

        for conn_name, conn in comp._connectors.items():
            conn_rect = layout.connector_rects[id(conn)]
            _draw_connector_header(dwg, conn_rect, conn_name)

            for attr_name, inst_pin in vars(conn).items():
                if not isinstance(inst_pin, Pin):
                    continue
                row_info = layout.pin_rows.get(id(inst_pin))
                if row_info is None:
                    continue
                shield = shield_by_pin.get(id(row_info.class_pin))
                _draw_pin_row(dwg, row_info, harness, shield, min_term_cx, colored, pin_shield_palette, jumper_stubs)

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
        dl = _drain_label(sg.drain) if sg.drain is not None else ""
        dl_remote = _drain_label(sg.drain_remote) if sg.drain_remote is not None else ""

        if sg.segments:
            # Connection-level shield: expand to all instance rows via class_pin_to_rows,
            # then group by component instance (same approach as class-body shields).
            src_rows_by_inst: dict[int, list] = {}
            rem_rows_by_inst: dict[int, list] = {}
            for seg in sg.segments:
                for ep, target in ((seg.end_a, src_rows_by_inst), (seg.end_b, rem_rows_by_inst)):
                    if not isinstance(ep, Pin):
                        continue
                    row = _find_row(ep)
                    if row is None:
                        continue
                    cp_id = id(row.class_pin)
                    for ri in class_pin_to_rows.get(cp_id, [row]):
                        inst_key = id(ri.pin._component) if ri.pin._component is not None else id(ri.pin)
                        if ri not in target.setdefault(inst_key, []):
                            target[inst_key].append(ri)
            for inst_rows in src_rows_by_inst.values():
                _draw_shield_ovals(dwg, inst_rows, sg.label, drain_label=dl)
            for inst_rows in rem_rows_by_inst.values():
                _draw_shield_ovals(dwg, inst_rows, sg.label, drain_remote_label=dl_remote)
        else:
            # Class-body shield: group rows from sg.pins by component instance.
            source_by_inst: dict[int, list] = {}
            for p in sg.pins:
                for ri in class_pin_to_rows.get(id(p), []):
                    if not ri.pin._connections and not p._connections:
                        continue
                    inst_key = id(ri.pin._component) if ri.pin._component is not None else id(ri.pin)
                    source_by_inst.setdefault(inst_key, []).append(ri)
            for inst_rows in source_by_inst.values():
                _draw_shield_ovals(
                    dwg,
                    inst_rows,
                    sg.label,
                    drain_label=dl,
                    drain_remote_label=dl_remote,
                    single_oval=sg.single_oval,
                )

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
                    source_key = id(ri.pin._component) if ri.pin._component is not None else id(ri.pin)
                    _add_remote_for_source(ri.pin, source_key)

            for rows in remote_rows_by_source.values():
                _draw_shield_ovals(dwg, rows, sg.label, drain_remote_label=dl_remote, single_oval=sg.single_oval)

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
            _draw_remote_box(dwg, group, harness)

    dwg.save()
