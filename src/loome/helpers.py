from __future__ import annotations

from .model import OffPageReference, Pin, ShieldGroup


class CanBus:
    """CAN bus port: shielded HIGH/LOW pair that auto-connects to a shared off-page ref.

    All ``CanBus`` instances across a design share one ``OffPageReference``
    ("To CAN Bus"), so no explicit ``connect()`` call is needed.

    Usage::

        class MyECU(Component):
            class J1(Connector):
                can = CanBus(1, 2)          # CAN High on pin 1, CAN Low on pin 2
    """

    _bus_ref: OffPageReference | None = None

    @classmethod
    def _ensure_ref(cls) -> OffPageReference:
        if cls._bus_ref is None:
            cls._bus_ref = OffPageReference("CAN_BUS", label="To CAN Bus")
        return cls._bus_ref

    def __init__(self, high_pin: int | str, low_pin: int | str) -> None:
        ref = CanBus._ensure_ref()
        sg = ShieldGroup(label="", pins=[])
        self._high = Pin(high_pin, "CAN High")
        self._low = Pin(low_pin, "CAN Low")
        for p in (self._high, self._low):
            p.shield_group = sg
            sg.pins.append(p)
        # Auto-connect at class level; all instances inherit this connection.
        self._high.connect(ref)
        self._low.connect(ref)
        self._attr_name = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        # Inject the individual pins so Component/Connector machinery can find them.
        setattr(owner, f"{name}_high", self._high)
        setattr(owner, f"{name}_low", self._low)

    def __get__(self, obj: object | None, objtype: type | None = None) -> CanBus:
        if obj is None:
            return self
        bound = object.__new__(CanBus)
        bound._attr_name = self._attr_name
        bound._high = getattr(obj, f"{self._attr_name}_high", self._high)
        bound._low = getattr(obj, f"{self._attr_name}_low", self._low)
        return bound


class RS232:
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

    def __init__(
        self,
        tx_pin: int | str,
        rx_pin: int | str,
        gnd_pin: int | str | None = None,
        name: str = "RS-232",
    ) -> None:
        self._name = name
        self._attr_name = ""
        sg = ShieldGroup(label="", pins=[])
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

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        setattr(owner, f"{name}_tx", self._tx)
        setattr(owner, f"{name}_rx", self._rx)
        if self._gnd is not None:
            setattr(owner, f"{name}_gnd", self._gnd)

    def __get__(self, obj: object | None, objtype: type | None = None) -> RS232:
        if obj is None:
            return self
        bound = object.__new__(RS232)
        bound._name = self._name
        bound._attr_name = self._attr_name
        bound._tx = getattr(obj, f"{self._attr_name}_tx", self._tx)
        bound._rx = getattr(obj, f"{self._attr_name}_rx", self._rx)
        bound._gnd = getattr(obj, f"{self._attr_name}_gnd", self._gnd) if self._gnd is not None else None
        return bound

    def connect(self, other: RS232, *, ground: bool = True) -> None:
        """Cross-connect: self.TX → other.RX and self.RX → other.TX."""
        self._tx.connect(other._rx)
        self._rx.connect(other._tx)
        if ground and self._gnd is not None and other._gnd is not None:
            self._gnd.connect(other._gnd)


class GPIO:
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

    def __init__(
        self,
        positive_pin: int | str,
        signal_pin: int | str,
        ground_pin: int | str,
        name: str = "GPIO",
        shielded: bool = True,
    ) -> None:
        self._name = name
        self._attr_name = ""
        self._positive = Pin(positive_pin, f"{name} Positive")
        self._signal = Pin(signal_pin, name)
        self._ground = Pin(ground_pin, f"{name} Ground")
        if shielded:
            sg = ShieldGroup(label="", pins=[])
            for p in (self._positive, self._signal, self._ground):
                p.shield_group = sg
                sg.pins.append(p)

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = name
        setattr(owner, f"{name}_positive", self._positive)
        setattr(owner, f"{name}_signal", self._signal)
        setattr(owner, f"{name}_ground", self._ground)

    def __get__(self, obj: object | None, objtype: type | None = None) -> GPIO:
        if obj is None:
            return self
        bound = object.__new__(GPIO)
        bound._name = self._name
        bound._attr_name = self._attr_name
        bound._positive = getattr(obj, f"{self._attr_name}_positive", self._positive)
        bound._signal = getattr(obj, f"{self._attr_name}_signal", self._signal)
        bound._ground = getattr(obj, f"{self._attr_name}_ground", self._ground)
        return bound

    def connect(self, other: GPIO, **kwargs) -> None:
        """Connect positive↔positive, signal↔signal, ground↔ground."""
        self._positive.connect(other._positive, **kwargs)
        self._signal.connect(other._signal, **kwargs)
        self._ground.connect(other._ground, **kwargs)
