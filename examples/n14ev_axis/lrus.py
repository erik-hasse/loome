from loome.components import (
    ACKE04,
    LEMO,
    SDSECU,
    Engine4Cyl,
    FlyLedsEssentialsController,
    PHAviationFlapMotor,
    RayAllanTrim,
    Stick,
    USBPort,
)
from loome.components.axis import GDU116B, GDU116NC
from loome.components.garmin import (
    G5,
    GAD27,
    GAP2620,
    GCO14,
    GDL51R,
    GEA24,
    GMC507,
    GMU11,
    GSA28,
    GSU25,
    GTP59,
    GTX45R,
    ConfigModule,
    GSA28RollServo,
    GTR205xR,
)
from loome.constants import Axis

gsu25 = GSU25("GSU 25C - Air Data")
gtp59 = GTP59("GTP 59 - OAT Probe")
gmu11 = GMU11("GMU 11 - Magnetometer")
gsa28_roll = GSA28RollServo("GSA 28 - Roll Servo")
gmc507 = GMC507("GMC 507 - AP Controller")
gsa28_pitch = GSA28("GSA 28 - Pitch Servo", axis=Axis.PITCH)
gsa28_yaw = GSA28("GSA 28 - Yaw Servo", axis=Axis.YAW)
gdl51r = GDL51R("GDL 51R - Sirius XM")
gtr205xr = GTR205xR("GTR 205xR - Com Radio", com_id=2)
gad27 = GAD27("GAD 27 - Flap & Light Controller")

roll_trim = RayAllanTrim("Roll Trim")
pitch_trim = RayAllanTrim("Pitch Trim")
gap26 = GAP2620("GAP 26-20 - Regulated Pitot Heat")
gtx45r = GTX45R("GTX 45R - Transponder")
gtx_usb_config = USBPort("GTX45R USB Config")

g5 = G5("G5 - Backup Instrument")
gea24 = GEA24("GEA24B - Engine Indication")


pilot_stick = Stick("Pilot Stick")
copilot_stick = Stick("Copilot Stick")

pilot_lemo = LEMO("Pilot Lemo")
copilot_lemo = LEMO("Copilot Lemo")

flap_motor = PHAviationFlapMotor("Flap Motor")

elt = ACKE04("ACK E-04 ELT")
gco14 = GCO14("GCO14 - CO Sensor")

engine = Engine4Cyl("IO390-EXP119")
sds_ecu = SDSECU()

flyleds_controller = FlyLedsEssentialsController("FlyLeds Essentials Controller")

pfd = GDU116NC("GDU 116NC - PFD, Nav/Com")
pfd_config = ConfigModule("GDU 116NC Config")
mfd = GDU116B("GDU 116B - MFD")
mfd_config = ConfigModule("GDU 116B Config")
