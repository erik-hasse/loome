from enum import StrEnum

from loome import (
    DPST,
    GPIO,
    RS232,
    CanBus,
    Component,
    Connector,
    Fuse,
    GroundSymbol,
    Harness,
    Pin,
    Shield,
    SpliceNode,
)


class GSU25(Component):
    """Air Data Unit"""

    class J251(Connector):
        ground = Pin(6, "Ground")
        power = Pin(7, "Power")
        backup_power = Pin(8, "Backup Power")

        can = CanBus(1, 2)
        rs232 = RS232(5, 4, 6, name="RS-232")  # tx, rx, gnd

    class J252(Connector):
        oat_probe_power = Pin(1, "OAT Probe Power")
        oat_probe_high = Pin(2, "OAT Probe High")
        oat_probe_low = Pin(3, "OAT Probe Low")

        rs232_3 = RS232(9, 10, 11, name="RS-232 3")  # tx, rx, gnd

        magnetometer_power = Pin(6, "Magnetometer Power")


class GDU460(Component):
    """Display Unit"""

    class P4501(Connector):
        rs232 = RS232(4, 5, 6, name="RS-232")  # tx, rx, gnd

    class P4601(Connector):
        rs232 = RS232(4, 5, 6, name="RS-232")  # tx, rx, gnd


class OATProbe(Component):
    oat_probe_power = Pin(1, "OAT Probe Power")
    oat_probe_high = Pin(2, "OAT Probe High")
    oat_probe_low = Pin(3, "OAT Probe Low")


class GTX45R(Component):
    """Remote Transponder"""

    class P3251(Connector):
        rs232 = RS232(9, 31, 11, name="RS-232")  # tx, rx, gnd


class GMU11(Component):
    """Magnetometer"""

    class J441(Connector):
        power = Pin(8, "Power")
        backup_power = Pin(7, "Backup Power")
        ground = Pin(9, "Ground")
        can = CanBus(1, 2)


class _BaseJ281(Connector):
    can = CanBus(1, 2)
    can_term_1 = Pin(3, "Can Term 1")
    can_term_2 = Pin(4, "Can Term 2")

    id_strap_1 = Pin(5, "ID Strap 1")
    id_strap_2 = Pin(6, "ID Strap 2")

    ground = Pin(9, "Ground")
    power = Pin(10, "Power")
    trim_in_1 = Pin(11, "Trim In 1")
    trim_in_2 = Pin(12, "Trim In 2")
    trim_out_1 = Pin(13, "Trim Out 1")
    trim_out_2 = Pin(14, "Trim Out 2")
    disconnect = Pin(15, "Disconnect")


class Axis(StrEnum):
    ROLL = "roll"
    PITCH = "pitch"
    YAW = "yaw"


class GSA28(Component):
    """Autopilot Servo (pitch/yaw variant). If axis is provided, strap jumpers will be
    connected automatically."""

    def __init__(self, name: str, axis: Axis | None = None, is_trim: bool = False):
        super().__init__(name)
        self.axis = axis
        self.is_trim = is_trim

        match axis, is_trim:
            case Axis.ROLL, False:
                if type(self) is GSA28:
                    raise ValueError("Use GSA28RollServo instead")
            case Axis.PITCH, False:
                self.J281[5].connect(self.J281[8])
            case Axis.YAW, False:
                self.J281[6].connect(self.J281[7])
            case Axis.ROLL, True:
                self.J281[5].connect(self.J281[8])
                self.J281[6].connect(self.J281[7])
            case Axis.PITCH, True:
                self.J281[7].connect(self.J281[8])
            case Axis.YAW, True:
                raise ValueError("GSA 28 does not support yaw trim")

    class J281(_BaseJ281):
        id_strap_3 = Pin(7, "ID Strap 3")
        id_strap_4 = Pin(8, "ID Strap 4")


class GSA28RollServo(GSA28):
    """Autopilot Servo, roll variant — repurposes pins 7/8 as RS-232."""

    def __init__(self, name: str):
        super().__init__(name, Axis.ROLL, is_trim=False)

    class J281(_BaseJ281):
        rs232 = RS232(7, 8, name="RS-232")


class GAD27(Component):
    """Flap, Lights, Trim Controller"""

    class J272(Connector):
        trim_out_1 = Pin(10, "Trim Out 1")
        trim_out_2 = Pin(9, "Trim Out 2")


class RayAllanTrim(Component):
    position = GPIO("Or", "Gr", "Bl", name="Position")  # positive, signal, ground
    trim_1 = Pin("Wh", "Trim 1")
    trim_2 = Pin("Gy", "Trim 2")


