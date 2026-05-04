"""SVG renderer for a bundle's abstract tree schematic."""

from __future__ import annotations

from pathlib import Path

import drawsvg as draw

from ..harness import Harness
from ..layout.bundle_layout import BundleLayout


def render_bundle(
    layout: BundleLayout,
    harness: Harness,
    output_path: str | Path,
) -> None:
    dwg = draw.Drawing(layout.canvas_width, layout.canvas_height)
    dwg.append(draw.Rectangle(0, 0, layout.canvas_width, layout.canvas_height, fill="white"))

    # Title
    dwg.append(
        draw.Text(
            layout.bundle.name,
            14,
            12,
            18,
            font_family="sans-serif",
            font_weight="bold",
            fill="#0f172a",
        )
    )

    # ── edges (trunk + branches) ────────────────────────────────────────────
    for parent_node, child_node, label in layout.edges:
        dwg.append(
            draw.Line(
                parent_node.x,
                parent_node.y,
                child_node.x,
                child_node.y,
                stroke="#0f172a",
                stroke_width=3,
            )
        )
        if label:
            mx = (parent_node.x + child_node.x) / 2
            my = (parent_node.y + child_node.y) / 2
            dwg.append(
                draw.Text(
                    label,
                    10,
                    mx + 4,
                    my - 4,
                    font_family="sans-serif",
                    fill="#475569",
                )
            )

    # ── breakout dots ────────────────────────────────────────────────────────
    for node in layout.nodes.values():
        dwg.append(
            draw.Circle(
                node.x,
                node.y,
                5,
                fill="#0f172a",
                stroke="#0f172a",
            )
        )
        dwg.append(
            draw.Text(
                node.breakout.id,
                10,
                node.x + 8,
                node.y - 8,
                font_family="sans-serif",
                fill="#0f172a",
            )
        )

    # ── attachment boxes and legs ────────────────────────────────────────────
    for box in layout.attachment_boxes:
        dwg.append(
            draw.Line(
                box.leg_x1,
                box.leg_y1,
                box.leg_x2,
                box.leg_y2,
                stroke="#475569",
                stroke_width=1.5,
            )
        )
        dwg.append(
            draw.Rectangle(
                box.rect.x,
                box.rect.y,
                box.rect.w,
                box.rect.h,
                rx=4,
                fill="#f8fafc",
                stroke="#334155",
                stroke_width=1.2,
            )
        )
        dwg.append(
            draw.Text(
                box.header,
                10,
                box.rect.x + 6,
                box.rect.y + 14,
                font_family="sans-serif",
                font_weight="bold",
                fill="#0f172a",
            )
        )
        # header separator
        dwg.append(
            draw.Line(
                box.rect.x,
                box.rect.y + 20,
                box.rect.x2,
                box.rect.y + 20,
                stroke="#cbd5e1",
                stroke_width=1,
            )
        )
        row_y = box.rect.y + 20 + 12
        for row in box.rows:
            pin_label = ""
            if row.pin is not None:
                pin_label = f"{row.pin.number} {row.pin.signal_name or ''}".strip()
            length_str = harness.format_length(row.length)
            left_txt = pin_label if pin_label else (row.wire_label or "")
            right_txt = length_str
            dwg.append(
                draw.Text(
                    left_txt,
                    9,
                    box.rect.x + 6,
                    row_y,
                    font_family="monospace",
                    fill="#0f172a",
                )
            )
            if row.wire_label and pin_label:
                dwg.append(
                    draw.Text(
                        row.wire_label,
                        9,
                        box.rect.x + box.rect.w / 2,
                        row_y,
                        font_family="monospace",
                        fill="#475569",
                        text_anchor="middle",
                    )
                )
            dwg.append(
                draw.Text(
                    right_txt,
                    9,
                    box.rect.x2 - 6,
                    row_y,
                    font_family="monospace",
                    fill="#0f172a",
                    text_anchor="end",
                )
            )
            row_y += 16

    dwg.save_svg(str(output_path))
