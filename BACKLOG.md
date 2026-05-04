# Backlog

Items are roughly in priority order within each section.


## Low effort

- Add optional `max_pins` to a disconnect's init

- **Switch schematic symbols** — `SPST`, `SPDT`, `DPST`, `DPDT` all default to
  `render=False` and have no SVG symbol. Adding simple line-art symbols (single-pole
  arc, double-pole arc) would let users put `render=True` and see switch positions in
  the schematic.

- **PDF export** — `cairosvg` converts SVG → PDF in one call; very low effort once SVG output
  is solid.

- **`SDSECU` incomplete pin numbers** — `tach` and `fuel_flow` pins use placeholder numbers
  `"TBD1"` / `"TBD2"`. Look up the actual SDS ECU wiring diagram and replace with real pin
  identifiers.

- **`BusBar` schematic symbol** — `BusBar` currently renders as a small filled rectangle
  (`primitives.py`). Should instead draw a labeled horizontal bar with tap-point markers,
  matching its role as a shared power rail.

- **`PortBuilder.notes()` semantics** — `PortBuilder.gauge()`, `.color()`, and `.system()`
  now apply to every conductor created by a port connection, but `.notes()` still annotates
  only the primary segment. Decide whether notes should apply to all conductors by default,
  or add an explicit per-conductor note API.

## Medium effort

- **CAN bus rendering** — data-model support is in place: `CanBusLine` captures device
  ordering, `Harness.resolved_length()` returns per-stub lengths for CAN pins, and
  `CanBusLine.stub_lengths_for()` exposes the two-neighbor lengths on intermediate taps.
  What's still missing is the renderer treatment: instead of every can pin stubbing to a
  shared off-page reference, draw a horizontal bus track with each device tapping off it in
  order, plus markers for the terminator devices at either end. layout is the bulk of the
  remaining work; the renderer already has all the length data it needs.

- Support multi-pin on the right hand side (e.g. GTR20 -> GMA245)

- **FuseBlock / CB-bank topology rendering** — the `FuseBlock` and `CircuitBreakerBank`
  data types exist and are consumed by the fuse schedule, but the bundle-layout view
  still attaches each `Fuse` / `CircuitBreaker` individually. Teach `renderers/bundle.py`
  to attach a block or bank to a breakout as a single unit and draw the member fuses/CBs
  inside it, respecting `positions`. Groups that aren't attached fall back to the current
  per-fuse behavior.

- **Terminal-to-terminal schematic rendering** — terminal endpoints can now be wired directly
  (`bus >> fuse`, `fuse >> splice`) and are included in BOM/segments, but schematic rendering
  still needs an explicit design for terminal-only wires that are not anchored by a pin row.
  Bus/fuse feed chains should render visibly instead of existing only as metadata.

## Larger features

- **Interactive SVG** — the sticky headers and remote-pin click-to-jump are already in place.
  Remaining interactivity work, roughly in priority order:

  1. **Cross-component navigation** — `loome render <spec> -o <directory>` already renders
     every component to its own SVG. The remaining work is an `index.html` linking them, plus
     a fixed top bar in each per-component SVG listing all components as links (back/forward
     navigation). This is a prerequisite for builder mode to be useful across a real harness.

  2. **Builder mode** — a toggleable overlay (e.g. `?builder=1` query param or a button) that
     lets the user mark individual wires as "run". Since each wire appears at both ends of the
     schematic, both occurrences need to dim together. Implementation sketch:
     - Emit a `data-seg-id` attribute on both the source pin row and the corresponding remote
       box entry so the JS can find both sides with one query.
     - A click on either end toggles a `wire--done` CSS class on both, visually dimming them.
     - State persists in `localStorage` keyed by a harness fingerprint (e.g. hash of component
       labels) so it survives a page reload.
     - A progress counter in the sticky component header ("14 / 47 wires run") gives per-connector
       completion at a glance.
     - For per-component SVGs, a shared `localStorage` key lets all open pages reflect the same
       state without a sidecar file.
     - In builder mode, wires are only persisted to `*.wires.yaml` when marked "done" instead of
       at render time.

  3. **Expand/collapse connectors** — click a connector header (`sh-conn-` ids are already
     present) to collapse all its pin rows. Useful for large harnesses where you want to focus
     on one connector at a time.

- **Multi-page / off-page split** — for large harnesses, split into logical sections
  (e.g. per sub-system) with `OffPageReference` cross-links between sheets. The model already
  has `OffPageReference`; this is mainly a layout and CLI concern.
