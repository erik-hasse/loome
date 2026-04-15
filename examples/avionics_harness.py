from loome import GPIO, RS232, CanBus, Component, Connector, Fuse, GroundSymbol, Harness, Pin, SpliceNode
from loome.model import Shielded


class GSU25(Component):
    """Air Data Unit"""

    class J251(Connector):
        ground = Pin(6, "Ground")
        power = Pin(7, "Power")
        backup_power = Pin(8, "Backup Power")

        can = CanBus(1, 2)
        rs232 = RS232(5, 4, 6, name="RS-232")  # tx, rx, gnd

    class J252(Connector):
        with Shielded():
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
    with Shielded():
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


class GSA28(Component):
    """Autopilot Servo"""

    class J281(Connector):
        can = CanBus(1, 2)
        can_term_1 = Pin(3, "Can Term 1")
        can_term_2 = Pin(4, "Can Term 2")

        id_strap_1 = Pin(5, "ID Strap 1")
        id_strap_2 = Pin(6, "ID Strap 2")
        id_strap_3 = Pin(7, "ID Strap 3")
        id_strap_4 = Pin(8, "ID Strap 4")

        rs232 = RS232(7, 8, name="RS-232 (Roll only)")
        ground = Pin(9, "Ground")
        power = Pin(10, "Power")
        trim_in_1 = Pin(11, "Trim In 1")
        trim_in_2 = Pin(12, "Trim In 2")
        trim_out_1 = Pin(13, "Trim Out 1")
        trim_out_2 = Pin(14, "Trim Out 2")
        disconnect = Pin(15, "Disconnect")


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

# ── class-level connections ───────────────────────────────────────────────────

GSU25.J251.power.connect(air_data_fuse)
GSU25.J251.backup_power.connect(backup_splice)
backup_splice.connect(air_data_backup_fuse)
backup_splice.connect(GMU11.J441.backup_power)
GSU25.J251.ground.connect(gnd)
GSU25.J251.rs232.connect(pfd.P4601.rs232, ground=False)  # cross-connects TX↔RX; GND defined but not wired

GSU25.J252.oat_probe_power.connect(OATProbe.oat_probe_power)
GSU25.J252.oat_probe_high.connect(OATProbe.oat_probe_high)
GSU25.J252.oat_probe_low.connect(OATProbe.oat_probe_low)
GSU25.J252.rs232_3.connect(GTX45R.P3251.rs232)
GSU25.J252.magnetometer_power.connect(GMU11.J441.power)

GMU11.J441.ground.connect(gnd)

# ── autopilot ─────────────────────────────────────────────────────────────────

ap_fuse = Fuse("ap", "Autopilot", 5)
ap_disconnect_splice = SpliceNode("AP Disconnect", label="AP Disconnect")
roll_servo = GSA28("Roll Servo")
roll_trim = RayAllanTrim("Roll Trim")
pitch_servo = GSA28("Pitch Servo")
pitch_trim = RayAllanTrim("Pitch Trim")
yaw_servo = GSA28("Yaw Servo")

# Class-level connections apply to all three servo instances
GSA28.J281.ground.connect(gnd)
GSA28.J281.power.connect(ap_fuse)
GSA28.J281.disconnect.connect(ap_disconnect_splice)

roll_servo.J281.trim_in_1.connect(GAD27.J272.trim_out_1)
roll_servo.J281.trim_in_2.connect(GAD27.J272.trim_out_2)
roll_servo.J281.trim_out_1.connect(roll_trim.trim_1)
roll_servo.J281.trim_out_2.connect(roll_trim.trim_2)

pitch_servo.J281.id_strap_1.connect(pitch_servo.J281.id_strap_4)
yaw_servo.J281.id_strap_2.connect(yaw_servo.J281.id_strap_3)

pilot_stick.ap_disconnect.connect(ap_disconnect_splice)
copilot_stick.ap_disconnect.connect(ap_disconnect_splice)

GEA24.J244.gp1.connect(pitch_trim.position)
GEA24.J244.gp2.connect(roll_trim.position)

# ── harness ───────────────────────────────────────────────────────────────────

harness = Harness("Avionics Harness")
