from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from loome.bom import (
    build_bom,
    build_fuse_schedule,
    render_bom_csv,
    render_bom_md,
    render_fuse_schedule_csv,
    render_fuse_schedule_md,
)
from loome.layout.bundle_layout import layout_bundle
from loome.layout.engine import layout
from loome.renderers.assets import asset_text
from loome.renderers.builder import builder_entries_for_script
from loome.renderers.bundle import render_bundle
from loome.renderers.svg import render
from loome.renderers.wires import _pin_row_id
from loome.wire_ids import (
    WireIdCheckError,
    assign_wire_ids,
    harness_builder_key,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="loome",
        description="Wiring harness diagram generator",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    render_cmd = sub.add_parser("render", help="Render a harness spec to SVG")
    render_cmd.add_argument("spec", help="Python harness spec file")
    render_cmd.add_argument("-o", "--output", default="out.svg", help="Output SVG path")
    render_cmd.add_argument("--no-color", action="store_true", help="Render wires in monochrome")
    render_cmd.add_argument("--builder", action="store_true", help="Emit builder-mode SVG controls and metadata")
    render_cmd.add_argument(
        "--show-unconnected",
        action="store_true",
        help="Render pins with no connections (useful while building the harness)",
    )
    _add_wire_id_args(render_cmd)

    bundle_cmd = sub.add_parser("bundle", help="Render a bundle's physical-layout tree SVG")
    bundle_cmd.add_argument("spec", help="Python harness spec file")
    bundle_cmd.add_argument("-o", "--output", default="bundle.svg", help="Output SVG path")
    bundle_cmd.add_argument("--name", default=None, help="Render only the bundle with this name")
    _add_wire_id_args(bundle_cmd)

    bom_cmd = sub.add_parser("bom", help="Emit a bill of materials (wires, connectors, terminals)")
    bom_cmd.add_argument("spec", help="Python harness spec file")
    bom_cmd.add_argument("-o", "--output", default=None, help="Output file (default: stdout)")
    bom_cmd.add_argument("--format", choices=("md", "csv"), default="md", help="Output format")
    _add_wire_id_args(bom_cmd)

    fuses_cmd = sub.add_parser("fuses", help="Emit the fuse / CB schedule")
    fuses_cmd.add_argument("spec", help="Python harness spec file")
    fuses_cmd.add_argument("-o", "--output", default=None, help="Output file (default: stdout)")
    fuses_cmd.add_argument("--format", choices=("md", "csv"), default="md", help="Output format")
    _add_wire_id_args(fuses_cmd)

    validate_cmd = sub.add_parser("validate", help="Validate bundle topology; exit non-zero on warnings")
    validate_cmd.add_argument("spec", help="Python harness spec file")
    _add_wire_id_args(validate_cmd)

    args = parser.parse_args()

    if args.cmd == "render":
        _cmd_render(args)
    elif args.cmd == "bundle":
        _cmd_bundle(args)
    elif args.cmd == "bom":
        _cmd_bom(args)
    elif args.cmd == "fuses":
        _cmd_fuses(args)
    elif args.cmd == "validate":
        _cmd_validate(args)


def _add_wire_id_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write-wire-ids", action="store_true", help="Update <spec>.wires.yaml with generated wire IDs")
    group.add_argument("--check-wire-ids", action="store_true", help="Fail if generated wire IDs would change sidecar")


def _load_harness(spec_path: Path, *, persist_wire_ids: bool = False, check_wire_ids: bool = False):
    namespace: dict = {}
    exec(compile(spec_path.read_text(), str(spec_path), "exec"), namespace)

    harness = namespace.get("harness")
    if harness is None:
        print("Error: spec must assign a 'harness' variable", file=sys.stderr)
        sys.exit(1)

    harness.autodetect(namespace)
    try:
        assignment = assign_wire_ids(harness, spec_path, persist=persist_wire_ids, check=check_wire_ids)
    except WireIdCheckError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    harness._wire_id_assignment = assignment  # type: ignore[attr-defined]
    return harness


def _safe_filename(label: str) -> str:
    """Convert a component label to a safe SVG filename stem."""
    return re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_") or "component"


def _cmd_render(args) -> None:
    spec_path = Path(args.spec).resolve()
    sidecar_name = spec_path.with_suffix(".wires.yaml").name
    harness = _load_spec_or_exit(
        args.spec,
        persist_wire_ids=args.write_wire_ids,
        check_wire_ids=args.check_wire_ids,
    )
    layout_result = layout(harness, show_unconnected=args.show_unconnected)
    output = Path(args.output)
    assignment = getattr(harness, "_wire_id_assignment", None)
    builder_key = harness_builder_key(harness, assignment.entries) if assignment is not None else None

    if output.is_dir() or not output.suffix:
        output.mkdir(parents=True, exist_ok=True)
        rendered = [c for c in harness.components if c.render]
        pin_index = _builder_pin_index(layout_result)
        builder_pages = []
        for comp in rendered:
            out_file = output / f"{_safe_filename(comp.label)}.svg"
            render(
                harness,
                layout_result,
                out_file,
                colored=not args.no_color,
                component=comp,
                builder=args.builder,
            )
            if args.builder:
                builder_pages.append(
                    {
                        "label": comp.label,
                        "stem": _safe_filename(comp.label),
                        "svg": _read_svg_markup(out_file),
                    }
                )
        if args.builder:
            _write_builder_index(
                output,
                builder_pages,
                builder_key or "",
                harness,
                pin_index,
                sidecar_name,
                selector_entries=builder_pages,
                single_page=False,
            )
        print(f"Rendered {len(rendered)} component(s) → {output}/")
    else:
        render(
            harness,
            layout_result,
            output,
            colored=not args.no_color,
            builder=args.builder,
        )
        if args.builder:
            _write_builder_index(
                output.parent,
                [{"label": output.stem, "stem": output.stem, "svg": _read_svg_markup(output)}],
                builder_key or "",
                harness,
                _builder_pin_index(layout_result),
                sidecar_name,
                selector_entries=_builder_component_entries(harness, layout_result),
                single_page=True,
            )
        print(f"Rendered {len(harness.components)} component(s) → {output}")


def _cmd_bundle(args) -> None:
    harness = _load_spec_or_exit(
        args.spec,
        persist_wire_ids=args.write_wire_ids,
        check_wire_ids=args.check_wire_ids,
    )
    if not harness.bundles:
        print("Error: spec has no bundles to render", file=sys.stderr)
        sys.exit(1)

    bundles = harness.bundles
    if args.name:
        bundles = [b for b in bundles if b.name == args.name]
        if not bundles:
            print(f"Error: no bundle named {args.name!r}", file=sys.stderr)
            sys.exit(1)

    warnings = harness.validate_bundles()
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    output = Path(args.output)
    if len(bundles) == 1:
        bl = layout_bundle(bundles[0], harness)
        render_bundle(bl, harness, output)
        print(f"Rendered bundle {bundles[0].name!r} → {output}")
    else:
        stem = output.stem
        suffix = output.suffix or ".svg"
        parent = output.parent
        for bundle in bundles:
            safe = bundle.name.replace(" ", "_")
            out_path = parent / f"{stem}_{safe}{suffix}"
            bl = layout_bundle(bundle, harness)
            render_bundle(bl, harness, out_path)
            print(f"Rendered bundle {bundle.name!r} → {out_path}")


def _load_spec_or_exit(spec_arg: str, *, persist_wire_ids: bool = False, check_wire_ids: bool = False):
    spec_path = Path(spec_arg).resolve()
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)
    return _load_harness(spec_path, persist_wire_ids=persist_wire_ids, check_wire_ids=check_wire_ids)


