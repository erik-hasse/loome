from loome.components import (
    ACKE04,
    LEMO,
    SDSECU,
    TRS,
    AithreShield3,
    Engine4Cyl,
    Fan,
    PHAviationFlapMotor,
    RayAllanTrim,
    Stick,
    USBPort,
)
from loome.components.garmin import (
    G5,
    GAD27,
    GAD29C,
    GAP2620,
    GDL51R,
    GDU460,
    GEA24,
    GMA245,
    GMC507,
    GMU11,
    GSA28,
    GSU25,
    GTP59,
    GTR20,
    GTX45R,
    ConfigModule,
    GSA28RollServo,
)
from loome.components.gtn650 import GTN650Xi
from loome.constants import Axis

gsu25 = GSU25("GSU 25 - Air Data")
gtp59 = GTP59("GTP 59 - OAT Probe")
gmu11 = GMU11("GMU 11 - Magnetometer")
gsa28_roll = GSA28RollServo("GSA 28 - Roll Servo")
gmc507 = GMC507("GMC 507 - AP Controller")
gsa28_pitch = GSA28("GSA 28 - Pitch Servo", axis=Axis.PITCH)
gsa28_yaw = GSA28("GSA 28 - Yaw Servo", axis=Axis.YAW)
gdl51r = GDL51R("GDL 51R - Sirius XM")
gma245 = GMA245("GMA 245 - Audio Panel")
gtr20 = GTR20("GTR 20 - Com Radio")
gad27 = GAD27("GAD 27 - Flap & Light Controller")

roll_trim = RayAllanTrim("Roll Trim")
pitch_trim = RayAllanTrim("Pitch Trim")
gap26 = GAP2620("GAP 26-20 - Regulated Pitot Heat")
gtx45r = GTX45R("GTX 45R - Transponder")
gtx_usb_config = USBPort("GTX45R USB Config")

gtn650xi = GTN650Xi("GTN 650Xi - GPS/NAV/COM")
gtn650_config = ConfigModule("GTN 650Xi Config")
gtn650_fan = Fan("GTN 650Xi Fan")
gad29 = GAD29C("GAD 29 - ARINC Adapter")
pfd = GDU460("GDU 460 PFD", mode="PFD")
gdu460_config = ConfigModule("GDU 460 Config")
mfd = GDU460("GDU 460 MFD", mode="MFD")
g5 = G5("G5 - Backup Instrument")
gea24 = GEA24("GEA24 - Engine Indication")


pilot_stick = Stick("Pilot Stick")
copilot_stick = Stick("Copilot Stick")

pilot_lemo = LEMO("Pilot Lemo")
copilot_lemo = LEMO("Copilot Lemo")
music_in = TRS("Music In")

flap_motor = PHAviationFlapMotor("Flap Motor")

elt = ACKE04("ACK E-04 ELT")
co2_sensor = AithreShield3("Aithre Shield CO2 Sensor")

engine = Engine4Cyl("IO390-EXP119")
sds_ecu = SDSECU
