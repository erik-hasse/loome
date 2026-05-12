from examples.n14ev.lights import left_7_stars, left_pos_strobe, right_7_stars, right_pos_strobe
from examples.n14ev.lrus import (
    flyleds_controller,
    gad27,
    gap26,
    gea24,
    gmu11,
    gsa28_roll,
    gsa28_yaw,
    gsu25,
    gtp59,
    mfd,
    roll_trim,
)
from examples.n14ev.power import avionics_block_1, avionics_block_2, avionics_block_3, gnd
from examples.n14ev.switches import landing_light_switch, pitot_heat_switch
from loome import Disconnect

right_wing_root_12_pin = Disconnect("Right Wing Root 12 pin")
right_wing_root_8_pin = Disconnect("Right Wing Root 8 pin")
right_wing_handshake = Disconnect("Right Wing Handshake")
(right_wing_handshake.between(gad27.TB273.light_2_output, right_7_stars.landing),)

right_wing_12_items = [
    # Trim
    (gsa28_roll.J281.trim_in_1, gad27.J272.roll_trim_out_1),
    (gsa28_roll.J281.trim_in_2, gad27.J272.roll_trim_out_2),
    # Power
    (gsa28_roll.J281.power, avionics_block_3.GSA28_roll),
    (gsa28_roll.J281.ground, gnd),
    (gmu11.J441.aircraft_power_1, avionics_block_1.GMU11),
    (gmu11.J441.aircraft_power_2, avionics_block_2.GMU11),
    (gmu11.J441.ground, gnd),
    # Lights
    (flyleds_controller.right_position_pos, right_pos_strobe.position_pos),
    (flyleds_controller.right_strobe_neg, right_pos_strobe.strobe_neg),
    (flyleds_controller.right_strobe_pos, right_pos_strobe.strobe_pos),
    (landing_light_switch.no1, right_7_stars.taxi),
]
right_wing_8_items = [
    # Signal
    (gsa28_roll.J281.disconnect, gsa28_yaw.J281.disconnect),
    # Shielded
    (gea24.J244.gp2, roll_trim.position),
    (gsa28_roll.J281.can, mfd.P4602.can),
]
for left, right in right_wing_8_items:
    right_wing_root_8_pin.between(left, right)

for left, right in right_wing_12_items:
    right_wing_root_12_pin.between(left, right)


left_wing_root = Disconnect("Left Wing Root")
left_wing_handshake = Disconnect("Left Wing Handshake")
left_wing_handshake.between(gad27.TB273.light_1_output, left_7_stars.landing)
left_wing_handshake.between(pitot_heat_switch.no, gap26.power)
left_wing_handshake.between(gap26.ground, gnd)

left_wing_root_items = [
    # Lights
    (flyleds_controller.left_position_pos, left_pos_strobe.position_pos),
    (flyleds_controller.left_strobe_neg, left_pos_strobe.strobe_neg),
    (flyleds_controller.left_strobe_pos, left_pos_strobe.strobe_pos),
    (landing_light_switch.no1, left_7_stars.taxi),
    # Pitot signal
    (gea24.J244.discrete_in_4, gap26.signal),
    # OAT Probe
    (gsu25.J252.oat_probe_power, gtp59.oat_probe_power),
    (gsu25.J252.oat_probe_high, gtp59.oat_probe_sense),
    (gsu25.J252.oat_probe_low, gtp59.oat_probe_low),
]
for left, right in left_wing_root_items:
    left_wing_root.between(left, right)
