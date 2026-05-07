from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import drawsvg as draw

from .._internal.endpoints import component_key_for_pin, connector_key_for_pin, other_endpoint
from .._internal.shields import segment_shield_for_endpoint
from ..harness import Harness
from ..layout.engine import MARGIN, LayoutResult, PinRowInfo
from ..model import Component, Pin, ShieldDrainTerminal, ShieldGroup, SpliceNode, Terminal, WireEndpoint
from .colors import _wire_attrs
from .context import build_render_context
from .primitives import (
    _CAN_TERM_BOX_CX,
    _CAN_TERM_SHIELD_SHIFT,
    _MONO_CHAR_W,
    _SHIELD_LEFT_CX,
    _SHIELD_RIGHT_CX,
    _TERM_SYMBOL_W,
    _draw_bullet,
    _draw_can_term_box,
    _draw_connector_header,
    _draw_section_bg,
    _draw_shield_ovals,
    _remote_label,
)
from .wires import _DRAIN_PIN_COLOR, _REMOTE_BOX_X, _draw_bullet_and_drop, _draw_pin_row, _draw_remote_box


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
            remote = other_endpoint(seg, use_pin, row.pin, row.class_pin)
            if not isinstance(remote, Terminal) or isinstance(remote, ShieldDrainTerminal):
                continue
            _check(_remote_label(remote, row.class_pin, harness), row.wire_end_x)

    if layout.pin_rows:
        wire_end_x = next(iter(layout.pin_rows.values())).wire_end_x
        for splice in harness.splice_nodes:
            for seg in splice._connections:
                remote = other_endpoint(seg, splice)
                if isinstance(remote, Terminal):
                    _check(remote.display_name(), wire_end_x)

    return min_cx if min_cx != float("inf") else 0


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


@dataclass
class _ShieldOvalPlan:
    """Rows normalized by shield view before SVG oval drawing.

    ``near`` rows use the shield's natural orientation: ``drain`` at the left
    oval and ``drain_remote`` at the right oval. ``far`` rows mirror that view
    for the other side of a cable.
    """

    near_rows_by_inst: dict[int, list[PinRowInfo]] = field(default_factory=dict)
    far_rows_by_inst: dict[int, list[PinRowInfo]] = field(default_factory=dict)


def _pin_instance_key(pin: Pin) -> int:
    return id(pin._component) if pin._component is not None else id(pin)


def _add_plan_row(rows_by_inst: dict[int, list[PinRowInfo]], row: PinRowInfo | None, key: int | None = None) -> None:
    if row is None:
        return
    bucket = rows_by_inst.setdefault(key if key is not None else _pin_instance_key(row.pin), [])
    if row not in bucket:
        bucket.append(row)


def _rows_for_pin_endpoint(ctx, seg, endpoint: Pin) -> list[PinRowInfo]:
    seg_rows = ctx.rows.rows_for_segment(seg)
    matched = [ri for ri in seg_rows if ri.pin is endpoint or ri.class_pin is endpoint]
    if matched:
        return matched
    row = ctx.rows.row_for_pin(endpoint)
    return [row] if row is not None else []


def _upstream_rows_for_splice(ctx, splice: SpliceNode, shielded_seg) -> list[PinRowInfo]:
    rows: list[PinRowInfo] = []
    for other_seg in splice._connections:
        if other_seg is shielded_seg:
            continue
        other_ep = other_endpoint(other_seg, splice)
        if not isinstance(other_ep, Pin):
            continue
        up_rows = [ri for ri in ctx.rows.rows_for_inst_pin(other_ep) if ri.segment is other_seg]
        rows.extend(up_rows or ctx.rows.rows_for_inst_pin(other_ep))
    return rows


def _collect_segment_owned_shield_rows(sg: ShieldGroup, ctx, plan: _ShieldOvalPlan) -> None:
    """Adapt ``with Shield(...)`` segment ownership into a normalized oval plan."""

    for seg in sg.segments:
        for endpoint, target in ((seg.end_a, plan.near_rows_by_inst), (seg.end_b, plan.far_rows_by_inst)):
            if isinstance(endpoint, Pin):
                for row in _rows_for_pin_endpoint(ctx, seg, endpoint):
                    _add_plan_row(target, row)
            elif isinstance(endpoint, SpliceNode):
                for row in _upstream_rows_for_splice(ctx, endpoint, seg):
                    _add_plan_row(target, row)


def _row_connections(row: PinRowInfo, class_pin: Pin) -> list:
    if row.segment is not None:
        return [row.segment]
    return list(row.pin._connections or class_pin._connections)


