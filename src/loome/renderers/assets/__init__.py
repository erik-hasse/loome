from __future__ import annotations

from importlib.resources import files

_ASSET_PACKAGE = "loome.renderers.assets"


def asset_text(name: str) -> str:
    return files(_ASSET_PACKAGE).joinpath(name).read_text(encoding="utf-8")
