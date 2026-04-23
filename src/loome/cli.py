from __future__ import annotations

import argparse
import sys
from pathlib import Path

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

    args = parser.parse_args()

    if args.cmd == "render":
        _cmd_render(args)
    elif args.cmd == "bundle":
        _cmd_bundle(args)


def _load_harness(spec_path: Path):
    namespace: dict = {}
    exec(compile(spec_path.read_text(), str(spec_path), "exec"), namespace)

    harness = namespace.get("harness")
    if harness is None:
        print("Error: spec must assign a 'harness' variable", file=sys.stderr)
        sys.exit(1)

    harness.autodetect(namespace)
    return harness


def _cmd_render(args) -> None:
    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    harness = _load_harness(spec_path)
    layout_result = layout(harness, show_unconnected=args.show_unconnected)
    render(harness, layout_result, args.output, colored=not args.no_color)
    print(f"Rendered {len(harness.components)} component(s) → {args.output}")


def _cmd_bundle(args) -> None:
    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    harness = _load_harness(spec_path)
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


if __name__ == "__main__":
    main()
