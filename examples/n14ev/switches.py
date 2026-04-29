from examples.n14ev.power import gnd
from loome.components.switches import DPST, SPST, Rheostat

toga = DPST("TO/GA", momentary=True, render=True)
toga.com1 >> toga.com2
toga.com1 >> gnd

flaps_up = SPST("Flaps Up", momentary=True)
flaps_up.com >> gnd

flaps_down = SPST("Flaps Down", momentary=True)
flaps_down.com >> gnd

landing_light_switch = SPST("Landing Lights")
landing_light_switch.com >> gnd

taxi_light_switch = SPST("Taxi Lights")
taxi_light_switch.com >> gnd

wig_wag = SPST("Wig Wag Lights")
wig_wag.com >> gnd

backlight_rheo = Rheostat("Backlight")
cabin_light_rheo = Rheostat("Cabin Light")