def _emit(text: str, output: str | None) -> None:
    if output is None:
        sys.stdout.write(text)
    else:
        Path(output).write_text(text)


def _cmd_bom(args) -> None:
    harness = _load_spec_or_exit(
        args.spec,
        persist_wire_ids=args.write_wire_ids,
        check_wire_ids=args.check_wire_ids,
    )
    bom = build_bom(harness)
    rendered = render_bom_md(bom, harness) if args.format == "md" else render_bom_csv(bom, harness)
    _emit(rendered, args.output)


def _cmd_fuses(args) -> None:
    harness = _load_spec_or_exit(
        args.spec,
        persist_wire_ids=args.write_wire_ids,
        check_wire_ids=args.check_wire_ids,
    )
    schedule = build_fuse_schedule(harness)
    rendered = (
        render_fuse_schedule_md(schedule, harness)
        if args.format == "md"
        else render_fuse_schedule_csv(schedule, harness)
    )
    _emit(rendered, args.output)


def _cmd_validate(args) -> None:
    harness = _load_spec_or_exit(
        args.spec,
        persist_wire_ids=args.write_wire_ids,
        check_wire_ids=args.check_wire_ids,
    )
    warnings = harness.validate_bundles()
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if warnings:
        sys.exit(1)
    print("OK")


