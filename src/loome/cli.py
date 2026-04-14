from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loome.layout.engine import layout
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

    args = parser.parse_args()

    if args.cmd == "render":
        _cmd_render(args)


def _cmd_render(args) -> None:
    spec_path = Path(args.spec).resolve()
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    namespace: dict = {}
    exec(compile(spec_path.read_text(), str(spec_path), "exec"), namespace)

    harness = namespace.get("harness")
    if harness is None:
        print("Error: spec must assign a 'harness' variable", file=sys.stderr)
        sys.exit(1)

    harness.autodetect(namespace)
    layout_result = layout(harness, show_unconnected=args.show_unconnected)
    render(harness, layout_result, args.output, colored=not args.no_color)
    print(f"Rendered {len(harness.components)} component(s) → {args.output}")


if __name__ == "__main__":
    main()
