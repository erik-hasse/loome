"""Composite ports — bundles of Pins plus a ``connect()`` protocol.

A Port lives on a ``Connector`` or ``Component`` class body as a descriptor:

    class MyDevice(Component):
        class J1(Connector):
            can = CanBus(1, 2)

Each Port owns a set of named inner ``Pin`` objects (e.g. ``high``/``low`` for
``CanBus``, ``tx``/``rx``/``gnd`` for ``RS232``). The :class:`Port` base class
handles the descriptor boilerplate (``__set_name__`` / ``__get__``) that
injects those pins into the owning class and binds them to the correct
instance at access time. Subclasses just declare ``_pin_attrs`` and implement
port-specific wiring logic.

Adding a new composite port means subclassing :class:`Port`, listing its
``_pin_attrs``, and implementing ``__init__`` to construct the inner pins —
the descriptor plumbing is inherited.
"""

from __future__ import annotations

from .model import GroundSymbol, OffPageReference, Pin, ShieldGroup

_CAN_DRAIN = GroundSymbol("_can_shield_drain_", "GND")


class Port:
    """Descriptor base for composite-pin ports.

    Subclasses must:
      * list the pin-attribute names in ``_pin_attrs`` (tuple of strings,
        corresponding to ``self._<name>`` attributes set by ``__init__``).
      * create those inner Pin objects in ``__init__``.

    The base class handles injecting inner pins onto the owning class at
    ``__set_name__`` time (as ``<port_name>_<pin_attr>``) and returning a
    bound copy at instance access time so connections resolve to the right
    instance rather than the class-level template.
    """

    _pin_attrs: tuple[str, ...] = ()

    def __init__(self) -> None:
        self._attr_name: str = ""

    def _inner_pins(self) -> list[Pin]:
        return [p for p in (getattr(self, f"_{n}", None) for n in self._pin_attrs) if isinstance(p, Pin)]

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        for pin_name in self._pin_attrs:
            pin = getattr(self, f"_{pin_name}", None)
            if pin is not None:
                setattr(owner, f"{name}_{pin_name}", pin)

    def __get__(self, obj: object | None, objtype: type | None = None):
        if obj is None:
            return self
        bound = object.__new__(type(self))
        bound.__dict__.update(self.__dict__)
        for pin_name in self._pin_attrs:
            inst_pin = getattr(obj, f"{self._attr_name}_{pin_name}", None)
            if inst_pin is not None:
                setattr(bound, f"_{pin_name}", inst_pin)
        return bound


class CanBus(Port):
    """CAN bus port: shielded HIGH/LOW pair that auto-connects to a shared off-page ref.

    All ``CanBus`` instances across a design share one ``OffPageReference``
    ("To CAN Bus"), so no explicit ``connect()`` call is needed.

    Usage::

        class MyECU(Component):
            class J1(Connector):
                can = CanBus(1, 2)          # CAN High on pin 1, CAN Low on pin 2
    """

    _pin_attrs = ("high", "low")
    _bus_ref: OffPageReference | None = None

    @classmethod
    def _ensure_ref(cls) -> OffPageReference:
        if cls._bus_ref is None:
            cls._bus_ref = OffPageReference("CAN_BUS", label="To CAN Bus")
        return cls._bus_ref

    def __init__(self, high_pin: int | str, low_pin: int | str) -> None:
        super().__init__()
        ref = CanBus._ensure_ref()
        sg = ShieldGroup(label="", pins=[], single_oval=True, drain=_CAN_DRAIN)
        self._high = Pin(high_pin, "CAN High")
        self._low = Pin(low_pin, "CAN Low")
        for p in (self._high, self._low):
            p.shield_group = sg
            sg.pins.append(p)
        # Auto-connect at class level; all instances inherit this connection.
        self._high.connect(ref)
        self._seg_low = self._low.connect(ref)

    def note(self, text: str) -> None:
        """Set a note on the CAN Low wire (bottom of the shielded pair)."""
        self._seg_low.notes = text


