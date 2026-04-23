"""SVG renderer for a bundle's abstract tree schematic."""

from __future__ import annotations

from pathlib import Path

import svgwrite

from ..harness import Harness
from ..layout.bundle_layout import BundleLayout, _format_length


def render_bundle(
    layout: BundleLayout,
    harness: Harness,
    output_path: str | Path,
) -> None:
    dwg = svgwrite.Drawing(str(output_path), size=(layout.canvas_width, layout.canvas_height), profile="full")
    dwg.add(dwg.rect(insert=(0, 0), size=("100%", "100%"), fill="white"))

    # Title
    dwg.add(
        dwg.text(
            layout.bundle.name,
            insert=(12, 18),
            font_family="sans-serif",
            font_size=14,
            font_weight="bold",
            fill="#0f172a",
        )
    )

    # ── edges (trunk + branches) ────────────────────────────────────────────
    for parent_node, child_node, label in layout.edges:
        dwg.add(
            dwg.line(
                start=(parent_node.x, parent_node.y),
                end=(child_node.x, child_node.y),
                stroke="#0f172a",
                stroke_width=3,
            )
        )
        if label:
            mx = (parent_node.x + child_node.x) / 2
            my = (parent_node.y + child_node.y) / 2
            dwg.add(
                dwg.text(
                    label,
                    insert=(mx + 4, my - 4),
                    font_family="sans-serif",
                    font_size=10,
                    fill="#475569",
                )
            )

    # ── breakout dots ────────────────────────────────────────────────────────
    for node in layout.nodes.values():
        dwg.add(
            dwg.circle(
                center=(node.x, node.y),
                r=5,
                fill="#0f172a",
                stroke="#0f172a",
            )
        )
        dwg.add(
            dwg.text(
                node.breakout.id,
                insert=(node.x + 8, node.y - 8),
                font_family="sans-serif",
                font_size=10,
                fill="#0f172a",
            )
        )

    # ── attachment boxes and legs ────────────────────────────────────────────
    for box in layout.attachment_boxes:
        dwg.add(
            dwg.line(
                start=(box.leg_x1, box.leg_y1),
                end=(box.leg_x2, box.leg_y2),
                stroke="#475569",
                stroke_width=1.5,
            )
        )
        dwg.add(
            dwg.rect(
                insert=(box.rect.x, box.rect.y),
                size=(box.rect.w, box.rect.h),
                rx=4,
                ry=4,
                fill="#f8fafc",
                stroke="#334155",
                stroke_width=1.2,
            )
        )
        dwg.add(
            dwg.text(
                box.header,
                insert=(box.rect.x + 6, box.rect.y + 14),
                font_family="sans-serif",
                font_size=10,
                font_weight="bold",
                fill="#0f172a",
            )
        )
        # header separator
        dwg.add(
            dwg.line(
                start=(box.rect.x, box.rect.y + 20),
                end=(box.rect.x2, box.rect.y + 20),
                stroke="#cbd5e1",
                stroke_width=1,
            )
        )
        row_y = box.rect.y + 20 + 12
        for row in box.rows:
            pin_label = ""
            if row.pin is not None:
                pin_label = f"{row.pin.number} {row.pin.signal_name or ''}".strip()
            length_str = _format_length(row.length, harness.length_unit)
            left_txt = pin_label if pin_label else (row.wire_label or "")
            right_txt = length_str
            dwg.add(
                dwg.text(
                    left_txt,
                    insert=(box.rect.x + 6, row_y),
                    font_family="monospace",
                    font_size=9,
                    fill="#0f172a",
                )
            )
            if row.wire_label and pin_label:
                dwg.add(
                    dwg.text(
                        row.wire_label,
                        insert=(box.rect.x + box.rect.w / 2, row_y),
                        font_family="monospace",
                        font_size=9,
                        fill="#475569",
                        text_anchor="middle",
                    )
                )
            dwg.add(
                dwg.text(
                    right_txt,
                    insert=(box.rect.x2 - 6, row_y),
                    font_family="monospace",
                    font_size=9,
                    fill="#0f172a",
                    text_anchor="end",
                )
            )
            row_y += 16

    dwg.save()
