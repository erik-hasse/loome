# Backlog

Items are roughly in priority order within each section.


## Backlog — switches (remaining)

- **Multi-position switches** — 3-position double-pole (e.g. ignition/fuel pump). Requires
  modeling switch *positions* and which poles connect to which throws per position.

- **Relays / solenoids** — coil + normally-open/normally-closed contacts as separate poles.
  Starter solenoid: momentary coil energization; relay: latching or non-latching.

- **Diodes** — another terminal type. Useful for flyback diodes and blocking diodes on power rails.

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
  (id, gauge, color, length if set), connectors + pin counts, terminals. Wire lengths already
  have a `length_mm` field; total wire by gauge is useful for cut sheets.

## Larger features

- **Full electrical system support** — extend loome beyond harness diagrams to model a
  complete aircraft (or vehicle) electrical system. Key additions:

  - *Wiring topology* — a higher-level graph that describes how subsystems (avionics bus,
    main bus, essential bus, ground bus) interconnect, so the layout engine can place pages
    and route inter-bus wires coherently rather than treating every wire independently.

  - *Rendered switch icons* — visual switch symbols (SPST, SPDT, DPDT, rotary) drawn with
    correct pin labels and connection points, so a switch in the model renders as an
    industry-standard schematic symbol rather than a generic terminal block entry.

  - *Bus bars* — a first-class `BusBar` model element: a named power/ground rail that
    accepts any number of wire taps. Renders as a thick horizontal bar with labeled tap
    points, replacing the current pattern of stubbing many wires to a single `OffPageReference`.

  - *Relay icons* — relay/contactor symbols (coil, NO contact, NC contact) rendered as
    proper schematic symbols with coil-voltage annotation, building on the relay model
    already in the backlog.

  Together these features let loome produce a complete, multi-sheet electrical schematic —
  power distribution, switching logic, and signal wiring — rather than a single harness
  diagram. This is the foundation for aircraft-level electrical documentation.

- **Interactive SVG** — embed hover/highlight via `<script>` tags so hovering a wire highlights
  both endpoints. Click-to-follow for tracing signal paths. No external dependencies needed;
  cleanest path is a `loome render --interactive` flag that injects a small JS block.

- **Multi-page / off-page split** — for large harnesses, split into logical sections
  (e.g. per sub-system) with `OffPageReference` cross-links between sheets. The model already
  has `OffPageReference`; this is mainly a layout and CLI concern.
