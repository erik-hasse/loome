from examples.n14ev.power import gnd
from loome.components.switches import DPST, SPST, DP3TProgressive, OnOffOnSwitch, Rheostat

toga = DPST("TO/GA", momentary=True, render=True)
toga.com1 >> toga.com2
toga.com1 >> gnd

flaps = OnOffOnSwitch("Flap Switch", momentary_up=True, momentary_down=True)
flaps.com >> gnd

landing_light_switch = DP3TProgressive("Landing Lights", render=True)

wig_wag = SPST("Wig Wag Lights")
wig_wag.com >> gnd

backlight_rheo = Rheostat("Backlight")
cabin_light_rheo = Rheostat("Cabin Light")
