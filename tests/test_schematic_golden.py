from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_schematic_output_matches_golden(tmp_path):
    spec = FIXTURES / "schematic_spec.py"
    golden = FIXTURES / "schematic_golden.svg"
    out = tmp_path / "out.svg"
    subprocess.run(
        [sys.executable, "-m", "loome.cli", "render", str(spec), "-o", str(out)],
        check=True,
        capture_output=True,
    )
    assert out.read_bytes().rstrip() == golden.read_bytes().rstrip(), (
        "schematic output drifted from golden fixture; run `loome render` "
        "against tests/fixtures/schematic_spec.py and update the fixture if "
        "the change is intentional"
    )
