from loome import Connector, Disconnect, DisconnectPin, Fuse, GroundSymbol, Harness, Pin
from loome.model import Component


class Widget(Component):
    class J1(Connector):
        power = Pin(1, "Power")
        ground = Pin(2, "Ground")

    class J2(Connector):
        signal = Pin(1, "Signal")


class Sprocket(Component):
    signal = Pin(1, "Signal")


class Display(Component):
    class P1(Connector):
        power_in = Pin(1, "Power In")
        ground_in = Pin(2, "Ground In")
        signal_out = Pin(3, "Signal Out")


class _MateDT(Disconnect):
    pwr = DisconnectPin(1, "signal")


widget = Widget("Widget")
display = Display("Display")
sprocket = Sprocket("Sprocket")
gnd = GroundSymbol("CHASSIS_GND")
main_fuse = Fuse("main", "Main", 5)
mate = _MateDT("DC1", label="Service disconnect")

widget.J1.power >> main_fuse
widget.J1.ground.connect(gnd)
with display.P1 as c:
    c.ground_in >> gnd
    c.power_in.connect(main_fuse)
    c.signal_out >> sprocket.signal
    c.signal_out.connect(widget.J2.signal)

mate.between(sprocket.signal, display.P1.signal_out)

harness = Harness("Schematic Golden")
