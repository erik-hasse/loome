from __future__ import annotations

from pathlib import Path

import drawsvg as draw

from .._internal.endpoints import component_key_for_pin, connector_key_for_pin, other_endpoint
from ..harness import Harness
from ..layout.engine import MARGIN, LayoutResult, PinRowInfo
from ..model import Component, Pin, ShieldDrainTerminal, ShieldGroup, SpliceNode, Terminal
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

    # ── drain-pin connection setup ──────────────────────────────────────────
    # A drain pin (sg.drain or sg.drain_remote) belongs to one component but
    # should appear as an extra row only in remote-box views drawn FROM the
    # OTHER components actually wired through that shield. Keying by target
    # alone over-includes (every box pointing to the drain's component would
    # show every drain). So key by (local_comp_key, target_key) instead.
    drains_for_pair: dict[tuple[int, tuple], list[tuple[Pin, ShieldGroup]]] = {}
    for sg in harness.shield_groups:
        if not sg.segments:
            continue
        # Component instances touched by this shield's segments.
        touched: set[int] = set()
        for seg in sg.segments:
            for ep in (seg.end_a, seg.end_b):
                if isinstance(ep, Pin):
                    touched.add(component_key_for_pin(ep))
        for p in (sg.drain, sg.drain_remote):
            if not isinstance(p, Pin):
                continue
            ptkey = ("component", component_key_for_pin(p), connector_key_for_pin(p))
            for local_ck in touched:
                if local_ck == component_key_for_pin(p):
                    continue  # drain pin's own component renders it as a local row
                drains_for_pair.setdefault((local_ck, ptkey), []).append((p, sg))

    # Pending vertical connections drawn after remote boxes:
    #   source-side: (oval_x, oval_bottom, drain_pin_cy)
    #   remote-side: (oval_x, oval_bottom, target_key, drain_pin)
    pending_drain_src: list[tuple[float, float, float]] = []
    pending_drain_rem: list[tuple[float, float, tuple, Pin]] = []

    # ── shield ovals ────────────────────────────────────────────────────────
    for sg in harness.shield_groups:
        if sg.cable_only:
            continue
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
                seg_rows = ctx.rows.rows_for_segment(seg)
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
                            row = ctx.rows.row_for_pin(ep)
                            if row is not None:
                                _add_row(target, row)
                    elif isinstance(ep, SpliceNode):
                        # Splice indirection: pull the splice's upstream pin
                        # row in (the wire visually extends through the splice).
                        for other_seg in ep._connections:
                            if other_seg is seg:
                                continue
                            other_ep = other_endpoint(other_seg, ep)
                            if isinstance(other_ep, Pin):
                                # Prefer the row whose segment is the splice's upstream wire.
                                up_rows = [ri for ri in ctx.rows.rows_for_inst_pin(other_ep) if ri.segment is other_seg]
                                if up_rows:
                                    for ri in up_rows:
                                        _add_row(target, ri)
                                else:
                                    for ri in ctx.rows.rows_for_inst_pin(other_ep):
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
                        drain=sg.drain if i == left_run else None,
                        drain_remote=sg.drain_remote if i == right_run else None,
                    )
                    # Collect Pin-drain connections (drawn after remote boxes).
                    wx_run = run[0].wire_start_x
                    y_bot_run = max(r.rect.y + r.rect.h for r in run)
                    oval_bottom = y_bot_run + 2
                    if isinstance(sg.drain, Pin) and i == left_run:
                        drain_row = ctx.rows.primary_inst_row(sg.drain)
                        if drain_row is not None:
                            pending_drain_src.append(
                                (wx_run + _SHIELD_LEFT_CX, oval_bottom, drain_row.rect.y + drain_row.rect.h / 2)
                            )
                    if isinstance(sg.drain_remote, Pin) and i == right_run:
                        p = sg.drain_remote
                        pending_drain_rem.append(
                            (
                                wx_run + _SHIELD_RIGHT_CX,
                                oval_bottom,
                                ("component", component_key_for_pin(p), connector_key_for_pin(p)),
                                p,
                            )
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
                        drain=sg.drain_remote if i == left_run else None,
                        drain_remote=sg.drain if i == right_run else None,
                    )
                    # Mirror of src-side: wire drain Pins on this view.
                    wx_run = run[0].wire_start_x
                    y_bot_run = max(r.rect.y + r.rect.h for r in run)
                    oval_bottom = y_bot_run + 2
                    if isinstance(sg.drain_remote, Pin) and i == left_run:
                        drain_row = ctx.rows.primary_inst_row(sg.drain_remote)
                        if drain_row is not None:
                            pending_drain_src.append(
                                (wx_run + _SHIELD_LEFT_CX, oval_bottom, drain_row.rect.y + drain_row.rect.h / 2)
                            )
                    if isinstance(sg.drain, Pin) and i == right_run:
                        p = sg.drain
                        pending_drain_rem.append(
                            (
                                wx_run + _SHIELD_RIGHT_CX,
                                oval_bottom,
                                ("component", component_key_for_pin(p), connector_key_for_pin(p)),
                                p,
                            )
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
                for ri in ctx.rows.rows_for_class_pin(p):
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
                        drain=sg.drain if i == left_run else None,
                        drain_remote=sg.drain_remote if i == right_run else None,
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
                    remote = other_endpoint(seg, src_pin)
                    if not isinstance(remote, Pin):
                        continue
                    if remote.shield_group is not None:
                        continue
                    row = ctx.rows.row_for_pin(remote)
                    if row is not None:
                        remote_rows_by_source.setdefault(source_key, []).append(row)

            for p in sg.pins:
                _add_remote_for_source(p, id(sg))
                for ri in ctx.rows.rows_for_class_pin(p):
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
                        drain=sg.drain_remote if i == left_run else None,
                        drain_remote=sg.drain if i == right_run else None,
                        single_oval=sg.single_oval,
                    )

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
