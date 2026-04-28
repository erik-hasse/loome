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

gsu25 = GSU25("GSU 25")
oat_probe = GTP59("GTP59")
gmu11 = GMU11("GMU 11")
roll_servo = GSA28RollServo("Roll Servo")
gmc507 = GMC507("AP Controller")
pitch_servo = GSA28("Pitch Servo", axis=Axis.PITCH)
yaw_servo = GSA28("Yaw Servo", axis=Axis.YAW)
gdl51r = GDL51R("GDL 51R")
gma245 = GMA245("GMA 245")
gtr20 = GTR20("GTR 20")
gad27 = GAD27("GAD 27")

roll_trim = RayAllanTrim("Roll Trim")
pitch_trim = RayAllanTrim("Pitch Trim")
gap26 = GAP2620("GAP 26-20")
gtx45r = GTX45R("GTX 45R")
gtx_usb_config = USBPort("GTX45R USB Config")

gtn650xi = GTN650Xi("GTX 650Xi")
gtn650_config = ConfigModule("GTN 650Xi Config")
gtn650_fan = Fan("GTN 650Xi Fan")
gad29 = GAD29C("GAD 29")
pfd = GDU460("GDU 460 PFD", mode="PFD")
gdu460_config = ConfigModule("GDU 460 Config")
mfd = GDU460("GDU 460 MFD", mode="MFD")
g5 = G5("G5")
gea24 = GEA24("GEA24")


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
