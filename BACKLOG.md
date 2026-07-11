# Backlog

Items are roughly in priority order within each section.


## Immediate priorities

- **Require CI checks before merge** — after the `CI` workflow has been pushed and has run once,
  configure the default branch's GitHub ruleset / branch protection to require both
  `CI / pre-commit` and `CI / test`. Keep the release workflow dependent on the same reusable
  checks so pull requests and published packages use identical gates.

- **Broader semantic validation** — extend `loome validate` beyond bundle topology. Useful
  checks include duplicate component labels / terminal IDs, duplicate connector pin numbers,
  duplicate manual wire IDs, unsupported wire colors, unresolved systems when
  `default_system=None`, orphan terminals, multiple protective devices feeding one branch,
  and CAN buses with missing or extra terminations.

- **Clean complex-example validation** — make the `n14ev_axis` and `n14ev_g3x` examples pass
  `loome validate`, or explicitly model/suppress intentionally incomplete topology. They currently
  produce warnings for unattached CAN devices and CAN-capable connectors omitted from their
  `CanBusLine`, which makes it harder to use them as authoritative end-to-end fixtures.

## Low effort

- Add optional `max_pins` to a disconnect's init

- **Explicit splice/junction DSL** — connections such as
  `power_1 >> power_2` intentionally render as a connector-adjacent splice, but read like a
  pin-to-pin jumper in the spec. Add an explicit helper such as
  `splice(power_1, power_2) >> fuse` (or an equivalent fluent API) that preserves the current
  schematic/BOM topology while making the physical junction and shared feed unambiguous. It
  should support more than two endpoints, conductor-wide modifiers such as gauge/color/system,
  and an optional label; document when to use it instead of a named `SpliceNode`.

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

- **Normalized harness / fabrication model** — introduce one explicit intermediate representation
  after autodetection and disconnect resolution. Wire IDs, physical cable buckets, disconnect
  sides, BOM rows, builder entries, cut lists, and machine-readable exports should consume that
  shared model instead of independently deriving overlapping state from mutable `Harness` objects.

- **Harden spec loading** — give executed specs normal script context (`__file__`, `__name__`, and
  imports relative to the spec directory), clearly document that specs are trusted executable code,
  and report execution errors without burying them behind CLI-only `sys.exit()` behavior.

- **Separate spec loading from side effects** — CLI commands currently load a spec, autodetect the
  harness, and assign wire IDs through one path. Split these into explicit load, normalize, assign,
  and persist steps so read-only commands and tests can exercise each stage independently.

- **Coverage and invariant testing** — publish test coverage in CI and add focused invariants for
  wire-ID uniqueness, BOM/builder/netlist parity, endpoint-direction independence, declaration-order
  independence, class-vs-instance wiring, and isolation of mutable state across component/container
  instances.

- **Split oversized modules** — `bom.py`, `renderers/wires.py`, `renderers/svg.py`,
  `disconnects.py`, and `ports.py` each carry several responsibilities. Break them into smaller
  collector, model, layout, and formatting helpers so future changes have narrower blast radius.

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
  helper types more consistently in bundle/layout APIs. Replace dynamically attached harness state
  such as wire-ID assignments and builder plans with explicit typed fields where practical.

- **Context-local DSL state** — replace the module-global `System` and `Shield` stacks with
  `contextvars.ContextVar` state so concurrent threads/tasks cannot leak active DSL context into one
  another.

## Larger features

- **Interactive SVG** — the sticky headers and remote-pin click-to-jump are already in place.
  Remaining interactivity work, roughly in priority order:

  1. **Expand/collapse connectors** — click a connector header (`sh-conn-` ids are already
     present) to collapse all its pin rows. Useful for large harnesses where you want to focus
     on one connector at a time.

- **Multi-page / off-page split** — for large harnesses, split into logical sections
  (e.g. per sub-system) with `OffPageReference` cross-links between sheets. The model already
  has `OffPageReference`; this is mainly a layout and CLI concern.

- **Pinout/component import helpers** — provide a workflow for creating `Component` classes from
  structured pinout data (CSV/YAML, and eventually extracted PDF tables). This would reduce the
  cost of adding new avionics boxes and make built-in component definitions easier to audit.
