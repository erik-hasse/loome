from loome import (
    DPST,
    Bundle,
    CanBusLine,
    Fuse,
    GroundSymbol,
    Harness,
    Shield,
    SpliceNode,
)
from loome.components import RayAllanTrim, Stick
from loome.components.garmin import (
    GAD27,
    GDU460,
    GEA24,
    GMC507,
    GMU11,
    GSA28,
    GSU25,
    GTX45R,
    GSA28RollServo,
    GTN650Xi,
    OATProbe,
)
from loome.constants import Axis

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

roll_servo.J281.trim_in_1.connect(GAD27.J272.roll_trim_out_1)
roll_servo.J281.trim_in_2.connect(GAD27.J272.roll_trim_out_2)
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

# ── bundle (physical-layout topology) ────────────────────────────────────────

trunk = Bundle("Main Avionics Trunk")
panel = trunk.breakout("panel")
pedestal = trunk.breakout("pedestal", after=panel, length=24)
tail = trunk.breakout("tail", after=pedestal, length=96)
wing_L = trunk.breakout("wing_L", after=pedestal, length=72)

panel.attach(pfd.P4601, leg_length=6)
panel.attach(gsu25.J251, leg_length=6)
panel.attach(gsu25.J252, leg_length=6)
panel.attach(gnd, leg_length=2)
panel.attach(air_data_fuse, leg_length=2)
panel.attach(air_data_backup_fuse, leg_length=2)
panel.attach(ap_fuse, leg_length=2)
panel.attach(backup_splice, leg_length=1)
pedestal.attach(controller.P7001, leg_length=8)
pedestal.attach(pitch_servo.J281, leg_length=10)
pedestal.attach(yaw_servo.J281, leg_length=12)
tail.attach(gmu11.J441, leg_length=10)
tail.attach(oat_probe, leg_length=5)
tail.attach(gtx45r.P3251, leg_length=8)
wing_L.attach(roll_servo.J281, leg_length=12)

main_can = CanBusLine(
    "Main CAN",
    devices=[gsu25.J251, roll_servo.J281, gmu11.J441],
)

# ── harness ───────────────────────────────────────────────────────────────────

harness = Harness("Avionics Harness", length_unit="in")
