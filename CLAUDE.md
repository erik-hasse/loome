# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses **uv** and requires Python ≥ 3.13.

- Install dev deps: `uv sync`
- Run the CLI: `uv run loome <subcommand> <spec.py>` (subcommands: `render`, `bundle`, `bom`, `fuses`, `validate`)
- Run all tests: `uv run pytest`
- Run a single test: `uv run pytest tests/test_bom.py::test_name -xvs`
- Lint / format: `uv run ruff check --fix` and `uv run ruff format` (line length 120; rules in `pyproject.toml`)
- Pre-commit: `uv run pre-commit run -a` (runs ruff, end-of-file-fixer, `uv lock --check`)

## Architecture

Loome is a Python library + CLI that turns a Python "spec file" describing a wiring harness into rendered SVGs and tabular outputs (BOM, fuse schedules). The spec file is a regular `.py` module that the CLI `exec()`s; it must assign a `Harness` instance to a module-level variable named `harness`.

### Pipeline (CLI → output)

1. **Spec load** (`cli.py::_load_harness`) — `exec()`s the spec into a fresh namespace, retrieves `harness`, then calls `harness.autodetect(namespace)` to walk the namespace and collect every `Component`, `SpliceNode`, `Terminal`, `Shield`, `Bundle`, `CanBusLine`, `FuseBlock`, `CircuitBreakerBank`, and `Disconnect` defined there. Wire endpoints reachable through `>>` / `.connect()` are also followed so unnamed terminals get registered.
2. **Layout** (`layout/engine.py::layout`) — places components, computes pin positions, orders connectors, routes wires. `layout/bundle_layout.py` handles the physical bundle topology (separate from schematic layout).
3. **Render** — `renderers/svg.py` (schematic) and `renderers/bundle.py` (bundle tree) consume the layout result and emit SVG via `drawsvg`. `renderers/wires.py`, `splices.py`, `primitives.py`, `colors.py` are shared drawing helpers.
4. **Tabular outputs** — `bom.py` builds and renders BOM and fuse schedules in markdown or CSV.

### Core domain model (`model.py`)

The user-facing DSL lives here:

- `Component` is subclassed by users; inner classes subclass `Connector`; pins are class attributes `Pin(number, signal_name)`. Component metaclass machinery turns the inner connector classes into per-instance `Connector` objects so each component instance has its own pin objects.
- Wire connection is via `pin_a >> pin_b` (returns a `WireBuilder` for chaining `.gauge().color().wire_id().notes()`) or `pin_a.connect(pin_b, ...)` (returns a `WireSegment` directly). Both produce `WireSegment` objects stored on the pins/terminals; `Harness.segments()` deduplicates across class-level and instance-level connections.
- `Terminal` subclasses (`GroundSymbol`, `OffPageReference`, `Fuse`, `CircuitBreaker`, `BusBar`, `SpliceNode`) are wire endpoints. `FuseBlock` / `CircuitBreakerBank` are containers; the declarative subclass pattern (class attributes are the contained `Fuse`s) is preferred.
- `Shield` is a context manager that groups all wire connections made inside its `with` block into one `ShieldGroup` foil.

### Composite ports (`ports.py`)

`CanBus`, `RS232`, `GPIO`, `ARINC429`, `Thermocouple`, `GarminEthernet` are pre-built multi-pin port descriptors that auto-wire shared bus lines. They live on `Connector` classes the same way `Pin` does and expose a `.connect()` that cross-wires (e.g. TX↔RX for `RS232`).

### Bundles (`bundles.py`, `buses.py`)

`Bundle` describes the physical topology of a wire run: a tree of `Breakout` nodes joined by trunk segments with lengths. `Breakout.attach(connector_or_terminal, leg_length=...)` declares a stub. From this loome computes per-wire physical lengths used in the BOM. `CanBusLine` describes an ordered daisy-chained CAN segment for layout.

### Built-in components (`components/`)

`components/garmin.py` (G3X / GTN ecosystem), `components/gtn650.py`, `components/switches.py` (`SPST`/`SPDT`/`DPST`/`DPDT`), and miscellaneous parts (`RayAllanTrim`, `Stick`, `LEMO`, `TRS`) in `components/__init__.py`. These are normal `Component` subclasses — the same DSL users write.

### Disconnects (`disconnects.py`)

In-line connector pairs that split a wire run; `Disconnect` / `DisconnectPin` integrate with both the schematic layout and bundle length math.

## Testing

Tests live in `tests/`. The most fragile is `test_schematic_golden.py`, which invokes the `loome` CLI on `tests/fixtures/schematic_spec.py` and byte-compares the output to `tests/fixtures/schematic_golden.svg`. Any rendering change will trip this — regenerate the fixture by running:

```
uv run loome render tests/fixtures/schematic_spec.py -o tests/fixtures/schematic_golden.svg
```

only when the change is intentional, and inspect the diff before committing.
