from __future__ import annotations

from typing import TypeAlias

from ..disconnects import Disconnect
from ..model import Component, Connector, SpliceNode, Terminal

AttachmentTarget: TypeAlias = Connector | Component | Terminal | SpliceNode | Disconnect


def describe_attachment_target(target: AttachmentTarget) -> str:
    if isinstance(target, Component):
        return target.label
    if isinstance(target, Connector):
        comp = getattr(target, "_component", None)
        name = type(target)._connector_name or ""
        if isinstance(comp, Component):
            return f"{comp.label}.{name}" if name else comp.label
        return name or type(target).__name__
    if isinstance(target, Terminal):
        return target.display_name()
    if isinstance(target, SpliceNode):
        return target.label or target.id
    if isinstance(target, Disconnect):
        return target.display_name()
    return repr(target)
