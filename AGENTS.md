# AGENTS.md

This file provides guidance to LLM agents working in this repository.

## Project Snapshot

Loome is a Python library and CLI for describing aircraft wiring harnesses in plain Python. A spec file defines
components, pins, terminals, wires, shields, disconnects, CAN buses, and optional bundle topology; the CLI executes
the spec, expects a module-level `harness: Harness`, then renders SVG schematics, bundle diagrams, BOMs, fuse
schedules, or validation output.

The package is source-layout under `src/loome`. Public API re-exports live in `src/loome/__init__.py`. User-facing
documentation is in `README.md`; realistic usage is in `examples/minimal.py` and `examples/n14ev/`; known gaps and
accepted future work are in `BACKLOG.md`. `manuals/` contains local, gitignored reference PDFs when present, useful for
avionics pinout work but not something to commit.

## Commands

This project uses `uv` and requires Python >= 3.13.

- Install dev deps: `uv sync`
- Run the CLI: `uv run loome <subcommand> <spec.py>`
- CLI subcommands: `render`, `bundle`, `bom`, `fuses`, `validate`
- Run all tests: `uv run pytest`
- Run one test: `uv run pytest tests/test_bom.py::test_name -xvs`
- Lint and format: `uv run ruff check --fix` and `uv run ruff format`
- Pre-commit: `uv run pre-commit run -a`

`pyproject.toml` sets Ruff line length to 120 and lint rules `E`, `W`, `F`, `PL`, `I`, ignoring `PLR`. Pre-commit runs
YAML checks, EOF/trailing whitespace fixes, Ruff format/check, and `uv lock --check`.

## CLI Pipeline And Side Effects

All CLI commands load specs through `cli.py::_load_harness`:

1. `exec()` the spec into a fresh namespace.
2. Retrieve `harness`; exit with an error if missing.
3. Call `harness.autodetect(namespace)`.
4. Call `assign_wire_ids(harness, spec_path)`.

Important: `assign_wire_ids()` reads and writes `<spec>.wires.yaml` for every CLI command, including `bom`, `fuses`,
`bundle`, `validate`, and `render`. This is intentional today. When running commands against fixtures or examples,
inspect sidecar diffs before keeping them. For tests or scratch code that should not mutate a sidecar, call
`assign_wire_ids(harness, None)` or put temporary specs under a temp directory.

`render -o <directory>` creates one SVG per rendered component using sanitized component labels. `render -o <file>`
creates a whole-harness SVG. Full schematic SVGs get the sticky-header JavaScript injected; per-component SVGs do not.

`validate` currently reports bundle-topology warnings only and exits non-zero if any warning is produced. Broader
semantic validation is backlog work.

## Architecture Map

- `model.py`: user DSL core: `Component`, `Connector`, `Pin`, `WireSegment`, `Terminal` subclasses, fuse/CB containers,
  `SpliceNode`, `Shield`, `ShieldGroup`, `System`.
- `ports.py`: composite port descriptors (`CanBus`, `RS232`, `GPIO`, `ARINC429`, `GarminEthernet`, `Thermocouple`) and
  `PortBuilder`.
- `harness.py`: object registration, namespace autodetection, segment collection, bundle length resolution, bundle
  validation.
- `wire_ids.py`: stable wire ID assignment and `<spec>.wires.yaml` persistence.
- `bundles.py`, `buses.py`, `disconnects.py`: physical topology, CAN bus ordering, inline connector metadata.
- `layout/engine.py`: schematic row/section layout. `layout/ordering.py` is the source of truth for pin and leg order.
  `layout/bundle_layout.py` lays out bundle topology diagrams.
- `renderers/svg.py`, `renderers/wires.py`, `renderers/splices.py`, `renderers/primitives.py`, `renderers/context.py`,
  `renderers/colors.py`: schematic rendering. `renderers/bundle.py` renders bundle trees.
- `bom.py`: pure-data collectors and markdown/CSV renderers for BOM and fuse schedules. It should not import SVG
  rendering.
- `_internal/endpoints.py`, `_internal/shields.py`, `_internal/systems.py`, `_internal/attachments.py`,
  `_internal/names.py`: shared helper layer for labels, fingerprints, shield ownership, system resolution, attachment
  target typing, and default signal naming.
