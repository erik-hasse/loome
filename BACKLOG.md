# Backlog

Items are roughly in priority order within each section.


## Low effort

- **`PortBuilder.__del__` deferred execution** — `port_a >> port_b` defers `connect()` until
  garbage collection so fluent modifiers (`.ground(False)`, `.drain(local)`) can be chained
  first. The downside is that Python silences exceptions raised inside `__del__`, so direction
  mismatches on ARINC 429 / Ethernet ports fail silently when using `>>`. Better pattern:
  call `connect()` immediately (like `Pin.__rshift__` does) and return a modifier object that
  mutates the already-created segments.

- **Ground Rendering** - The triangles for ground (both local and chassis) render strangely and
  should be cleaned up.

- **PDF export** — `cairosvg` converts SVG → PDF in one call; very low effort once SVG output
  is solid.

- **`loome validate` command** — dedicated CLI entry that runs `Harness.validate_bundles()`
  and exits non-zero on warnings, for CI use without also rendering SVG.

## Medium effort

- Support multi-pin on the right hand side (e.g. GTR20 -> GMA245))

- **CAN bus rendering** — data-model support is in place: `CanBusLine` captures device
  ordering, `Harness.resolved_length()` returns per-stub lengths for CAN pins, and
  `CanBusLine.stub_lengths_for()` exposes the two-neighbor lengths on intermediate taps.
  What's still missing is the renderer treatment: instead of every can pin stubbing to a
  shared off-page reference, draw a horizontal bus track with each device tapping off it in
  order, plus markers for the terminator devices at either end. layout is the bulk of the
  remaining work; the renderer already has all the length data it needs.

- **automatic can termination** — add a `connector.can_terminate()` instance method that
  `canbusline` calls on its first and last device. two flavors a device can implement:

  1. *in-connector jumper* — short two dedicated terminator pins together (e.g. the
     `can_term_1`/`can_term_2` pins on `_basej281`, or `can_bus_term` on the gdu). just
     emits an internal wire segment; the existing renderer already handles same-connector
     jumpers.
  2. *termination adapter* — splice in a pass-through connector that exposes h/l on both
     sides with a 120ω resistor between them. needs a new adapter-style `component` that
     renders inline on the bus and carries a "120ω h↔l" note on its symbol.

- **FuseBlock / CB-bank topology rendering** — the `FuseBlock` and `CircuitBreakerBank`
  data types exist and are consumed by the fuse schedule, but the bundle-layout view
  still attaches each `Fuse` / `CircuitBreaker` individually. Teach `renderers/bundle.py`
  to attach a block or bank to a breakout as a single unit and draw the member fuses/CBs
  inside it, respecting `positions`. Groups that aren't attached fall back to the current
  per-fuse behavior.

## Larger features

- **Interactive SVG** — embed hover/highlight via `<script>` tags so hovering a wire highlights
  both endpoints. Click-to-follow for tracing signal paths. No external dependencies needed;
  cleanest path is a `loome render --interactive` flag that injects a small JS block.

- **Multi-page / off-page split** — for large harnesses, split into logical sections
  (e.g. per sub-system) with `OffPageReference` cross-links between sheets. The model already
  has `OffPageReference`; this is mainly a layout and CLI concern.
