from loome.components.switches import DPST, SPST, DPOnOnOnSwitch, OnOffOnSwitch, Rheostat

toga = DPST("TO/GA", momentary=True, render=True)

flaps = OnOffOnSwitch("Flap Switch", momentary_up=True, momentary_down=True)

landing_light_switch = DPOnOnOnSwitch("Landing Lights", render=True, labels=("Off", "Taxi", "Landing"))
nav_strobe_switch = DPOnOnOnSwitch("Nav & Strobe Lights", render=True, labels=("Off", "Nav", "Nav + Strobe"))

wig_wag = SPST("Wig Wag Lights")

backlight_rheo = Rheostat("Backlight")
cabin_light_rheo = Rheostat("Cabin Light")

pitot_heat_switch = SPST("Pitot Heat")