- `components/`: built-in component definitions. Garmin-heavy definitions are normal `Component` subclasses and should
  follow the same DSL rules as user specs.

## Core Domain Invariants

`Component` subclasses may define direct `Pin` attributes and inner `Connector` subclasses. `Connector` subclasses
define `Pin` class attributes. Component/connector initialization copies class pins to per-instance pins and annotates
metadata (`_attr_name`, `_component_class`, `_connector_class`, `_component`, `_connector`). Preserve this copy-and-tag
behavior when touching `Component`, `Connector`, `Pin`, or port descriptors.

Class-level wiring is a supported feature. A connection like `Widget.J1.power.connect(splice)` applies to every
instance unless an instance-level pin has its own connections. `Harness.segments()` intentionally lets instance-level
connections override class-level connections for the same pin.

`WireEndpoint` is `Pin | SpliceNode | Terminal`. Terminals include `GroundSymbol`, `OffPageReference`, `Fuse`,
`CircuitBreaker`, `BusBar`, and internal `ShieldDrainTerminal`. Terminal-to-terminal connections are supported by the
model, autodetection, BOM, and fuse schedule, but schematic rendering for terminal-only chains is still a known backlog
gap.

`pin_a >> pin_b` immediately creates a `WireSegment` and returns a `WireBuilder` that mutates that segment. `.connect()`
returns the `WireSegment` directly. Port `>>` also connects immediately and returns a `PortBuilder` that mutates all
segments created by the port connection.

`Pin.local_ground()` creates an open local `GroundSymbol` and a local segment that is deliberately skipped by wire ID and
BOM logic. `ShieldDrainTerminal` stubs are also layout-only/local.

`WireSegment.effective_color` is the shared defaulting rule: explicit color wins, fuse/CB endpoints default red,
ground endpoints default black, everything else defaults white. Keep BOM and renderers using this shared behavior.

## Systems And Wire IDs

System resolution order is:

1. Explicit per-segment system (`.system(...)` or `connect(system=...)`), including values captured from `with System(...)`.
2. Component instance system (`Component(..., system="ENG")` or class attribute `system = "ENG"`) on the first endpoint
   that has one.
3. `harness.default_system`.

`System(code)` validates 1-4 alphanumeric/underscore characters. If `harness.default_system is None`, every non-local
wire or shielded cable must resolve a system or `assign_wire_ids()` raises.

Wire IDs are assigned in `wire_ids.py` with stable fingerprints from `_internal/endpoints.py`. Normal IDs are
`<system><gauge><color><nn>`; shielded cables use `SH`; disconnect-split BOM rows add `A`/`B` suffixes. The sidecar keeps
orphaned old IDs so renamed endpoints can be recovered manually. A non-empty `Shield(label=...)` is treated as an
explicit cable ID override.

In tests, build the harness, call `h.autodetect(ns)` if needed, then call `assign_wire_ids(h, None)` before asserting
specific IDs or BOM rows.

## Shields And Ports

Shield membership is stored in two model-level forms, but downstream code should treat that as an implementation detail:

- Connection-level `with Shield(...)`: `_active_shield_stack` assigns `seg.shield_group`, marks segments shielded, and
  appends them to `ShieldGroup.segments`.
- Port/class-body shields: pins carry `pin.shield_group`; segments store endpoint-side ownership in
  `end_a_shield_group` and `end_b_shield_group`.

Use `_internal/shields.py` helpers (`segment_shield_groups`, `segment_shield_for_endpoint`, `segment_source_shield_group`,
`segments_for_shield`) instead of ad hoc checks when adding BOM, layout, rendering, or ID logic. For schematic shield
ovals specifically, route both storage forms through the SVG shield-oval plan instead of branching in the draw pass.

Shield drains accept `"block"`, `"ground"`, `None`, or an explicit pin/endpoint. Pin drains create a `ShieldDrainTerminal`
stub and set `_drain_for` so ordering and rendering can keep the drain row with the shield.

Ports are descriptors. `Port.__set_name__` injects inner pins onto the owner as `<port>_<pin_attr>`, and `Port.__get__`
returns a bound copy for each component/connector instance. If adding a port, set `_pin_attrs`, create the inner `Pin`s,
and preserve bound shield group behavior.

