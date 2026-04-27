from loome.components import LEMO, TRS, RayAllanTrim, Stick
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

gtn650xi = GTN650Xi("GTX 650Xi")
gad29 = GAD29C("GAD 29")
pfd = GDU460("GDU 460 PFD", mode="PFD")
mfd = GDU460("GDU 460 MFD", mode="MFD")
g5 = G5("G5")
gea24 = GEA24("GEA24")


pilot_stick = Stick("Pilot Stick")
copilot_stick = Stick("Copilot Stick")

pilot_lemo = LEMO("Pilot Lemo")
copilot_lemo = LEMO("Copilot Lemo")
music_in = TRS("Music In")
