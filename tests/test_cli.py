from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

from loome.bom import build_bom
from loome.cli import _load_harness
from loome.renderers.builder import builder_entries_for_script


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loome.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _write_bundle_spec(tmp_path: Path) -> Path:
    spec = tmp_path / "bundle_spec.py"
    spec.write_text(
        textwrap.dedent(
            """
            from loome import Bundle, Component, Connector, Fuse, GroundSymbol, Harness, Pin


            class Source(Component):
                class J1(Connector):
                    pwr = Pin(1, "Power Out")
                    gnd = Pin(2, "Ground")


            class Load(Component):
                class J1(Connector):
                    pwr = Pin(1, "Power In")
                    gnd = Pin(2, "Ground")


            source = Source("Source")
            load = Load("Load")
            fuse = Fuse("F1", amps=5)
            gnd = GroundSymbol("GND")

            source.J1.pwr >> fuse
            fuse >> load.J1.pwr
            source.J1.gnd >> gnd
            load.J1.gnd >> gnd

            main = Bundle("Main")
            left = main.breakout("left")
            right = main.breakout("right", after=left, length=12)
            left.attach(source.J1, leg_length=2)
            left.attach(fuse, leg_length=1)
            right.attach(load.J1, leg_length=3)
            left.attach(gnd, leg_length=1)

            harness = Harness("CLI Fixture")
            """
        )
    )
    return spec


def _write_invalid_bundle_spec(tmp_path: Path) -> Path:
    spec = tmp_path / "invalid_bundle_spec.py"
    spec.write_text(
        textwrap.dedent(
            """
            from loome import Bundle, Component, Connector, Harness, Pin


            class Box(Component):
                class J1(Connector):
                    sig = Pin(1, "Signal")


            a = Box("A")
            b = Box("B")
            a.J1.sig >> b.J1.sig

            main = Bundle("Main")
            root = main.breakout("root")
            root.attach(a.J1, leg_length=1)

            harness = Harness("Invalid CLI Fixture")
            """
        )
    )
    return spec


def _write_disconnect_spec(tmp_path: Path) -> Path:
    spec = tmp_path / "disconnect_spec.py"
    spec.write_text(
        textwrap.dedent(
            """
            from loome import Component, Connector, Disconnect, DisconnectPin, Fuse, Harness, Pin, SpliceNode


            class Box(Component):
                class J1(Connector):
                    pwr = Pin(1, "Power")
                    aux = Pin(2, "Aux")


            class Mate(Disconnect):
                pwr = DisconnectPin(1, "Power")


            a = Box("A")
            b = Box("B")
            fuse = Fuse("F1", "Main", 5)
            splice = SpliceNode("S1", label="Aux Splice")
            a.J1.pwr >> b.J1.pwr
            a.J1.aux >> splice
            splice >> fuse
            mate = Mate("DC1")
            aux_mate = Mate("DC2")
            mate.pwr.between(a.J1.pwr, b.J1.pwr)
            aux_mate.pwr.between(splice, fuse)

            harness = Harness("Disconnect CLI Fixture")
            """
        )
    )
    return spec


def _write_can_disconnect_spec(tmp_path: Path) -> Path:
    spec = tmp_path / "can_disconnect_spec.py"
    spec.write_text(
        textwrap.dedent(
            """
            from loome import CanBus, CanBusLine, Component, Connector, Disconnect, Harness


            class Node(Component):
                def can_terminate(self):
                    pass

                class J1(Connector):
                    can = CanBus(1, 2)


            a = Node("A")
            b = Node("B")
            bus = CanBusLine("CAN", devices=[a.J1, b.J1])
            mate = Disconnect("DC1")
            mate.between(a.J1.can, b.J1.can)

            harness = Harness("CAN Disconnect CLI Fixture")
            """
        )
    )
    return spec


