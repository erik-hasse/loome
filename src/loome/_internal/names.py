from __future__ import annotations


def default_signal_name(attr_name: str) -> str:
    return attr_name.replace("_", " ").title()
