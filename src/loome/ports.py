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

from typing import Any

from .model import DrainSpec, GroundSymbol, OffPageReference, Pin, ShieldGroup, _resolve_drain

# Sentinel meaning "caller did not supply this argument" — distinct from None
# (which means "explicitly set to floating / no drain").
_UNSET: Any = object()


class PortBuilder:
    """Lazy fluent wrapper returned by ``port >> other``.

    The underlying ``connect()`` is deferred until the builder is garbage
    collected, so modifiers like ``.ground(False)`` can be applied first.
    """

    def __init__(self, src, dst) -> None:
        self._src = src
        self._dst = dst
        self._kwargs: dict = {}
        self._done = False

    def _finish(self) -> None:
        if not self._done:
            self._done = True
            self._src.connect(self._dst, **self._kwargs)

    def __del__(self) -> None:
        self._finish()

    def ground(self, value: bool) -> "PortBuilder":
        self._kwargs["ground"] = value
        return self

    def drain(self, value: DrainSpec = "block") -> "PortBuilder":
        self._kwargs["drain"] = value
        return self

    def drain_remote(self, value: DrainSpec = "block") -> "PortBuilder":
        self._kwargs["drain_remote"] = value
        return self

    def notes(self, value: str) -> "PortBuilder":
        self._kwargs["notes"] = value
        return self


_CAN_DRAIN = GroundSymbol("_can_shield_drain_", "GND", style="open")
_RS232_BACKSHELL = GroundSymbol("_rs232_backshell_", "GND", style="open")
_ARINC_BACKSHELL = GroundSymbol("_arinc_backshell_", "GND", style="open")
_ETHERNET_BACKSHELL = GroundSymbol("_ethernet_backshell_", "GND", style="open")


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

    def terminate(self) -> None:
        """Mark this CAN port as externally terminated (120Ω adapter).

        Must be called on a bound port (i.e. from a component instance method
        via ``self.J1.can.terminate()``). The renderer draws a TERM box spanning
        the H/L rows for any connector whose CAN pins are marked terminated.
        """
        self._high._can_terminated = True
        self._low._can_terminated = True

    def note(self, text: str) -> None:
        """Set a note on the CAN Low wire (bottom of the shielded pair)."""
        self._seg_low.notes = text

    @property
    def high(self) -> Pin:
        return self._high

    @property
    def low(self) -> Pin:
        return self._low


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
        # Shield is always drained to the connector backshell at this end,
        # independent of whether the cable carries a separate signal-ground wire.
        sg = ShieldGroup(label="", pins=[], drain=_RS232_BACKSHELL)
        self._sg = sg
        self._tx = Pin(tx_pin, f"{name} Out")
        self._rx = Pin(rx_pin, f"{name} In")
        self._gnd: Pin | None = None
        pins: list[Pin] = [self._tx, self._rx]
        if gnd_pin is not None:
            self._gnd = Pin(gnd_pin, f"{name} GND")
            pins.append(self._gnd)
        for p in pins:
            p.shield_group = sg
            sg.pins.append(p)

    def connect(
        self,
        other: RS232,
        *,
        ground: bool = True,
        notes: str = "",
        drain: DrainSpec | object = _UNSET,
        drain_remote: DrainSpec | object = _UNSET,
    ) -> None:
        """Cross-connect: self.TX → other.RX and self.RX → other.TX."""
        seg_tx = self._tx.connect(other._rx)
        seg_tx.port_order = 0
        seg_rx = self._rx.connect(other._tx)
        seg_rx.port_order = 1
        self._sg.drain_remote = _resolve_drain(drain_remote) if drain_remote is not _UNSET else _RS232_BACKSHELL
        other._sg.drain_remote = _resolve_drain(drain) if drain is not _UNSET else _RS232_BACKSHELL
        if drain is not _UNSET:
            self._sg.drain = _resolve_drain(drain)
        if drain_remote is not _UNSET:
            other._sg.drain = _resolve_drain(drain_remote)
        if ground and self._gnd is not None and other._gnd is not None:
            seg_gnd = self._gnd.connect(other._gnd)
            seg_gnd.port_order = 2
            if notes:
                seg_gnd.notes = notes
        elif notes:
            seg_rx.notes = notes

    def __rshift__(self, other: RS232) -> PortBuilder:
        return PortBuilder(self, other)

    @property
    def tx(self) -> Pin:
        return self._tx

    @property
    def rx(self) -> Pin:
        return self._rx

    @property
    def gnd(self) -> Pin | None:
        return self._gnd


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

    def __rshift__(self, other: GPIO) -> PortBuilder:
        return PortBuilder(self, other)

    def connect(
        self,
        other: GPIO,
        notes: str = "",
        drain: DrainSpec | object = _UNSET,
        drain_remote: DrainSpec | object = _UNSET,
        **_,
    ) -> None:
        """Connect positive↔positive, signal↔signal, ground↔ground.

        Args:
            drain: drain endpoint at the local end. ``True`` = local ground,
                ``False``/``None`` = floating, or an explicit ``WireEndpoint``.
            drain_remote: drain endpoint at the remote end (same encoding).
        """
        self._positive.connect(other._positive)
        self._signal.connect(other._signal)
        seg = self._ground.connect(other._ground)
        if notes:
            seg.notes = notes
        if drain is not _UNSET:
            if self._sg is not None:
                self._sg.drain = _resolve_drain(drain)
            if other._sg is not None:
                other._sg.drain_remote = _resolve_drain(drain)
        if drain_remote is not _UNSET:
            if self._sg is not None:
                self._sg.drain_remote = _resolve_drain(drain_remote)
            if other._sg is not None:
                other._sg.drain = _resolve_drain(drain_remote)

    @property
    def positive(self) -> Pin:
        return self._positive

    @property
    def signal(self) -> Pin:
        return self._signal

    @property
    def ground(self) -> Pin:
        return self._ground