def _row_covered_by_other_segment_shield(row: PinRowInfo, class_pin: Pin, sg: ShieldGroup) -> bool:
    connections = _row_connections(row, class_pin)
    return bool(connections) and all(
        seg.shield_group is not None and seg.shield_group is not sg and seg.shield_group.segments for seg in connections
    )


def _row_endpoint_owns_shield(row: PinRowInfo, class_pin: Pin, sg: ShieldGroup) -> bool:
    connections = _row_connections(row, class_pin)
    use_pin = row.pin if row.pin._connections else class_pin
    return any(segment_shield_for_endpoint(seg, use_pin, row.class_pin) is sg for seg in connections)


def _rows_for_shield_pin(pin: Pin, ctx) -> list[PinRowInfo]:
    rows: list[PinRowInfo] = []
    for row in [*ctx.rows.rows_for_class_pin(pin), *ctx.rows.rows_for_inst_pin(pin)]:
        if row not in rows:
            rows.append(row)
    return rows


def _endpoint_owned_source_rows(sg: ShieldGroup, ctx) -> dict[int, list[PinRowInfo]]:
    """Rows where pins carry ``sg`` directly, filtered to real multi-pin cables."""

    rows_by_inst: dict[int, list[PinRowInfo]] = {}
    for pin in sg.pins:
        for row in _rows_for_shield_pin(pin, ctx):
            if not row.pin._connections and not pin._connections:
                continue
            if not _row_endpoint_owns_shield(row, pin, sg):
                continue
            if _row_covered_by_other_segment_shield(row, pin, sg):
                continue
            _add_plan_row(rows_by_inst, row)

    return {inst_key: rows for inst_key, rows in rows_by_inst.items() if len({id(row.class_pin) for row in rows}) >= 2}


def _collect_endpoint_remote_rows(sg: ShieldGroup, ctx, source_rows_by_inst: dict[int, list[PinRowInfo]], plan) -> None:
    included_inst_pins: set[int] = {id(row.pin) for rows in source_rows_by_inst.values() for row in rows}

    def _add_remote_for_source(src_pin: Pin, source_key: int) -> None:
        for seg in src_pin._connections:
            if seg.shield_group is not None and seg.shield_group is not sg:
                continue
            remote = other_endpoint(seg, src_pin)
            if not isinstance(remote, Pin):
                continue
            if remote.shield_group is not None:
                continue
            _add_plan_row(plan.far_rows_by_inst, ctx.rows.row_for_pin(remote), source_key)

    for pin in sg.pins:
        if pin._connections:
            _add_remote_for_source(pin, id(sg))
        for row in _rows_for_shield_pin(pin, ctx):
            if id(row.pin) not in included_inst_pins:
                continue
            _add_remote_for_source(row.pin, _pin_instance_key(row.pin))


def _collect_endpoint_owned_shield_rows(sg: ShieldGroup, ctx, plan: _ShieldOvalPlan) -> None:
    """Adapt port/class-body pin ownership into a normalized oval plan."""

    source_rows_by_inst = _endpoint_owned_source_rows(sg, ctx)
    for inst_key, rows in source_rows_by_inst.items():
        for row in rows:
            _add_plan_row(plan.near_rows_by_inst, row, inst_key)
    _collect_endpoint_remote_rows(sg, ctx, source_rows_by_inst, plan)


def _build_shield_oval_plan(sg: ShieldGroup, ctx) -> _ShieldOvalPlan:
    plan = _ShieldOvalPlan()
    _collect_segment_owned_shield_rows(sg, ctx, plan)
    _collect_endpoint_owned_shield_rows(sg, ctx, plan)
    return plan


def _component_keys_for_plan(plan: _ShieldOvalPlan) -> set[int]:
    return {
        component_key_for_pin(row.pin)
        for rows_by_inst in (plan.near_rows_by_inst, plan.far_rows_by_inst)
        for rows in rows_by_inst.values()
        for row in rows
    }


def _target_key_for_pin(pin: Pin) -> tuple:
    return ("component", component_key_for_pin(pin), connector_key_for_pin(pin))


def _queue_pin_drain_connection(
    ctx,
    rows: list[PinRowInfo],
    run: list[PinRowInfo],
    endpoint: WireEndpoint | None,
    oval_x_offset: float,
    oval_bottom: float,
    pending_drain_src: list[tuple[float, float, float]],
    pending_drain_rem: list[tuple[float, float, tuple, Pin]],
    *,
    remote: bool,
) -> None:
    if not isinstance(endpoint, Pin):
        return
    wx_run = run[0].wire_start_x
    oval_x = wx_run + oval_x_offset
    if remote:
        pending_drain_rem.append((oval_x, oval_bottom, _target_key_for_pin(endpoint), endpoint))
        return
    drain_row = ctx.rows.primary_inst_row(endpoint)
    if drain_row is None:
        drain_row = next((row for row in rows if row.pin is endpoint or row.class_pin is endpoint), None)
    if drain_row is None:
        return
    pending_drain_src.append((oval_x, oval_bottom, drain_row.rect.y + drain_row.rect.h / 2))


