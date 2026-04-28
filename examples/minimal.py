from loome import Component, Connector, Fuse, GroundSymbol, Harness, Pin, SpliceNode


class PowerSupply(Component):
    class J1(Connector):
        positive = Pin(1, "12V Out")
        ground = Pin(2, "Ground")


class LoadDevice(Component):
    class J1(Connector):
        power = Pin(1, "Power In")
        ground = Pin(2, "Ground")
        signal = Pin(3, "Signal Out")


class Display(Component):
    class J1(Connector):
        power = Pin(1, "Power")
        ground = Pin(2, "Ground")
        data_in = Pin(3, "Data In")


psu = PowerSupply("Power Supply")
device = LoadDevice("Load Device")
display = Display("Display")

f1 = Fuse("F1", amps=5)
f2 = Fuse("F2", amps=3)
sp1 = SpliceNode("SP1", label="Power Splice")
gnd = GroundSymbol("GND")

# Power: PSU positive -> fuse, then distribute to loads
psu.J1.positive >> f1
device.J1.power >> f1
display.J1.power >> f1

# Grounds
psu.J1.ground >> gnd
device.J1.ground >> gnd
display.J1.ground >> gnd

# Signal
device.J1.signal >> display.J1.data_in

harness = Harness("Minimal Example", length_unit="in")
