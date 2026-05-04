from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


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