def _draw_shield_plan_side(
    dwg,
    ctx,
    sg: ShieldGroup,
    rows: list[PinRowInfo],
    pending_drain_src: list[tuple[float, float, float]],
    pending_drain_rem: list[tuple[float, float, tuple, Pin]],
    *,
    mirrored: bool,
) -> None:
    runs = _split_contiguous(rows)
    left_endpoint = sg.drain_remote if mirrored else sg.drain
    right_endpoint = sg.drain if mirrored else sg.drain_remote
    left_run = _drain_run_index(runs, left_endpoint)
    right_run = _drain_run_index(runs, right_endpoint)
    term_shift = _CAN_TERM_SHIELD_SHIFT if any(row.pin._can_terminated for row in rows) else 0

    for i, run in enumerate(runs):
        _draw_shield_ovals(
            dwg,
            run,
            sg.label,
            drain=left_endpoint if i == left_run else None,
            drain_remote=right_endpoint if i == right_run else None,
            single_oval=sg.single_oval,
            x_offset=term_shift,
        )
        y_bot_run = max(row.rect.y + row.rect.h for row in run)
        oval_bottom = y_bot_run + 2
        if i == left_run:
            _queue_pin_drain_connection(
                ctx,
                rows,
                run,
                left_endpoint,
                _SHIELD_LEFT_CX + term_shift,
                oval_bottom,
                pending_drain_src,
                pending_drain_rem,
                remote=False,
            )
        if i == right_run:
            _queue_pin_drain_connection(
                ctx,
                rows,
                run,
                right_endpoint,
                _SHIELD_RIGHT_CX,
                oval_bottom,
                pending_drain_src,
                pending_drain_rem,
                remote=True,
            )


def _draw_shield_oval_plan(
    dwg,
    ctx,
    sg: ShieldGroup,
    plan: _ShieldOvalPlan,
    pending_drain_src: list[tuple[float, float, float]],
    pending_drain_rem: list[tuple[float, float, tuple, Pin]],
) -> None:
    for rows in plan.near_rows_by_inst.values():
        _draw_shield_plan_side(dwg, ctx, sg, rows, pending_drain_src, pending_drain_rem, mirrored=False)
    for rows in plan.far_rows_by_inst.values():
        _draw_shield_plan_side(dwg, ctx, sg, rows, pending_drain_src, pending_drain_rem, mirrored=True)


_STICKY_JS = """\
(function(){
  var svg=document.querySelector('svg');
  var CH=28;
  var ol=document.createElementNS('http://www.w3.org/2000/svg','g');
  ol.setAttribute('pointer-events','none');
  svg.appendChild(ol);
  function mk(el){var y=+el.id.split('-')[2];return{el:el,y:y,p:el.parentNode,ns:el.nextSibling};}
  var cs=Array.from(document.querySelectorAll('[id^="sh-comp-"]')).map(mk).sort(function(a,b){return a.y-b.y;});
  var ks=Array.from(document.querySelectorAll('[id^="sh-conn-"]')).map(mk).sort(function(a,b){return a.y-b.y;});
  function sc(){return+svg.getAttribute('height')/svg.getBoundingClientRect().height;}
  function find(arr,thr){var r=null;for(var i=0;i<arr.length;i++){if(arr[i].y<=thr)r=arr[i];else break;}return r;}
  var pc=null,pk=null;
  function sqr(h){
    h.el.querySelectorAll('rect').forEach(function(r){
      var rx=r.getAttribute('rx');
      if(rx){r._rx=rx;r._ry=r.getAttribute('ry');r.removeAttribute('rx');r.removeAttribute('ry');}
    });
  }
  function unsqr(h){
    h.el.querySelectorAll('rect').forEach(function(r){
      if(r._rx){r.setAttribute('rx',r._rx);r.setAttribute('ry',r._ry);delete r._rx;delete r._ry;}
    });
  }
  function stick(h,dy){ol.appendChild(h.el);h.el.setAttribute('transform','translate(0,'+(dy-h.y)+')');sqr(h);}
  function unstick(h){
    unsqr(h);
    var ref=h.ns;
    if(ref&&ref.parentNode===h.p)h.p.insertBefore(h.el,ref);else h.p.appendChild(h.el);
    h.el.removeAttribute('transform');
  }
  function update(){
    var s=sc(),vt=window.scrollY*s;
    var ac=find(cs,vt),ak=find(ks,vt+CH);
    if(ac&&ak&&ak.y<=ac.y)ak=null;
    if(ac!==pc){if(pc)unstick(pc);pc=ac;}
    if(ak!==pk){if(pk)unstick(pk);pk=ak;}
    if(ac){
      var nc=cs[cs.indexOf(ac)+1];
      var cy=nc?Math.min(vt,nc.y-CH):vt;
      stick(ac,cy);
    }
    if(ak){
      var ki=ks.indexOf(ak),nk=ks[ki+1];
      var nc2=ac?cs[cs.indexOf(ac)+1]:null;
      var ny=Infinity;
      if(nk)ny=Math.min(ny,nk.y);
      if(nc2)ny=Math.min(ny,nc2.y);
      var ky=isFinite(ny)?Math.min(vt+CH,ny-CH):vt+CH;
      stick(ak,ky);
    }
  }
  window.addEventListener('scroll',update,{passive:true});
  window.addEventListener('resize',update,{passive:true});
  update();
})();
"""


