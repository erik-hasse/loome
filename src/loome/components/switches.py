from __future__ import annotations

from loome.model import Component, Pin


class SPST(Component):
    render = False
    com = Pin(1, "COM")
    no = Pin(2, "NO")

    def __init__(self, label: str | None = None, *, momentary: bool = False, render: bool = False):
        super().__init__(label, render=render)
        self.momentary = momentary


class SPDT(Component):
    render = False
    com = Pin(1, "COM")
    no = Pin(2, "NO")
    nc = Pin(3, "NC")

    def __init__(self, label: str | None = None, *, momentary: bool = False, render: bool = False):
        super().__init__(label, render=render)
        self.momentary = momentary


class DPST(Component):
    render = False
    com1 = Pin(1, "COM 1")
    no1 = Pin(2, "NO 1")
    com2 = Pin(3, "COM 2")
    no2 = Pin(4, "NO 2")

    def __init__(self, label: str | None = None, *, momentary: bool = False, render: bool = False):
        super().__init__(label, render=render)
        self.momentary = momentary


class DPDT(Component):
    render = False
    com1 = Pin(1, "COM 1")
    no1 = Pin(2, "NO 1")
    nc1 = Pin(3, "NC 1")
    com2 = Pin(4, "COM 2")
    no2 = Pin(5, "NO 2")
    nc2 = Pin(6, "NC 2")

    def __init__(self, label: str | None = None, *, momentary: bool = False, render: bool = False):
        super().__init__(label, render=render)
        self.momentary = momentary


class Rheostat(Component):
    render = False
    ground = Pin("BLK", "Ground")
    power = Pin("RED", "Power")
    out = Pin("BLU", "Out")


class OnOffOnSwitch(Component):
    render = False

    com = Pin(1, "COM")
    up = Pin(2, "UP")
    down = Pin(3, "DOWN")

    def __init__(
        self,
        label: str | None = None,
        *,
        momentary_up: bool = False,
        momentary_down: bool = False,
        render: bool = False,
    ):
        super().__init__(label, render=render)
        self.momentary_up = momentary_up
        self.momentary_down = momentary_down


class DPOnOnOnSwitch(Component):
    """The first position switches com1 from nc1 to no1, the second position switches
    com2 from nc2 to no2 (keeping com1-no1 connected).

    Honeywell 2TL1-10, Carling 2-10, or similar
    """

    render = False

    def __init__(self, label: str | None = None, *, labels: tuple[str, str, str] | None = None, render: bool = False):
        super().__init__(label, render=render)
        self.labels = labels

    nc2 = Pin(1, "NC2")
    no2 = Pin(3, "NO2")
    com2 = Pin(2, "COM2")

    nc1 = Pin(4, "NC1")
    com1 = Pin(5, "COM1")
    no1 = Pin(6, "NO1")
