# Backlog

Items are roughly in priority order within each section.


## Backlog — switches (remaining)

- **PDF export** — `cairosvg` converts SVG → PDF in one call; very low effort once SVG output
  is solid.

## Medium effort

- **CAN Bus ordering / visualization** — CAN pins currently render as ordinary wires going to
  an off-page reference. Better treatment: a horizontal bus bar with all CAN devices stubbing
  off it, respecting termination resistor placement. Requires layout changes, not just renderer
  changes.

- **Fuse / CB summary** — `loome fuses spec.py` CLI command (or a dedicated section within the
  BoM) that renders a table of every `Fuse` and `CircuitBreaker` in the harness: name, rating
  (amps), the wire ID / gauge it feeds, and the pin/connector it ultimately protects. Requires
  traversing each terminal's wire connections to identify the protected load. Useful for
  populating the "fuse schedule" block that most aviation and automotive harness drawings
  include. Similar implementation effort to BoM export.

- **BoM export** — `loome bom spec.py` CLI command that outputs a parts list: wire segments
  (id, gauge, color, length if resolved from bundle), connectors + pin counts, terminals.
  Total wire by gauge is useful for cut sheets.

## Larger features

- **Interactive SVG** — embed hover/highlight via `<script>` tags so hovering a wire highlights
  both endpoints. Click-to-follow for tracing signal paths. No external dependencies needed;
  cleanest path is a `loome render --interactive` flag that injects a small JS block.

- **Multi-page / off-page split** — for large harnesses, split into logical sections
  (e.g. per sub-system) with `OffPageReference` cross-links between sheets. The model already
  has `OffPageReference`; this is mainly a layout and CLI concern.