def test_cli_bom_and_fuses_emit_nonempty_outputs(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)

    bom = _run_cli("bom", str(spec))
    assert bom.returncode == 0, bom.stderr
    assert "# Bill of Materials" in bom.stdout
    assert "F1" in bom.stdout

    fuses = _run_cli("fuses", str(spec))
    assert fuses.returncode == 0, fuses.stderr
    assert "# Fuse / CB Schedule" in fuses.stdout
    assert "F1" in fuses.stdout


def test_cli_bundle_renders_svg(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)
    output = tmp_path / "bundle.svg"

    result = _run_cli("bundle", str(spec), "-o", str(output))

    assert result.returncode == 0, result.stderr
    assert output.exists()
    assert "<svg" in output.read_text()


def test_cli_validate_exits_zero_for_resolved_bundle(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)

    result = _run_cli("validate", str(spec))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_cli_validate_exits_nonzero_for_unresolved_bundle(tmp_path: Path):
    spec = _write_invalid_bundle_spec(tmp_path)

    result = _run_cli("validate", str(spec))

    assert result.returncode == 1
    assert "one end unattached" in result.stderr


def test_cli_render_directory_outputs_one_svg_per_component(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)
    output_dir = tmp_path / "schematics"

    result = _run_cli("render", str(spec), "-o", str(output_dir))

    assert result.returncode == 0, result.stderr
    svgs = sorted(p.name for p in output_dir.glob("*.svg"))
    assert svgs == ["Load.svg", "Source.svg"]


def test_cli_defaults_leave_wire_id_sidecar_untouched(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)

    result = _run_cli("bom", str(spec))

    assert result.returncode == 0, result.stderr
    assert not spec.with_suffix(".wires.yaml").exists()


def test_cli_write_wire_ids_updates_sidecar(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)

    result = _run_cli("bom", str(spec), "--write-wire-ids")

    assert result.returncode == 0, result.stderr
    sidecar = spec.with_suffix(".wires.yaml")
    assert sidecar.exists()
    assert "wires:" in sidecar.read_text()


def test_cli_defaults_use_existing_wire_id_sidecar_without_rewriting(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)
    sidecar = spec.with_suffix(".wires.yaml")
    write_result = _run_cli("bom", str(spec), "--write-wire-ids")
    assert write_result.returncode == 0, write_result.stderr

    data = yaml.safe_load(sidecar.read_text())
    data["wires"][0]["id"] = "CUSTOM01"
    sidecar.write_text(yaml.safe_dump(data, sort_keys=False))
    before = sidecar.read_text()

    result = _run_cli("bom", str(spec))

    assert result.returncode == 0, result.stderr
    assert "CUSTOM01" in result.stdout
    assert sidecar.read_text() == before


def test_cli_check_wire_ids_fails_when_sidecar_would_change(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)

    result = _run_cli("bom", str(spec), "--check-wire-ids")

    assert result.returncode == 1
    assert "wire ID sidecar would change" in result.stderr
    assert not spec.with_suffix(".wires.yaml").exists()


def test_cli_builder_render_directory_outputs_index_and_metadata(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)
    output_dir = tmp_path / "schematics"

    result = _run_cli("render", str(spec), "-o", str(output_dir), "--builder")

    assert result.returncode == 0, result.stderr
    assert (output_dir / "index.html").exists()
    assert not (output_dir / "Load.html").exists()
    assert not (output_dir / "Source.html").exists()
    svg = (output_dir / "Load.svg").read_text()
    html = (output_dir / "index.html").read_text()
    assert "data-seg-id" in svg
    assert "loome-builder-progress" in html
    assert "loome-builder-progress-fill" in html
    assert "loome-builder-export-yaml" in html
    assert "bundle_spec.wires.yaml" in html
    assert "const BUILDER_SINGLE_PAGE = false;" in html
    assert "builder-state.json" not in html
    assert "function exportYaml()" in html
    assert "<svg" in html
    assert "contentDocument" not in html
    assert "<object" not in html
    assert '<select id="loome-builder-component"' in html
    assert '<option value="Load">Load</option>' in html
    assert "--builder-jump-offset:88px" in html
    assert ".component-view{padding-bottom:calc(100vh - var(--builder-toolbar-h) - var(--builder-jump-offset))}" in html
    assert "<nav>" not in html
    assert "event.target.closest('a.pin-link')" in html
    assert "BUILDER_PIN_INDEX" in html
    assert "showComponent(component, targetId, 'push')" in html
    assert "setupStickyHeaders()" in html
    assert "scrollRoot.addEventListener('scroll', updateStickyHeaders" in html
    assert "scrollToTarget(targetId)" in html
    assert "rootBox.top - jumpOffset" in html
    assert "scrollIntoView" not in html
    assert "history.pushState" in html
    assert "popstate" in html
    assert "loome-builder-progress" not in svg
    assert not spec.with_suffix(".wires.yaml").exists()