class Stick(Component):
    ap_disconnect = Pin(10, "AP Disconnect")


class GEA24(Component):
    """EIS Interface"""

    class J244(Connector):
        gp1 = GPIO(18, 19, 20, name="GP1")  # positive, signal, ground
        gp2 = GPIO(21, 22, 23, name="GP2")  # positive, signal, ground


class GMC507(Component):
    """Autopilot controller"""

    class P7001(Connector):
        remote_go_around = Pin(10, "Remote Go-Around")


class GTN650Xi(Component):
    """GPS/NAV/COM"""

    class P1001(Connector):
        remote_go_around = Pin(37, "Remote Go-Around")


# ── instances ─────────────────────────────────────────────────────────────────

pilot_stick = Stick("Pilot Stick")
copilot_stick = Stick("Copilot Stick")
pfd = GDU460("GDU 460 PFD")

gsu25 = GSU25("GSU 25")
oat_probe = OATProbe("OAT Probe")
gtx45r = GTX45R("GTX45R")
gmu11 = GMU11("GMU 11")
gea24 = GEA24("GEA24")

# ── terminals ─────────────────────────────────────────────────────────────────

gnd = GroundSymbol("CHASSIS_GND")
air_data_fuse = Fuse("air_data", "Air Data", 5)
air_data_backup_fuse = Fuse("air_data_backup", "Air Data Backup", 5)
backup_splice = SpliceNode("S1", label="Bkp Pwr")

# ── switches ──────────────────────────────────────────────────────────────────

toga = DPST("TO/GA", momentary=True)
toga_splice = SpliceNode("toga", label="TOGA")
toga.com1.connect(toga_splice)
toga.com2.connect(toga_splice)
toga_splice.connect(gnd)


# ── class-level connections ───────────────────────────────────────────────────

GSU25.J251.power.connect(air_data_fuse)
GSU25.J251.backup_power.connect(backup_splice)
backup_splice.connect(air_data_backup_fuse)
backup_splice.connect(GMU11.J441.backup_power)
GSU25.J251.ground.connect(gnd)
GSU25.J251.rs232.connect(pfd.P4601.rs232, ground=False)  # cross-connects TX↔RX; GND defined but not wired

oat_shield = Shield(drain=gnd, drain_remote=gnd)
with oat_shield:
    GSU25.J252.oat_probe_power.connect(OATProbe.oat_probe_power)
    GSU25.J252.oat_probe_high.connect(OATProbe.oat_probe_high)
    GSU25.J252.oat_probe_low.connect(OATProbe.oat_probe_low)
GSU25.J252.rs232_3.connect(GTX45R.P3251.rs232)
GSU25.J252.magnetometer_power.connect(GMU11.J441.power)

GMU11.J441.ground.connect(gnd)

# ── autopilot ─────────────────────────────────────────────────────────────────

ap_fuse = Fuse("ap", "Autopilot", 5)
ap_disconnect_splice = SpliceNode("AP Disconnect", label="AP Disconnect")
roll_servo = GSA28RollServo("Roll Servo")
roll_trim = RayAllanTrim("Roll Trim")
pitch_servo = GSA28("Pitch Servo", axis=Axis.PITCH)
pitch_trim = RayAllanTrim("Pitch Trim")
yaw_servo = GSA28("Yaw Servo", axis=Axis.YAW)
controller = GMC507("AP Controller")

# Class-level connections apply to all three servo instances
GSA28.J281.ground.connect(gnd)
GSA28.J281.power.connect(ap_fuse)
GSA28.J281.disconnect.connect(ap_disconnect_splice)

roll_servo.J281.trim_in_1.connect(GAD27.J272.trim_out_1)
roll_servo.J281.trim_in_2.connect(GAD27.J272.trim_out_2)
roll_servo.J281.trim_out_1.connect(roll_trim.trim_1)
roll_servo.J281.trim_out_2.connect(roll_trim.trim_2)


pilot_stick.ap_disconnect.connect(ap_disconnect_splice)
copilot_stick.ap_disconnect.connect(ap_disconnect_splice)

GEA24.J244.gp1.connect(pitch_trim.position, drain_remote=gnd)
GEA24.J244.gp2.connect(roll_trim.position, drain_remote=gnd)

controller.P7001.remote_go_around.connect(toga.no1)

# ── GPS ───────────────────────────────────────────────────────────────────────

gps = GTN650Xi("GPS")
gps.P1001.remote_go_around.connect(toga.no2)

# ── harness ───────────────────────────────────────────────────────────────────

harness = Harness("Avionics Harness")