Port-specific behavior to preserve:

- `CanBus` auto-connects high/low pins to a shared `OffPageReference`, uses `single_oval=True`, and is hidden from layout
  unless a `CanBusLine` covers the connector.
- `CanBusLine` should be assigned to a variable or passed explicitly to `Harness(..., can_buses=[...])`; an unbound
  bare constructor call will not be autodetected. It marks first/last devices as terminated by calling the owning
  component's `can_terminate()` method.
- `RS232` cross-wires TX to RX and RX to TX, with optional ground. `PortBuilder.ground(False)` removes the ground
  segment. `PortBuilder.notes()` currently annotates only the primary segment; this is a documented backlog concern.
- `ARINC429` and `GarminEthernet` require one `"out"` and one `"in"` port.
- `Thermocouple` creates a `cable_only` shield group, defaults to 20 AWG, and wires high yellow / low red. It appears as
  a cable row without shield ovals.

## Bundles And Lengths

A `Bundle` is a tree of `Breakout` nodes. `breakout(id)` creates the single root; subsequent breakouts must pass
`after=<parent>` and may set `length=<trunk distance>`. `Breakout.attach(target, leg_length=...)` attaches a
`Connector`, `Component`, `Terminal`, `SpliceNode`, or `Disconnect` to the breakout.

`Harness.autodetect()` freezes bundles. `Bundle.attachment_for()` requires a frozen bundle and rejects double-attached
targets within the same bundle. Class-level pins can resolve through a uniquely attached instance of their connector or
component class; if there are zero or multiple candidates, length resolution returns `None`.

`Harness.resolved_length(seg)` returns leg + trunk + leg for endpoints in the same bundle, CAN stub length for CAN pins,
or the sum of both sides for a non-CAN disconnect. `Harness.resolved_sides(seg)` returns per-side lengths for disconnects.
`Harness.format_wire_length(seg)` handles CAN neighbor lengths and disconnect side display.

Wires with both ends unattached are ignored by `validate_bundles()`; one attached end, different bundles, missing
disconnect attachment, unattached CAN devices, and CAN-capable connectors omitted from a `CanBusLine` produce warnings.

## Disconnects

`Disconnect` describes inline connector metadata attached to already-declared wires; it does not add extra
`WireSegment`s for ordinary wires. `Disconnect.between(...)` can be declared before the wire exists because resolution is
lazy. `Harness.segments()` and schematic `layout()` call `disc.resolve(harness)`.

Supported bindings:

- Pin/splice/terminal endpoint pair: one disconnect pin.
- Same-type port pair: one disconnect pin per inner conductor.
- CAN port pair: two pins (H/L) and only for adjacent devices on a registered `CanBusLine`.

Shielded port disconnects and fully covered standalone `Shield(...)` groups auto-allocate one shield-drain pin. Partial
coverage of a standalone shield raises because it is physically inconsistent; use `between_shield()` for explicit
overrides.

BOM output lists disconnect pin rows. Ordinary disconnect-split wires become `IDA` and `IDB` rows. CAN disconnects split
the adjacent CAN cable into side A/B cable rows while disconnect pin rows reference the base cable ID.

## Layout And Rendering Notes

`layout/ordering.py` is where pin ordering and multi-leg ordering rules live. Change that file before changing renderer
draw order. Shield grouping, remote-target clustering, self-jumper pairing, and terminal-first leg ordering are all
centralized there.

`layout/engine.py` computes `LayoutResult` rows, section rects, connector rects, dynamic pin-name/remote-box widths, and
continuation rows for multi-direct pins. It skips components with `render=False`, skips unconnected pins unless
`--show-unconnected` is set, and hides orphan CAN pins.

Renderers should consume `LayoutResult` and `RenderContext`; avoid rebuilding row/segment/shield indexes inline. The
SVG renderer normalizes shield rows into a shield-oval plan before drawing ovals/drains, then has separate passes for
rows, shield ovals/drains, jumper bars, bullets, remote boxes, and CAN TERM boxes.
Changes to geometry often affect `tests/fixtures/schematic_golden.svg`.

