from loome.model import Component, Connector, Pin
from loome.ports import GPIO, Thermocouple


class RayAllanTrim(Component):
    position = GPIO("Or", "Gr", "Bl", name="Position")  # positive, signal, ground
    trim_1 = Pin("Wh", "Trim 1")
    trim_2 = Pin("Gy", "Trim 2")


class Stick(Component):
    ap_disconnect = Pin(1, "AP Disconnect")
    push_to_talk = Pin(2, "Push to Talk")
    com_swap = Pin(3, "COM Swap")
    replay = Pin(4, "Replay")
    trim_up = Pin(5, "Trim Up")
    trim_down = Pin(6, "Trim Down")
    trim_left = Pin(7, "Trim Left")
    trim_right = Pin(8, "Trim Right")
    frequency_swap = Pin(9, "Frequency Swap")
    ground = Pin(11, "Ground")


class LEMO(Component):
    power = Pin(1, "Power")
    ground = Pin(2, "Ground")
    audio_left = Pin(3, "Audio Left")
    audio_right = Pin(4, "Audio Right")
    mic_high = Pin(5, "Mic High")
    mic_low = Pin(6, "Mic Low")


class TRS(Component):
    render = False
    tip = Pin("T", "Tip")
    ring = Pin("R", "Ring")
    sleeve = Pin("S", "Sleeve")


class LED(Component):
    render = False
    power = Pin(1, "Power")
    ground = Pin(2, "Ground")


class PHAviationFlapMotor(Component):
    extend = Pin("BRN", "Extend")
    retract = Pin("BLU", "Retract")

    position = GPIO("YLW", "WHT", "RED", name="Position")


class USBPort(Component):
    render = False
    power = Pin("RED", "Power")
    ground = Pin("BLK", "Ground")
    data_high = Pin("GRN", "Data High")
    data_low = Pin("WHT", "Data Low")


class Fan(Component):
    render = False
    control = GPIO("RED", "YLW", "BLK", name="Control")


class ACKE04(Component):
    class DIN(Connector):
        remote_switch = Pin(1, "Remote Switch")
        rs232_test = Pin(2, "R232 Test")
        ground = Pin(3, "Ground")
        elt_rx = Pin(4, "Elt RX")


class _Cylinder(Connector):
    egt = Thermocouple("YEL", "RED", "EGT")
    cht = Thermocouple("YEL", "RED", "CHT")


class Engine4Cyl(Component):
    render = False

    class Cylinder1(_Cylinder):
        pass

    class Cylinder2(_Cylinder):
        pass

    class Cylinder3(_Cylinder):
        pass

    class Cylinder4(_Cylinder):
        pass


class GPIOSensor(Component):
    render = False
    gpio = GPIO("RED", "GRN", "BLK", name="GPIO")


class HighLowSensor(Component):
    render = False
    high = Pin("RED", "High")
    low = Pin("GRN", "Low")


class SingleInputSensor(Component):
    render = False
    power = Pin(1, "Power")


class SDSECU(Component):
    tach = Pin("TBD1", "Tachometer")
    fuel_flow = Pin("TBD2", "Fuel Flow")


class AithreShield3(Component):
    power = Pin("RED", "Power")
    signal = Pin("WHT", "Signal")
    ground = Pin("BLK", "Ground")