class RS232(Port):
    """RS-232 serial port: TX, RX, and optional GND, always shielded.

    ``connect()`` performs the cross-connection (TX→RX, RX→TX) automatically.

    Args:
        tx_pin: transmit pin number on this connector.
        rx_pin: receive pin number on this connector.
        gnd_pin: optional ground pin number (omit if ground is not wired).
        name: label prefix, e.g. ``"RS-232 3"``.

    Usage::

        class MyDevice(Component):
            class J1(Connector):
                rs232 = RS232(tx_pin=5, rx_pin=4, gnd_pin=6)

        MyDevice.J1.rs232.connect(OtherDevice.J2.rs232)
        MyDevice.J1.rs232.connect(OtherDevice.J2.rs232, ground=False)
    """

    _pin_attrs = ("tx", "rx", "gnd")

    def __init__(
        self,
        tx_pin: int | str,
        rx_pin: int | str,
        gnd_pin: int | str | None = None,
        name: str = "RS-232",
    ) -> None:
        super().__init__()
        self._name = name
        sg = ShieldGroup(label="", pins=[])
        self._sg = sg
        self._tx = Pin(tx_pin, f"{name} Out")
        self._rx = Pin(rx_pin, f"{name} In")
        self._gnd: Pin | None = None
        pins: list[Pin] = [self._tx, self._rx]
        if gnd_pin is not None:
            self._gnd = Pin(gnd_pin, f"{name} GND")
            pins.append(self._gnd)
            sg.drain = self._gnd
        for p in pins:
            p.shield_group = sg
            sg.pins.append(p)

    def connect(self, other: RS232, *, ground: bool = True, notes: str = "") -> None:
        """Cross-connect: self.TX → other.RX and self.RX → other.TX."""
        self._tx.connect(other._rx)
        seg_rx = self._rx.connect(other._tx)
        if self._gnd is not None and other._gnd is not None:
            self._sg.drain_remote = other._gnd
            other._sg.drain = other._gnd
            other._sg.drain_remote = self._gnd
        if ground and self._gnd is not None and other._gnd is not None:
            seg_gnd = self._gnd.connect(other._gnd)
            if notes:
                seg_gnd.notes = notes
        elif notes:
            seg_rx.notes = notes


class GPIO(Port):
    """Three-wire analog port: positive (drive), signal (sense), ground reference.

    Shielded by default. ``connect()`` matches pins by role:
    positive↔positive, signal↔signal, ground↔ground.

    Args:
        positive_pin: excitation / drive pin number.
        signal_pin: measurement / sensor return pin number.
        ground_pin: ground reference pin number.
        name: label prefix.
        shielded: wrap pins in a ShieldGroup (default ``True``).

    Usage::

        class Sensor(Component):
            output = GPIO("Or", "Gr", "Bl", name="Position")

        class Reader(Component):
            class J1(Connector):
                gp1 = GPIO(18, 19, 20, name="GP1")

        Reader.J1.gp1.connect(sensor_inst.output)
    """

    _pin_attrs = ("positive", "signal", "ground")

    def __init__(
        self,
        positive_pin: int | str,
        signal_pin: int | str,
        ground_pin: int | str,
        name: str = "GPIO",
        shielded: bool = True,
    ) -> None:
        super().__init__()
        self._name = name
        self._positive = Pin(positive_pin, f"{name} Positive")
        self._signal = Pin(signal_pin, name)
        self._ground = Pin(ground_pin, f"{name} Ground")
        self._sg: ShieldGroup | None = None
        if shielded:
            sg = ShieldGroup(label="", pins=[])
            self._sg = sg
            for p in (self._positive, self._signal, self._ground):
                p.shield_group = sg
                sg.pins.append(p)

    def connect(self, other: GPIO, notes: str = "", drain=None, drain_remote=None, **kwargs) -> None:
        """Connect positive↔positive, signal↔signal, ground↔ground.

        Args:
            drain: endpoint (e.g. GroundSymbol) that drains the shield at the local end.
            drain_remote: endpoint that drains the shield at the remote end.
        """
        self._positive.connect(other._positive, **kwargs)
        self._signal.connect(other._signal, **kwargs)
        seg = self._ground.connect(other._ground, **kwargs)
        if notes:
            seg.notes = notes
        if drain is not None and self._sg is not None:
            self._sg.drain = drain
        if drain_remote is not None:
            if self._sg is not None:
                self._sg.drain_remote = drain_remote
            if other._sg is not None:
                other._sg.drain = drain_remote