def test_cli_builder_single_file_dropdown_jumps_to_components(tmp_path: Path):
    spec = _write_bundle_spec(tmp_path)
    output = tmp_path / "full.svg"

    result = _run_cli("render", str(spec), "-o", str(output), "--builder")

    assert result.returncode == 0, result.stderr
    html = (tmp_path / "index.html").read_text()
    assert output.exists()
    assert "const BUILDER_SINGLE_PAGE = true;" in html
    assert '<option value="Source" data-target="sh-comp-' in html
    assert '<option value="Load" data-target="sh-comp-' in html
    assert '<option value="full">' not in html
    assert "view.hidden = !BUILDER_SINGLE_PAGE" in html
    assert "option?.dataset.target" in html
    assert "window.scrollY" not in output.read_text()
    assert "window.scrollY" not in html


def test_cli_builder_splits_disconnect_sides(tmp_path: Path):
    spec = _write_disconnect_spec(tmp_path)
    output_dir = tmp_path / "schematics"

    result = _run_cli("render", str(spec), "-o", str(output_dir), "--builder")

    assert result.returncode == 0, result.stderr
    html = (output_dir / "index.html").read_text()
    assert '"run_key": "' in html
    assert '-a"' in html
    assert '-b"' in html
    assert "return BUILDER_ENTRIES.map(entry => entry.run_key)" in html

    harness = _load_harness(spec, persist_wire_ids=False)
    entry_keys = {entry["run_key"] for entry in builder_entries_for_script(harness)}
    svg_keys = set()
    for svg_path in output_dir.glob("*.svg"):
        svg_keys.update(re.findall(r'data-seg-id="([^"]+)"', svg_path.read_text()))
    assert svg_keys <= entry_keys
    assert any(key.endswith("-a") for key in svg_keys)
    assert any(key.endswith("-b") for key in svg_keys)


def test_cli_builder_uses_split_can_disconnect_keys(tmp_path: Path):
    spec = _write_can_disconnect_spec(tmp_path)
    output_dir = tmp_path / "schematics"

    result = _run_cli("render", str(spec), "-o", str(output_dir), "--builder")

    assert result.returncode == 0, result.stderr
    harness = _load_harness(spec, persist_wire_ids=False)
    can_entries = [entry for entry in builder_entries_for_script(harness) if entry["run_key"].endswith(("-a", "-b"))]
    assert len(can_entries) == 2
    can_keys = {entry["run_key"] for entry in can_entries}
    base_keys = {key.removesuffix("-a").removesuffix("-b") for key in can_keys}

    svg_keys = set()
    for svg_path in output_dir.glob("*.svg"):
        svg_keys.update(re.findall(r'data-seg-id="([^"]+)"', svg_path.read_text()))
    assert can_keys <= svg_keys
    assert svg_keys.isdisjoint(base_keys)


def test_builder_entry_count_matches_bom_rows_for_n14ev_example(repo_root: Path):
    spec = (repo_root / "examples/n14ev/avionics_harness.py").resolve()
    harness = _load_harness(spec, persist_wire_ids=False)

    bom = build_bom(harness)
    entries = builder_entries_for_script(harness)

    assert len(entries) == len(bom.wires) + len(bom.shielded_cables)
    assert len({entry["run_key"] for entry in entries}) == len(entries)