Known rendering gaps from `BACKLOG.md`: terminal-to-terminal schematic wires, proper bus-bar symbol, switch symbols when
`render=True`, CAN bus track rendering, fuse-block/CB-bank bundle rendering, and broader interactive SVG features.

## BOM And Fuse Schedule Notes

`bom.py` has no SVG dependency. `trace_loads()` starts at a `Fuse` or `CircuitBreaker`, walks through splices and
busbars, and records protected loads. `build_fuse_schedule()` uses block/bank placement for locations.

`build_bom()` produces combined wire/cable rows, gauge totals for unshielded wires, system totals for wires and cables,
connectors, terminals, and disconnect sections. CAN bus plumbing and `single_oval` shield segments are excluded from
ordinary wire rows and represented as adjacent-pair shielded cable rows instead.

If a code path expects final wire IDs, ensure `assign_wire_ids()` has run first. The CLI does this automatically; unit
tests often use helpers that call `assign_wire_ids(h, None)`.

## Examples And Docs

`README.md` is the public DSL reference. Update it when adding public APIs, CLI flags, port types, or user-visible
semantics. Add new top-level exports to `src/loome/__init__.py` and `__all__`.

`examples/minimal.py` mirrors the README quick start. `examples/n14ev/avionics_harness.py` is the best complex spec
reference for systems, shields, ports, disconnects, fuses, local grounds, and CAN bus ordering. It explicitly passes
many objects into `Harness(...)` and sets `default_system=None`, so missing `System(...)` coverage surfaces quickly.

Generated SVGs are ignored by `.gitignore`, except already tracked fixtures/examples. Do not add generated render output
unless it is an intentional fixture or documentation asset.

## Testing Map

- `tests/test_model` does not exist; model behavior is covered across the suite.
- `tests/test_wire_ids.py`: systems, stable sidecar IDs, shield IDs, CAN pair IDs, fingerprints.
- `tests/test_bom.py`: fuse tracing, fuse/CB blocks, terminal-to-terminal autodetect, shielded cable rows, CAN BOM rows,
  CSV/markdown parsing.
- `tests/test_ports.py`: port descriptor binding, cross-wiring, modifiers, drains, direction checks.
- `tests/test_bundles.py` and `tests/test_length_derivation.py`: bundle tree constraints, attachment lookup, resolved
  lengths, validation warnings.
- `tests/test_can_bus_line.py`: CAN trunk/stub length and validation warnings.
- `tests/test_disconnects.py`: lazy resolution, port/CAN disconnects, shield drain pins, BOM disconnect rows.
- `tests/test_layout_ordering.py`: fragile row ordering and shield grouping rules.
- `tests/test_renderer_context.py`: shared render indexes, shield lookup, and shield-oval planning.
- `tests/test_cli.py`: subprocess CLI behavior and directory render output.
- `tests/test_schematic_golden.py`: byte-level SVG golden check.

The most fragile test is `test_schematic_golden.py`. It runs:

```bash
uv run loome render tests/fixtures/schematic_spec.py -o tests/fixtures/schematic_golden.svg
```

Regenerate `tests/fixtures/schematic_golden.svg` only for intentional rendering changes, then inspect both the SVG and
diff. This command can also touch `tests/fixtures/schematic_spec.wires.yaml` through CLI wire-ID persistence.

## Coding Guidance

Prefer established DSL patterns over new abstractions. Keep user-facing APIs simple Python objects and fluent operators.
If adding a new public concept, add focused tests, top-level exports, and README coverage.

Use shared internal helpers for endpoint labels/fingerprints, shield membership, system resolution, attachment target
descriptions, and default signal names. These helpers exist to keep BOM, wire IDs, layout, rendering, and diagnostics
consistent.

Be careful with side effects:

- `exec()`ing a spec can run arbitrary user code.
- `Harness.autodetect()` mutates the harness and freezes bundles.
- `Harness.segments()` resolves disconnects.
- CLI loading mutates wire ID sidecars.

For renderer changes, run the smallest relevant layout/renderer tests first, then the golden test. For bundle or length
changes, include validation tests. For wire IDs or BOM changes, include sidecar and CSV/markdown tests. For public DSL
changes, include at least one spec-like integration test using `Harness.autodetect()`.