def _inject_sticky_script(output_path: str | Path) -> None:
    p = Path(output_path)
    text = p.read_text(encoding="utf-8")
    tag = '<script type="text/ecmascript"><![CDATA[\n' + _STICKY_JS + "]]></script>"
    p.write_text(text.replace("</svg>", tag + "</svg>", 1), encoding="utf-8")


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
    ctx = build_render_context(harness, layout)

    min_term_cx = _compute_min_term_cx(layout, harness)

    if component is not None:
        sect_rect = layout.section_rects[id(component)]
        vb_y = sect_rect.y - MARGIN
        vb_h = sect_rect.h + 2 * MARGIN
        dwg = draw.Drawing(layout.canvas_width, vb_h, origin=(0, vb_y))
        components_to_render = [component]
        bg = draw.Rectangle(0, vb_y, layout.canvas_width, vb_h, fill="white")
    else:
        dwg = draw.Drawing(layout.canvas_width, layout.canvas_height)
        components_to_render = [c for c in harness.components if c.render]
        bg = draw.Rectangle(0, 0, layout.canvas_width, layout.canvas_height, fill="white")

    dwg.append(
        draw.Raw(
            "<style>"
            "a.pin-link { cursor: pointer; }"
            " a.pin-link:hover rect { fill: #bfdbfe; fill-opacity: 0.45; }"
            " [id^='pr-'] { scroll-margin-top: 56px; }"
            " path { stroke-linecap: square; }"
            "</style>"
        )
    )

    dwg.append(bg)

    jumper_stubs: dict[int, list] = {}  # id(seg) -> [seg, wire_x, bar_x, [cy, ...]]
    deferred_bullets: list[tuple[float, float]] = []  # (cx, cy) drawn after jumper bars

    for comp in components_to_render:
        sect_rect = layout.section_rects[id(comp)]
        _draw_section_bg(dwg, sect_rect, comp.label)

        def _draw_row_and_continuations(primary):
            sh = ctx.shield_for_row(primary)
            _draw_pin_row(dwg, primary, harness, sh, min_term_cx, colored, ctx.pin_shield_palette, jumper_stubs)
            for cont in primary.continuation_rows:
                csh = ctx.shield_for_row(cont)
                _draw_pin_row(dwg, cont, harness, csh, min_term_cx, colored, ctx.pin_shield_palette, jumper_stubs)
            # Drop lines drawn now; bullet glyph deferred until after jumper bars.
            pos = _draw_bullet_and_drop(dwg, primary, colored=colored, pin_shield_palette=ctx.pin_shield_palette)
            if pos is not None:
                deferred_bullets.append(pos)

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

        dwg.append(
            draw.Rectangle(
                sect_rect.x,
                sect_rect.y,
                sect_rect.w,
                sect_rect.h,
                rx=6,
                fill="none",
                stroke="#334155",
                stroke_width=2,
            )
        )

    shield_plans = [(sg, _build_shield_oval_plan(sg, ctx)) for sg in harness.shield_groups if not sg.cable_only]

    # ── drain-pin connection setup ──────────────────────────────────────────
    # A drain pin (sg.drain or sg.drain_remote) belongs to one component but
    # should appear as an extra row only in remote-box views drawn FROM the
    # OTHER components actually wired through that shield. Keying by target
    # alone over-includes (every box pointing to the drain's component would
    # show every drain). So key by (local_comp_key, target_key) instead.
    drains_for_pair: dict[tuple[int, tuple], list[tuple[Pin, ShieldGroup]]] = {}
    for sg, plan in shield_plans:
        touched = _component_keys_for_plan(plan)
        for drain_pin in (sg.drain, sg.drain_remote):
            if not isinstance(drain_pin, Pin):
                continue
            ptkey = _target_key_for_pin(drain_pin)
            for local_ck in touched:
                if local_ck == component_key_for_pin(drain_pin):
                    continue  # drain pin's own component renders it as a local row
                bucket = drains_for_pair.setdefault((local_ck, ptkey), [])
                if not any(pin is drain_pin and shield is sg for pin, shield in bucket):
                    bucket.append((drain_pin, sg))

    # Pending vertical connections drawn after remote boxes:
    #   source-side: (oval_x, oval_bottom, drain_pin_cy)
    #   remote-side: (oval_x, oval_bottom, target_key, drain_pin)
    pending_drain_src: list[tuple[float, float, float]] = []
    pending_drain_rem: list[tuple[float, float, tuple, Pin]] = []

    # ── shield ovals ────────────────────────────────────────────────────────
    for sg, plan in shield_plans:
        _draw_shield_oval_plan(dwg, ctx, sg, plan, pending_drain_src, pending_drain_rem)

    # ── jumper vertical bars ─────────────────────────────────────────────────
    for entry in jumper_stubs.values():
        seg, wx, bar_x, cys = entry
        if len(cys) == 2:
            attrs = _wire_attrs(seg, ctx.pin_shield_palette, colored)
            dwg.append(draw.Line(bar_x, min(cys), bar_x, max(cys), **attrs))

    # ── bullets (on top of jumper bars) ──────────────────────────────────────
    for bullet_cx, bullet_cy in deferred_bullets:
        _draw_bullet(dwg, bullet_cx, bullet_cy)

    # ── remote component boxes ───────────────────────────────────────────────
    rendered_pin_ids = ctx.rows.rendered_pin_ids
    for group in layout.pin_groups:
        if group.target_key[0] != "component":
            continue
        if not group.rows:
            continue
        local_pin = group.rows[0].pin
        local_ck = component_key_for_pin(local_pin) if isinstance(local_pin, Pin) else id(local_pin)
        extras = drains_for_pair.get((local_ck, group.target_key), [])
        extra = [p for p, _ in extras]
        drain_cys = _draw_remote_box(
            dwg,
            group,
            harness,
            layout.remote_box_w,
            rendered_pin_ids,
            extra_drain_pins=extra if extra else None,
        )
        # Draw the remote-side drain L-connections for this box.
        if drain_cys:
            box_x = group.rows[0].wire_start_x + _REMOTE_BOX_X
            for oval_x, oval_bottom, tkey, drain_pin in pending_drain_rem:
                if tkey != group.target_key:
                    continue
                idx = next((i for i, (p, _) in enumerate(extras) if p is drain_pin), None)
                if idx is not None and idx < len(drain_cys):
                    drain_cy = drain_cys[idx]
                    dwg.append(
                        draw.Line(oval_x, oval_bottom, oval_x, drain_cy, stroke=_DRAIN_PIN_COLOR, stroke_width=1.5)
                    )
                    dwg.append(draw.Line(oval_x, drain_cy, box_x, drain_cy, stroke=_DRAIN_PIN_COLOR, stroke_width=1.5))

    # ── source-side drain connections ────────────────────────────────────────
    for oval_x, oval_bottom, drain_cy in pending_drain_src:
        dwg.append(draw.Line(oval_x, oval_bottom, oval_x, drain_cy, stroke=_DRAIN_PIN_COLOR, stroke_width=1.5))

    # ── CAN TERM boxes ───────────────────────────────────────────────────────
    for comp in components_to_render:
        for conn in comp._connectors.values():
            term_rows = []
            for inst_pin in vars(conn).values():
                if isinstance(inst_pin, Pin) and inst_pin._can_terminated:
                    row = ctx.rows.primary_inst_row(inst_pin)
                    if row is not None:
                        term_rows.append(row)
            if len(term_rows) >= 2:
                wx = term_rows[0].wire_start_x
                y_top = min(r.rect.y for r in term_rows)
                y_bot = max(r.rect.y + r.rect.h for r in term_rows)
                _draw_can_term_box(dwg, wx + _CAN_TERM_BOX_CX, y_top, y_bot)

    dwg.save_svg(str(output_path))

    if component is None:
        _inject_sticky_script(output_path)
