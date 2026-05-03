from examples.n14ev.lights import left_7_stars, left_pos_strobe
from examples.n14ev.lrus import flyleds_controller, gad27, gmu11, gsa28_roll, gsa28_yaw, mfd
from examples.n14ev.power import avionics_block_1, avionics_block_2, avionics_block_3, gnd
from examples.n14ev.switches import landing_light_switch
from loome import Disconnect

left_wing_root = Disconnect("Wing Root")

left_wing_root_items = [
    (gsa28_roll.J281.can, mfd.P4602.can),
    (gsa28_roll.J281.power, avionics_block_3.GSA28_roll),
    (gsa28_roll.J281.ground, gnd),
    (gsa28_roll.J281.trim_in_1, gad27.J272.roll_trim_out_1),
    (gsa28_roll.J281.trim_in_2, gad27.J272.roll_trim_out_2),
    (gsa28_roll.J281.disconnect, gsa28_yaw.J281.disconnect),
    (gmu11.J441.aircraft_power_1, avionics_block_1.GMU11),
    (gmu11.J441.aircraft_power_2, avionics_block_2.GMU11),
    (gmu11.J441.ground, gnd),
    # (flyleds_controller.left_shield, left_pos_strobe.position_neg),
    (flyleds_controller.left_position_pos, left_pos_strobe.position_pos),
    (flyleds_controller.left_strobe_neg, left_pos_strobe.strobe_neg),
    (flyleds_controller.left_strobe_pos, left_pos_strobe.strobe_pos),
    (landing_light_switch.no1, left_7_stars.taxi),
    (gad27.TB273.light_1_output, left_7_stars.landing),
]
for left, right in left_wing_root_items:
    left_wing_root.between(left, right)
