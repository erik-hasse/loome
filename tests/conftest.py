import sys
from pathlib import Path

import pytest


@pytest.fixture()
def repo_root() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def python_path(repo_root: Path) -> list[str]:
    sys.path.insert(0, repo_root.as_posix())
