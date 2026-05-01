# Backlog

Items are roughly in priority order within each section.


## Low effort

- **Splice-fan grouping with their direct siblings** — when several pins on a
  connector fan through a shared splice to multiple remotes (e.g. GAD27 J271
  pin 37/38 → splice → Cabin Light + Backlight) and adjacent pins go directly
  to one of those same remotes (pin 39 → Backlight, pin 40 → Cabin Light), the
  direct pins land in their own remote-only clusters and don't sit next to the
  splice-fan rows. Layout would feel tighter if direct-to-X rows were drawn
  into the cluster of any splice-fan that targets X.

- **`PortBuilder.__del__` deferred execution** — `port_a >> port_b` defers `connect()` until
  garbage collection so fluent modifiers (`.ground(False)`, `.drain(local)`) can be chained
  first. The downside is that Python silences exceptions raised inside `__del__`, so direction
  mismatches on ARINC 429 / Ethernet ports fail silently when using `>>`. Better pattern:
  call `connect()` immediately (like `Pin.__rshift__` does) and return a modifier object that
  mutates the already-created segments.

- **Switch schematic symbols** — `SPST`, `SPDT`, `DPST`, `DPDT` all default to
  `render=False` and have no SVG symbol. Adding simple line-art symbols (single-pole
  arc, double-pole arc) would let users put `render=True` and see switch positions in
  the schematic.

- **PDF export** — `cairosvg` converts SVG → PDF in one call; very low effort once SVG output
  is solid.

- **`SDSECU` incomplete pin numbers** — `tach` and `fuel_flow` pins use placeholder numbers
  `"TBD1"` / `"TBD2"`. Look up the actual SDS ECU wiring diagram and replace with real pin
  identifiers.

- **`PortBuilder` missing `.gauge()` / `.color()` modifiers** — `WireBuilder` (returned by
  `pin_a >> pin_b`) supports `.gauge()` and `.color()`, but `PortBuilder` (returned by
  `port_a >> port_b`) does not. Both modifiers should be chainable on port connections too.

- **`BusBar` schematic symbol** — `BusBar` currently renders as a small filled rectangle
  (`primitives.py`). Should instead draw a labeled horizontal bar with tap-point markers,
  matching its role as a shared power rail.

## Medium effort

- **CAN bus rendering** — data-model support is in place: `CanBusLine` captures device
  ordering, `Harness.resolved_length()` returns per-stub lengths for CAN pins, and
  `CanBusLine.stub_lengths_for()` exposes the two-neighbor lengths on intermediate taps.
  What's still missing is the renderer treatment: instead of every can pin stubbing to a
  shared off-page reference, draw a horizontal bus track with each device tapping off it in
  order, plus markers for the terminator devices at either end. layout is the bulk of the
  remaining work; the renderer already has all the length data it needs.

- **Shielded cable BoM entries** — shielded wire groups should appear as a single
  cable entry rather than N individual wire rows. Each `ShieldGroup` in
  `harness.shield_groups` corresponds to one physical cable; the conductors are the
  segments in `sg.segments` (connection-level) or via `p._connections` for each `p`
  in `sg.pins` (class-body). Implementation sketch:
  - Add `BomShieldedRow(shield_id, conductors, gauge, length, from_label, to_label)`
    where `conductors` = number of segments, `gauge` is the dominant gauge (or
    "mixed"), and from/to come from the first segment's endpoints.
  - Collect all segment ids covered by any shield group; exclude those from the
    individual wire list in `build_bom()`.
  - Add a "Shielded cables" section to both MD and CSV renderers.
  - Skip shield groups with `single_oval=True` (CAN bus topology markers, not
    discrete cables) and groups with zero connected segments.
  - For class-body shields (RS232, GPIO etc.) group by component instance so each
    device-pair connection becomes its own cable row.

- Support multi-pin on the right hand side (e.g. GTR20 -> GMA245))

- **FuseBlock / CB-bank topology rendering** — the `FuseBlock` and `CircuitBreakerBank`
  data types exist and are consumed by the fuse schedule, but the bundle-layout view
  still attaches each `Fuse` / `CircuitBreaker` individually. Teach `renderers/bundle.py`
  to attach a block or bank to a breakout as a single unit and draw the member fuses/CBs
  inside it, respecting `positions`. Groups that aren't attached fall back to the current
  per-fuse behavior.

## Test coverage

- **Port type tests** — no tests cover `RS232.connect`, `ARINC429.connect`, `GPIO.connect`,
  `Thermocouple.connect`, or `GarminEthernet.connect`. Should verify pin injection,
  cross-wiring, and direction validation.

- **`PortBuilder.__del__` silent-failure test** — the known bug where direction mismatches on
  `ARINC429`/`GarminEthernet` port connections swallow exceptions is untested. A test that
  asserts the exception is eventually surfaced will also drive fixing the underlying `__del__`
  pattern.

- **Shield / `ShieldGroup` context manager** — no tests for `Shield` as a context manager,
  for `ShieldGroup.pins` population, or for `cable_only` / `single_oval` flags.

- **`FuseBlock` declarative subclass** — no tests for the class-body fuse-declaration style
  or `CircuitBreakerBank`.

- **CLI subcommand tests** — `bundle`, `bom`, and `fuses` subcommands have no CLI-level tests.
  At minimum, confirm each exits 0 and produces non-empty output on the fixture spec.
  `loome validate` (newly added) also needs both passing and failing cases.

- **`WireBuilder` fluent API** — `.gauge()`, `.color()`, `.wire_id()`, `.notes()` are
  untested; verify they mutate the underlying `WireSegment` correctly.

- **Layout ordering rules** — `layout/ordering.py` has no tests; the sort-key functions are
  load-bearing for schematic readability.

## Larger features

- **Interactive SVG** — the sticky headers and remote-pin click-to-jump are already in place.
  Remaining interactivity work, roughly in priority order:

  1. **Cross-component navigation** — a `loome render-all` (or `--all`) command that renders
     every component to its own SVG plus an `index.html` linking them. Each per-component SVG
     gets a fixed top bar listing all components as links (back/forward navigation). This is a
     prerequisite for builder mode to be useful across a real harness.

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

  3. **Expand/collapse connectors** — click a connector header (`sh-conn-` ids are already
     present) to collapse all its pin rows. Useful for large harnesses where you want to focus
     on one connector at a time.

- **Multi-page / off-page split** — for large harnesses, split into logical sections
  (e.g. per sub-system) with `OffPageReference` cross-links between sheets. The model already
  has `OffPageReference`; this is mainly a layout and CLI concern.
