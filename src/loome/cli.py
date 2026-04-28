from __future__ import annotations

import argparse
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
from loome.renderers.bundle import render_bundle
from loome.renderers.svg import render


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
    render_cmd.add_argument(
        "--show-unconnected",
        action="store_true",
        help="Render pins with no connections (useful while building the harness)",
    )

    bundle_cmd = sub.add_parser("bundle", help="Render a bundle's physical-layout tree SVG")
    bundle_cmd.add_argument("spec", help="Python harness spec file")
    bundle_cmd.add_argument("-o", "--output", default="bundle.svg", help="Output SVG path")
    bundle_cmd.add_argument("--name", default=None, help="Render only the bundle with this name")

    bom_cmd = sub.add_parser("bom", help="Emit a bill of materials (wires, connectors, terminals)")
    bom_cmd.add_argument("spec", help="Python harness spec file")
    bom_cmd.add_argument("-o", "--output", default=None, help="Output file (default: stdout)")
    bom_cmd.add_argument("--format", choices=("md", "csv"), default="md", help="Output format")

    fuses_cmd = sub.add_parser("fuses", help="Emit the fuse / CB schedule")
    fuses_cmd.add_argument("spec", help="Python harness spec file")
    fuses_cmd.add_argument("-o", "--output", default=None, help="Output file (default: stdout)")
    fuses_cmd.add_argument("--format", choices=("md", "csv"), default="md", help="Output format")

    args = parser.parse_args()

    if args.cmd == "render":
        _cmd_render(args)
    elif args.cmd == "bundle":
        _cmd_bundle(args)
    elif args.cmd == "bom":
        _cmd_bom(args)
    elif args.cmd == "fuses":
        _cmd_fuses(args)


def _load_harness(spec_path: Path):
    namespace: dict = {}
    exec(compile(spec_path.read_text(), str(spec_path), "exec"), namespace)

    harness = namespace.get("harness")
    if harness is None:
        print("Error: spec must assign a 'harness' variable", file=sys.stderr)
        sys.exit(1)

    harness.autodetect(namespace)
    return harness


def _safe_filename(label: str) -> str:
    """Convert a component label to a safe SVG filename stem."""
    return re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_") or "component"


def _cmd_render(args) -> None:
    harness = _load_spec_or_exit(args.spec)
    layout_result = layout(harness, show_unconnected=args.show_unconnected)
    output = Path(args.output)

    if output.is_dir() or not output.suffix:
        output.mkdir(parents=True, exist_ok=True)
        rendered = [c for c in harness.components if c.render]
        for comp in rendered:
            out_file = output / f"{_safe_filename(comp.label)}.svg"
            render(harness, layout_result, out_file, colored=not args.no_color, component=comp)
        print(f"Rendered {len(rendered)} component(s) → {output}/")
    else:
        render(harness, layout_result, output, colored=not args.no_color)
        print(f"Rendered {len(harness.components)} component(s) → {output}")


def _cmd_bundle(args) -> None:
    harness = _load_spec_or_exit(args.spec)
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


def _load_spec_or_exit(spec_arg: str):
    spec_path = Path(spec_arg).resolve()
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)
    return _load_harness(spec_path)


def _emit(text: str, output: str | None) -> None:
    if output is None:
        sys.stdout.write(text)
    else:
        Path(output).write_text(text)


def _cmd_bom(args) -> None:
    harness = _load_spec_or_exit(args.spec)
    bom = build_bom(harness)
    rendered = render_bom_md(bom, harness) if args.format == "md" else render_bom_csv(bom, harness)
    _emit(rendered, args.output)


def _cmd_fuses(args) -> None:
    harness = _load_spec_or_exit(args.spec)
    schedule = build_fuse_schedule(harness)
    rendered = (
        render_fuse_schedule_md(schedule, harness)
        if args.format == "md"
        else render_fuse_schedule_csv(schedule, harness)
    )
    _emit(rendered, args.output)


if __name__ == "__main__":
    main()
