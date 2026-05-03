from examples.n14ev.power import gnd
from loome.components import LED, FlyLedsEssentials, FlyLedsSevenStars

cabin_lights = LED("Cabin Lights")
cabin_lights.ground >> gnd

left_7_stars = FlyLedsSevenStars("Left 7 Stars")
left_7_stars.ground >> gnd
right_7_stars = FlyLedsSevenStars("Right 7 Stars")
right_7_stars.ground >> gnd

left_pos_strobe = FlyLedsEssentials("Left Position & Strobe")
right_pos_strobe = FlyLedsEssentials("Right Position & Strobe")
tail_light = LED("Tail Light")


master_warning = LED("Master Warning")
master_warning.ground >> gnd

master_caution = LED("Master Caution")
master_caution.ground >> gnd
