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

- **Read-only CLI mode for generated wire IDs** — `render`, `bundle`, `bom`, and `fuses`
  currently assign IDs through the same path that writes `<spec>.wires.yaml`. Add a
  `--no-write-wire-ids` / `--check-wire-ids` mode so CI, examples, and exploratory renders
  can run without mutating sidecar files.

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

- **Broader semantic validation** — extend `loome validate` beyond bundle topology. Useful
  checks include duplicate component labels / terminal IDs, duplicate connector pin numbers,
  duplicate manual wire IDs, unsupported wire colors, unresolved systems when
  `default_system=None`, orphan terminals, multiple protective devices feeding one branch,
  and CAN buses with missing or extra terminations.

- **Machine-readable exports** — add JSON output for BOM, fuse schedules, and a normalized
  netlist (`components`, `connectors`, `pins`, `segments`, `terminals`, `bundles`). This would
  make loome easier to integrate with spreadsheets, CAD/electrical tools, custom QA scripts,
  and downstream label/cut-list tooling.

- **Part metadata and richer BOM rows** — let components, connectors, terminals, pins, and
  disconnects carry optional manufacturer part numbers, connector housing references, contact
  part numbers, backshells, seals, and quantities. The BOM can then move from wire inventory
  toward an orderable build list.

- **Wire cut list / label report** — generate a fabrication-oriented report separate from the
  BOM: wire ID, from/to endpoint, length, color/gauge, shield/cable membership, disconnect side
  suffixes, label text, and optional service-loop / strip-length allowances.

- **Configurable length policies** — support bundle- or harness-level allowances such as service
  loops, branch slack, minimum cut length, and unit conversion/rounding rules so displayed lengths
  and BOM totals match real shop practices.

## Internal cleanup

- **Split oversized modules** — `bom.py`, `renderers/wires.py`, `renderers/svg.py`,
  `disconnects.py`, and `ports.py` each carry several responsibilities. Break them into smaller
  collector, model, layout, and formatting helpers so future changes have narrower blast radius.

- **Separate spec loading from side effects** — CLI commands currently load a spec, autodetect the
  harness, assign wire IDs, and write the sidecar file through one path. Split these into explicit
  load, normalize, assign, and persist steps so read-only commands and tests can exercise each stage
  independently.

- **Extract CLI command bodies** — move `loome` command behavior into testable functions that return
  structured results/status instead of printing and exiting directly. Keep the argparse layer thin.

- **Extract validation rules** — move semantic checks into composable validators with focused tests.
  That keeps `Harness.validate()` small while making future checks such as duplicate IDs, orphan
  terminals, and CAN termination rules easy to add.

- **Reduce renderer coupling** — endpoint/remote-end resolution and render-time row/shield indexes are
  now shared instead of built inline in `renderers/svg.py`. SVG geometry decisions, presentation
  attributes, and DOM construction are still interleaved; continue extracting
  render planning so schematic features can be added without threading state through low-level
  drawing functions.

- **Tighten typing around endpoints and attachments** — endpoint helper protocols and an
  `AttachmentTarget` alias now exist under `loome._internal`, but many call sites still accept broad
  `object`s. Continue by adding small shared types for renderable terminal-like objects and using the
  helper types more consistently in bundle/layout APIs.

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

- **Pinout/component import helpers** — provide a workflow for creating `Component` classes from
  structured pinout data (CSV/YAML, and eventually extracted PDF tables). This would reduce the
  cost of adding new avionics boxes and make built-in component definitions easier to audit.
