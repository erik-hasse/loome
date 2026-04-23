from loome import Connector, Fuse, GroundSymbol, Harness, Pin, SpliceNode
from loome.model import Component


class Widget(Component):
    class J1(Connector):
        power = Pin(1, "Power")
        ground = Pin(2, "Ground")


class Display(Component):
    class P1(Connector):
        power_in = Pin(1, "Power In")
        ground_in = Pin(2, "Ground In")


widget = Widget("Widget")
display = Display("Display")
gnd = GroundSymbol("CHASSIS_GND")
main_fuse = Fuse("main", "Main", 5)
pwr_splice = SpliceNode("S1", label="Pwr")

Widget.J1.power.connect(pwr_splice)
pwr_splice.connect(main_fuse)
pwr_splice.connect(Display.P1.power_in)
Widget.J1.ground.connect(gnd)
Display.P1.ground_in.connect(gnd)

harness = Harness("Schematic Golden")