class ARINC429(Port):
    """Shielded unidirectional ARINC 429 differential pair (A and B wires).

    ``direction`` must be ``"in"`` or ``"out"``. Connecting two ports with the
    same direction raises ``ValueError``.

    Usage::

        class MyLRU(Component):
            class J1(Connector):
                arinc_in = ARINC429(48, 67, "in", name="ARINC 429 In 1")
                arinc_out = ARINC429(50, 68, "out", name="ARINC 429 Out 1")

        MyLRU.J1.arinc_out >> OtherLRU.J2.arinc_in
    """

    _pin_attrs = ("a", "b")

    def __init__(
        self,
        a_pin: int | str,
        b_pin: int | str,
        direction: str,
        name: str = "ARINC 429",
    ) -> None:
        super().__init__()
        if direction not in ("in", "out"):
            raise ValueError(f"direction must be 'in' or 'out', got {direction!r}")
        self._direction = direction
        self._name = name
        sg = ShieldGroup(label="", pins=[], drain=_ARINC_BACKSHELL)
        self._sg = sg
        self._a = Pin(a_pin, f"{name} A")
        self._b = Pin(b_pin, f"{name} B")
        for p in (self._a, self._b):
            p.shield_group = sg
            sg.pins.append(p)

    def connect(
        self,
        other: "ARINC429",
        *,
        notes: str = "",
        drain: DrainSpec | object = _UNSET,
        drain_remote: DrainSpec | object = _UNSET,
        **_,
    ) -> None:
        if self._direction == other._direction:
            raise ValueError(f"ARINC 429 requires one 'in' and one 'out' port, but both are {self._direction!r}")
        seg = self._a.connect(other._a)
        self._b.connect(other._b)
        if notes:
            seg.notes = notes
        self._sg.drain_remote = _resolve_drain(drain_remote) if drain_remote is not _UNSET else _ARINC_BACKSHELL
        other._sg.drain_remote = _resolve_drain(drain) if drain is not _UNSET else _ARINC_BACKSHELL
        if drain is not _UNSET:
            self._sg.drain = _resolve_drain(drain)
        if drain_remote is not _UNSET:
            other._sg.drain = _resolve_drain(drain_remote)

    def __rshift__(self, other: "ARINC429") -> PortBuilder:
        return PortBuilder(self, other)