def _builder_component_options(entries: list[dict[str, str]]) -> str:
    options: list[str] = []
    for entry in entries:
        target = entry.get("target")
        target_attr = f' data-target="{html.escape(target, quote=True)}"' if target else ""
        options.append(
            f'<option value="{html.escape(entry["stem"], quote=True)}"{target_attr}>'
            f"{html.escape(entry['label'])}</option>"
        )
    return "\n".join(options)


def _builder_component_entries(harness, layout_result) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for comp in harness.components:
        if not comp.render:
            continue
        rect = layout_result.section_rects.get(id(comp))
        if rect is None:
            continue
        entries.append(
            {
                "label": comp.label,
                "stem": _safe_filename(comp.label),
                "target": f"sh-comp-{int(rect.y)}",
            }
        )
    return entries


def _builder_pin_index(layout_result) -> dict[str, str]:
    pages: dict[str, str] = {}
    for row in layout_result.all_rows:
        if row.is_continuation:
            continue
        comp = row.pin._component
        if comp is None:
            continue
        pages[_pin_row_id(row.pin)] = _safe_filename(comp.label)
    return pages


def _builder_shell(
    *,
    builder_key: str,
    pages: list[dict[str, str]],
    harness,
    pin_index: dict[str, str],
    sidecar_name: str,
    selector_entries: list[dict[str, str]] | None = None,
    single_page: bool = False,
) -> str:
    entries = json.dumps(builder_entries_for_script(harness))
    pin_index_json = json.dumps(pin_index)
    component_options = _builder_component_options(selector_entries or pages)
    component_selector = (
        f'<select id="loome-builder-component" aria-label="Component">{component_options}</select>'
        if component_options
        else ""
    )
    views = "\n".join(
        f'<section class="component-view" data-component="{page["stem"]}" hidden>{page["svg"]}</section>'
        for page in pages
    )
    return asset_text("builder.html").format(
        title="Loome Builder",
        css=asset_text("builder.css"),
        component_selector=component_selector,
        views=views,
        builder_key=json.dumps(builder_key),
        entries=entries,
        pin_index=pin_index_json,
        sidecar_name=json.dumps(sidecar_name),
        single_page=json.dumps(single_page),
        js=asset_text("builder.js"),
    )


def _read_svg_markup(path: Path) -> str:
    svg_markup = path.read_text(encoding="utf-8")
    svg_markup = re.sub(r"^\s*<\?xml[^>]*>\s*", "", svg_markup)
    return svg_markup


def _write_builder_index(
    output: Path,
    pages: list[dict[str, str]],
    builder_key: str,
    harness,
    pin_index: dict[str, str],
    sidecar_name: str,
    selector_entries: list[dict[str, str]] | None = None,
    single_page: bool = False,
) -> None:
    output.joinpath("index.html").write_text(
        _builder_shell(
            builder_key=builder_key,
            pages=pages,
            harness=harness,
            pin_index=pin_index,
            sidecar_name=sidecar_name,
            selector_entries=selector_entries,
            single_page=single_page,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
