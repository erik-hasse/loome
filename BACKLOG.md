# Backlog

Items are roughly in priority order within each section.


## Low effort

- **Wire-crossing jumper ordering** — when a pin fans out to two targets and one of them
  is a ground symbol, the jumper bar can hop over the ground stub or over the other leg
  depending on connection order, and both orderings look awkward (see TO/GA COM1 example).
  The layout engine should order fan-out legs so that short stubs (ground symbols, off-page
  refs) are placed last, minimising the height of the jumper bar that other legs must cross.

- **Ground Rendering** - The triangles for ground (both local and chassis) render strangely and
  should be cleaned up.

- **`PortBuilder.__del__` deferred execution** — `port_a >> port_b` defers `connect()` until
  garbage collection so fluent modifiers (`.ground(False)`, `.drain(local)`) can be chained
  first. The downside is that Python silences exceptions raised inside `__del__`, so direction
  mismatches on ARINC 429 / Ethernet ports fail silently when using `>>`. Better pattern:
  call `connect()` immediately (like `Pin.__rshift__` does) and return a modifier object that
  mutates the already-created segments.

- **PDF export** — `cairosvg` converts SVG → PDF in one call; very low effort once SVG output
  is solid.

- **`loome validate` command** — dedicated CLI entry that runs `Harness.validate_bundles()`
  and exits non-zero on warnings, for CI use without also rendering SVG.

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

## Larger features

- **Interactive SVG** — embed hover/highlight via `<script>` tags so hovering a wire highlights
  both endpoints. Click-to-follow for tracing signal paths. No external dependencies needed;
  cleanest path is a `loome render --interactive` flag that injects a small JS block.

- **Multi-page / off-page split** — for large harnesses, split into logical sections
  (e.g. per sub-system) with `OffPageReference` cross-links between sheets. The model already
  has `OffPageReference`; this is mainly a layout and CLI concern.