class GarminEthernet(Port):
    """Shielded unidirectional Garmin Ethernet differential pair (A and B wires).

    Identical semantics to :class:`ARINC429` — unidirectional, shielded,
    direction-checked on connect — but labelled as Ethernet.

    Usage::

        class GTX45R(Component):
            class P3252(Connector):
                ethernet_out = GarminEthernet(6, 1, "out", name="Ethernet Out 1")
                ethernet_in  = GarminEthernet(7, 2, "in",  name="Ethernet In 1")
    """

    _pin_attrs = ("a", "b")

    def __init__(
        self,
        a_pin: int | str,
        b_pin: int | str,
        direction: str,
        name: str = "Ethernet",
    ) -> None:
        super().__init__()
        if direction not in ("in", "out"):
            raise ValueError(f"direction must be 'in' or 'out', got {direction!r}")
        self._direction = direction
        self._name = name
        sg = ShieldGroup(label="", pins=[], drain=_ETHERNET_BACKSHELL)
        self._sg = sg
        self._a = Pin(a_pin, f"{name} A")
        self._b = Pin(b_pin, f"{name} B")
        for p in (self._a, self._b):
            p.shield_group = sg
            sg.pins.append(p)

    def connect(
        self,
        other: "GarminEthernet",
        *,
        notes: str = "",
        drain: DrainSpec | object = _UNSET,
        drain_remote: DrainSpec | object = _UNSET,
        **_,
    ) -> None:
        if self._direction == other._direction:
            raise ValueError(
                f"Ethernet connection requires one 'in' and one 'out' port, but both are {self._direction!r}"
            )
        seg = self._a.connect(other._a)
        self._b.connect(other._b)
        if notes:
            seg.notes = notes
        self._sg.drain_remote = _resolve_drain(drain_remote) if drain_remote is not _UNSET else _ETHERNET_BACKSHELL
        other._sg.drain_remote = _resolve_drain(drain) if drain is not _UNSET else _ETHERNET_BACKSHELL
        if drain is not _UNSET:
            self._sg.drain = _resolve_drain(drain)
        if drain_remote is not _UNSET:
            other._sg.drain = _resolve_drain(drain_remote)

    def __rshift__(self, other: "GarminEthernet") -> PortBuilder:
        return PortBuilder(self, other)


class Thermocouple(Port):
    """Two-wire thermocouple connection: High (yellow) and Low (red).

    Default gauge is 20. ``connect()`` wires high↔high with yellow wire and
    low↔low with red wire.

    Usage::

        class GEA24(Component):
            class J241(Connector):
                egt1 = Thermocouple(25, 13, "EGT 1")

        # creates "EGT 1 High" on pin 25 (yellow) and "EGT 1 Low" on pin 13 (red)
        gea24.J241.egt1 >> egt1_probe.leads
    """

    _pin_attrs = ("high", "low")

    def __init__(
        self,
        high_pin: int | str,
        low_pin: int | str,
        name: str = "Thermocouple",
        gauge: int | str = 20,
    ) -> None:
        super().__init__()
        self._name = name
        self._gauge = gauge
        self._high = Pin(high_pin, f"{name} High")
        self._low = Pin(low_pin, f"{name} Low")
        sg = ShieldGroup(label="", pins=[], cable_only=True)
        for p in (self._high, self._low):
            p.shield_group = sg
            sg.pins.append(p)

    def connect(self, other: "Thermocouple", *, notes: str = "", **_) -> None:
        seg = self._high.connect(other._high, gauge=self._gauge, color="Y")
        self._low.connect(other._low, gauge=self._gauge, color="R")
        if notes:
            seg.notes = notes

    def __rshift__(self, other: "Thermocouple") -> PortBuilder:
        return PortBuilder(self, other)
