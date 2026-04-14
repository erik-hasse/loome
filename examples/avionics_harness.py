from loome import Component, Connector, Fuse, GroundSymbol, Harness, OffPageReference, Pin, SpliceNode
from loome.model import Shielded


class GSU25(Component):
    class J251(Connector):
        ground = Pin(6, "Ground")
        power = Pin(7, "Power")
        backup_power = Pin(8, "Backup Power")

        with Shielded():
            can_high = Pin(1, "CAN High")
            can_low = Pin(2, "CAN Low")
        with Shielded():
            rs232_in = Pin(4, "RS-232 In")
            rs232_out = Pin(5, "RS-232 Out")

    class J252(Connector):
        with Shielded():
            oat_probe_power = Pin(1, "OAT Probe Power")
            oat_probe_high = Pin(2, "OAT Probe High")
            oat_probe_low = Pin(3, "OAT Probe Low")

        with Shielded():
            rs232_3_rx = Pin(10, "RS-232 3 RX")
            rs232_3_tx = Pin(9, "RS-232 3 TX")
            rs232_3_gnd = Pin(11, "RS-232 3 GND")

        magnetometer_power = Pin(6, "Magnetometer Power")


class GDU460(Component):
    class P4601(Connector):
        with Shielded():
            rs232_out = Pin(4, "RS-232 Out")
            rs232_in = Pin(5, "RS-232 In")


class OATProbe(Component):
    with Shielded():
        oat_probe_power = Pin(1, "OAT Probe Power")
        oat_probe_high = Pin(2, "OAT Probe High")
        oat_probe_low = Pin(3, "OAT Probe Low")


class GTX45R(Component):
    class P3251(Connector):
        with Shielded():
            rs232_1_out = Pin(9, "RS-232 1 Out")
            rs232_1_in = Pin(31, "RS-232 1 In")
            rs232_1_gnd = Pin(11, "RS-232 1 GND")


class GMU11(Component):
    power = Pin(8, "Power")
    backup_power = Pin(7, "Backup Power")

    ground = Pin(9, "Ground")

    with Shielded():
        can_high = Pin(1, "CAN High")
        can_low = Pin(2, "CAN Low")


class GSA28(Component):
    power = Pin(10, "Power")
    ground = Pin(9, "Ground")

    with Shielded():
        can_high = Pin(1, "CAN High")
        can_low = Pin(2, "CAN Low")

    disconnect = Pin(15, "Disconnect")

    trim_in_1 = Pin(11, "Trim In 1")
    trim_in_2 = Pin(12, "Trim In 2")

    trim_out_1 = Pin(13, "Trim Out 1")
    trim_out_2 = Pin(14, "Trim Out 2")


class GAD27(Component):
    class J272(Connector):
        trim_out_1 = Pin(10, "Trim Out 1")
        trim_out_2 = Pin(9, "Trim Out 2")


class RayAllanTrim(Component):
    with Shielded():
        excitation = Pin("Or", "Excitation")
        position = Pin("Gr", "Position")
        ground = Pin("Bl", "Ground")

    trim_1 = Pin("Wh", "Trim 1")
    trim_2 = Pin("Gy", "Trim 2")


class Stick(Component):
    ap_disconnect = Pin(10, "AP Disconnect")


class GEA24(Component):
    class J244(Connector):
        gp1_high = Pin(18, "GP1 High")
        gp1 = Pin(19, "GP1")
        gp1_low = Pin(20, "GP1 Low")

        gp2_high = Pin(21, "GP2 High")
        gp2 = Pin(22, "GP2")
        gp2_low = Pin(23, "GP2 Low")


pilot_stick = Stick("Pilot Stick")
copilot_stick = Stick("Copilot Stick")


gnd = GroundSymbol("CHASSIS_GND")
can_bus = OffPageReference("CAN_BUS", label="To CAN Bus")
pfd = GDU460("GDU 460 PFD")

air_data_fuse = Fuse("air_data", "Air Data", 5)
air_data_backup_fuse = Fuse("air_data_backup", "Air Data Backup", 5)

# Splice: backup power rail shared between GSU 25 and GMU 11
backup_splice = SpliceNode("S1", label="Bkp Pwr")

# Class-level connections — pin numbers are automatic from Pin definitions
GSU25.J251.power.connect(air_data_fuse)
GSU25.J251.backup_power.connect(backup_splice)
backup_splice.connect(air_data_backup_fuse)
backup_splice.connect(GMU11.backup_power)
GSU25.J251.ground.connect(gnd)
GSU25.J251.can_high.connect(can_bus)
GSU25.J251.can_low.connect(can_bus)
GSU25.J251.rs232_in.connect(pfd.P4601.rs232_out)
GSU25.J251.rs232_out.connect(pfd.P4601.rs232_in)

GSU25.J252.oat_probe_power.connect(OATProbe.oat_probe_power)
GSU25.J252.oat_probe_low.connect(OATProbe.oat_probe_low)
GSU25.J252.oat_probe_high.connect(OATProbe.oat_probe_high)
GSU25.J252.rs232_3_rx.connect(GTX45R.P3251.rs232_1_out)
GSU25.J252.rs232_3_tx.connect(GTX45R.P3251.rs232_1_in)
GSU25.J252.rs232_3_gnd.connect(GTX45R.P3251.rs232_1_gnd)
GSU25.J252.magnetometer_power.connect(GMU11.power)

GMU11.ground.connect(gnd, color="N")
GMU11.can_low.connect(can_bus)
GMU11.can_high.connect(can_bus)

ap_fuse = Fuse("ap", "Autopilot", 5)
ap_disconnect_splice = SpliceNode("AP Disconnect", label="AP Disconnect")
roll_servo = GSA28("Roll Servo")
roll_trim = RayAllanTrim("Roll Trim")
pitch_servo = GSA28("Pitch Servo")
pitch_trim = RayAllanTrim("Pitch Trim")
yaw_servo = GSA28("Yaw Servo")

GSA28.ground.connect(gnd)
GSA28.can_high.connect(can_bus)
GSA28.can_low.connect(can_bus)
GSA28.power.connect(ap_fuse)
GSA28.disconnect.connect(ap_disconnect_splice)

roll_servo.trim_in_1.connect(GAD27.J272.trim_out_1)
roll_servo.trim_in_2.connect(GAD27.J272.trim_out_2)
roll_servo.trim_out_1.connect(roll_trim.trim_1)
roll_servo.trim_out_2.connect(roll_trim.trim_2)

pilot_stick.ap_disconnect.connect(ap_disconnect_splice)
copilot_stick.ap_disconnect.connect(ap_disconnect_splice)

GEA24.J244.gp2_high.connect(roll_trim.excitation)
GEA24.J244.gp2.connect(roll_trim.position)
GEA24.J244.gp2_low.connect(roll_trim.ground)

GEA24.J244.gp1_high.connect(pitch_trim.excitation)
GEA24.J244.gp1.connect(pitch_trim.position)
GEA24.J244.gp1_low.connect(pitch_trim.ground)


gsu25 = GSU25("GSU 25")
oat_probe = OATProbe("OAT Probe")
gtx45r = GTX45R("GTX45R")
gmu11 = GMU11("GMU 11")
gea24 = GEA24("GEA24")

harness = Harness("Avionics Harness")
