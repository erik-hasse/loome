from examples.n14ev.power import gnd
from loome.components import LED

cabin_lights = LED("Cabin Lights")
cabin_lights.ground >> gnd

left_landing_lights = LED("Landing Lights Left")
left_landing_lights.ground >> gnd
right_landing_lights = LED("Landing Lights Right")
right_landing_lights.ground >> gnd
left_taxi_lights = LED("Taxi Lights Left")
left_taxi_lights.ground >> gnd
right_taxi_lights = LED("Taxi Lights Right")
right_taxi_lights.ground >> gnd

master_warning = LED("Master Warning")
master_warning.ground >> gnd

master_caution = LED("Master Caution")
