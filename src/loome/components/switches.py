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
