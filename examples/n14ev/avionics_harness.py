from examples.n14ev.lights import (
    cabin_lights,
    left_landing_lights,
    left_taxi_lights,
    master_caution,
    master_warning,
    right_landing_lights,
    right_taxi_lights,
)
from examples.n14ev.lrus import (
    co2_sensor,
    copilot_lemo,
    copilot_stick,
    elt,
    engine,
    flap_motor,
    g5,
    gad27,
    gad29,
    gap26,
    gdl51r,
    gdu460_config,
    gea24,
    gma245,
    gmc507,
    gmu11,
    gsu25,
    gtn650_config,
    gtn650_fan,
    gtn650xi,
    gtr20,
    gtx45r,
    gtx_usb_config,
    mfd,
    music_in,
    oat_probe,
    pfd,
    pilot_lemo,
    pilot_stick,
    pitch_servo,
    pitch_trim,
    roll_servo,
    roll_trim,
    sds_ecu,
    yaw_servo,
)
from examples.n14ev.power import avionics_block_1, avionics_block_2, avionics_block_3, gnd, main_block
from examples.n14ev.sensors import fuel_pressure, left_fuel, manifold_pressure, oil_pressure, oil_temp, right_fuel
from examples.n14ev.switches import (
    backlight_rheo,
    cabin_light_rheo,
    flaps_down,
    flaps_up,
    landing_light_switch,
    taxi_light_switch,
    toga,
    wig_wag,
)
from loome import CanBusLine, Fuse, Harness, Shield

# Page 2
with gsu25.J251 as c:
    c.ground_a >> gnd
    c.aircraft_power_1 >> avionics_block_1.GSU25
    c.aircraft_power_2 >> avionics_block_2.GSU25
    (c.rs232 >> pfd.P4601.rs232).notes("Not Configured")

with gsu25.J252 as c:
    with Shield(drain=True, drain_remote=True):
        c.oat_probe_power >> oat_probe.oat_probe_power
        c.oat_probe_high >> oat_probe.oat_probe_sense
        c.oat_probe_low >> oat_probe.oat_probe_low
    c.rs232_3 >> gtx45r.P3251.rs232_1


with gmu11.J441 as c:
    c.aircraft_power_1 >> avionics_block_1.GMU11
    c.aircraft_power_2 >> avionics_block_2.GMU11
    c.ground >> gnd

# Page 3
with roll_servo.J281 as c:
    c.ground >> gnd
    c.power >> avionics_block_3.GSA28_roll
    c.trim_in_1 >> gad27.J272.roll_trim_out_1
    c.trim_in_2 >> gad27.J272.roll_trim_out_2
    c.trim_out_1 >> roll_trim.trim_1
    c.trim_out_2 >> roll_trim.trim_2

with gmc507.J7001 as c:
    c.aircraft_power_1 >> avionics_block_1.GMC507
    c.aircraft_power_2 >> avionics_block_2.GMC507
    c.ground >> gnd
    c.remote_go_around >> toga.no2

# Page 4
with pitch_servo.J281 as c:
    c.ground >> gnd
    c.power >> avionics_block_3.GSA28_pitch
    c.trim_in_1 >> gad27.J272.pitch_trim_out_1
    c.trim_in_2 >> gad27.J272.pitch_trim_out_2
    c.trim_out_1 >> pitch_trim.trim_1
    c.trim_out_2 >> pitch_trim.trim_2

pilot_stick.ap_disconnect >> copilot_stick.ap_disconnect
copilot_stick.ap_disconnect >> pitch_servo.J281.disconnect
pitch_servo.J281.disconnect >> yaw_servo.J281.disconnect
yaw_servo.J281.disconnect >> roll_servo.J281.disconnect

(toga.no1 >> gtn650xi.P1001[37]).notes("Reconfigure to Remote Go Around")

# Page 5

with yaw_servo.J281 as c:
    c.ground >> gnd
    c.power >> avionics_block_3.GSA28_yaw

# Page 6

with gdl51r as c:
    c.aircraft_power >> avionics_block_3.GDL51R
    c.ground >> gnd
    with Shield(drain_remote=True):
        c.music_out_left >> gma245.J2402.music_2_in_left
        c.music_out_common >> gma245.J2402.music_2_in_low
        c.music_out_right >> gma245.J2402.music_2_in_right

    c.rs232_1 >> pfd.P4602.rs232_1
    c.rs232_2 >> mfd.P4602.rs232_4

# Page 7
with gma245.P2401 as c:
    with Shield(drain=True):
        c.pilot_mic_key_in >> pilot_stick.push_to_talk
        c.pilot_mic_audio_in_high >> pilot_lemo.mic_high
        c.pilot_mic_audio_in_low >> pilot_lemo.mic_low

with gma245.J2402 as c:
    with Shield(drain=True):
        c.pilot_headset_audio_out_left >> pilot_lemo.audio_left
        c.pilot_headset_audio_out_right >> pilot_lemo.audio_right
        c.pilot_headset_audio_out_low >> pilot_lemo.ground

    with Shield(drain=True):
        c.copilot_headset_audio_out_left >> copilot_lemo.audio_left
        c.copilot_headset_audio_out_right >> copilot_lemo.audio_right
        c.copilot_headset_audio_out_low >> copilot_lemo.ground

    with Shield(drain=True):
        c.copilot_mic_key_in >> copilot_stick.push_to_talk
        c.copilot_mic_audio_in_high >> copilot_lemo.mic_high
        c.copilot_mic_audio_in_low >> copilot_lemo.mic_low

    # Page 8
    with Shield(drain=True):
        c.music_1_in_left >> music_in.tip
        c.music_1_in_right >> music_in.ring
        c.music_1_in_low >> music_in.sleeve

    c.aircraft_power_a >> avionics_block_3.GMA245
    c.aircraft_power_b >> avionics_block_3.GMA245
    c.ground_a >> gnd
    c.ground_b >> gnd

    c.lighting_bus_high >> c.lighting_bus_14v_high_28v_low
    c.lighting_bus_low.local_ground()

    c.com_swap >> pilot_stick.com_swap
    c.com_swap >> copilot_stick.com_swap

    c.play_key >> pilot_stick.replay
    c.play_key >> copilot_stick.replay


# Page 9
with gma245.P2401 as c:
    with Shield(drain=True):
        c.com_1_audio_in_high >> gtn650xi.P1003.com_audio_hi
        c.com_1_audio_low >> gtn650xi.P1003.com_audio_lo

    with Shield(drain=True):
        c.com_1_audio_low >> gtn650xi.P1003.mic_audio_in_lo
        c.com_1_mic_audio_out_high >> gtn650xi.P1003.com_mic_1_audio_in_hi
        c.com_1_mic_key_out >> gtn650xi.P1003.com_mic_1_key
    c.com_1_mic_key_out >> gtr20.J2001.tx_interlock_in

    with Shield(drain=True):
        c.nav_1_audio_in_high >> gtn650xi.P1004.vor_loc_audio_out_hi
        c.nav_1_audio_in_low >> gtn650xi.P1004.vor_loc_audio_out_lo

    with Shield(drain=True):
        c.alert_3_4_aux_3_audio_in_low >> gtn650xi.P1001.audio_out_lo
        c.alert_4_audio_in_high >> gtn650xi.P1001.audio_out_hi

    with Shield(drain=True):
        c.com_2_audio_in_high >> gtr20.J2001.receiver_out_high
        c.com_2_audio_low >> gtr20.J2001.receiver_audio_low

    with Shield(drain=True):
        c.com_2_audio_low >> gtr20.J2001.pilot_mic_low
        c.com_2_mic_audio_out_high >> gtr20.J2001.pilot_mic_in
        c.com_2_mic_key_out >> gtr20.J2001.pilot_ptt

    with Shield(drain=True):
        c.alert_1_audio_in_high >> pfd.P4602.mono_audio_out_high
        c.alert_1_audio_in_low >> pfd.P4602.mono_audio_out_low


# Page 10

with gtr20.J2001 as c:
    c.ground >> gnd
    c.aircraft_power >> avionics_block_3.GTR20

# Page 11
with gad27.J271 as c:
    c.aircraft_power >> avionics_block_1.GAD27
    c.ground >> gnd
    c.flap_up_1 >> flaps_up.no
    c.flap_down_1 >> flaps_down.no
    c.pilot_pitch_trim_up >> pilot_stick.trim_up
    c.pilot_pitch_trim_down >> pilot_stick.trim_down
    c.pilot_roll_trim_left >> pilot_stick.trim_left
    c.pilot_roll_trim_right >> pilot_stick.trim_right
    c.copilot_pitch_trim_up >> copilot_stick.trim_up
    c.copilot_pitch_trim_down >> copilot_stick.trim_down
    c.copilot_roll_trim_left >> copilot_stick.trim_left
    c.copilot_roll_trim_right >> copilot_stick.trim_right

    c.discrete_in_7 >> pilot_stick.frequency_swap
    c.discrete_in_7 >> copilot_stick.frequency_swap

    # c.discrete_in_1 >> alt_regulator
    # c.discrete_in_2 >> monkworkz_active

    # Page 12
    c.light_1_switch >> landing_light_switch.no
    c.light_2_switch >> taxi_light_switch.no
    c.alternating_flash_on >> wig_wag.no

    c.output_12v >> backlight_rheo.power
    c.lighting_bus_gnd >> backlight_rheo.ground
    c.lighting_control_in_1 >> backlight_rheo.out

    c.output_12v >> cabin_light_rheo.power
    c.lighting_bus_gnd >> cabin_light_rheo.ground
    c.lighting_control_in_2 >> cabin_light_rheo.out

    c.pwm_lighting_1 >> cabin_lights.power

# Page 13
with gad27.J272 as c:
    c.pitch_trim_power_gnd >> gnd
    c.roll_trim_power_gnd >> gnd

with gad27.TB273 as c:
    c.keep_alive_power_in >> avionics_block_2.GAD27
    c.keep_alive_power_out >> gad27.J272.pitch_trim_power_in
    c.keep_alive_power_out >> gad27.J272.roll_trim_power_in

    # Page 14
    (c.light_1_power >> main_block.landing_lights).gauge(18)
    (c.light_2_power >> main_block.taxi_lights).gauge(18)

    (c.flap_power_in >> main_block.flaps).gauge(18)
    (c.flap_power_gnd >> gnd).gauge(18)
    (c.flap_power_out_1 >> flap_motor.extend).gauge(18)
    (c.flap_power_out_2 >> flap_motor.retract).gauge(18)

    (c.light_1_output >> left_landing_lights.power).gauge(18)
    (c.light_1_output >> right_landing_lights.power).gauge(18)

    (c.light_2_output >> left_taxi_lights.power).gauge(18)
    (c.light_2_output >> right_taxi_lights.power).gauge(18)


# Page 15
gad27.J271.dc_lighting_1 >> mfd.P4602.lighting_bus_high_14V
mfd.P4602.lighting_bus_high_14V >> pfd.P4602.lighting_bus_high_14V
pfd.P4602.lighting_bus_high_14V >> gtn650xi.P1001.lighting_bus_1_hi
gtn650xi.P1001.lighting_bus_1_hi >> gmc507.J7001.lighting_bus_high
gmc507.J7001.lighting_bus_high >> gma245.J2402.lighting_bus_high

# TODO Add a switch
gap26.power >> main_block.pitot_heat
gap26.ground >> gnd

# Page 16
with gtx45r.P3251 as c:
    c.power_config.local_ground()
    c.ground_1 >> gnd
    c.ground_2 >> gnd
    c.power_control.local_ground()

    c.aircraft_power_1a >> avionics_block_1.GTX45R
    c.aircraft_power_1b >> avionics_block_1.GTX45R
    c.aircraft_power_2a >> avionics_block_2.GTX45R
    c.aircraft_power_2b >> avionics_block_2.GTX45R

    c.usb_vbus_power >> gtx_usb_config.power
    c.usb_ground >> gtx_usb_config.ground
    c.usb_data_high >> gtx_usb_config.data_high
    c.usb_data_low >> gtx_usb_config.data_low

    (c.rs232_2 >> pfd.P4602.rs232_3).notes("Connext Format 4, 115200 baud")
    (c.rs232_3 >> gtn650xi.P1001.rs232_4).notes("ADS-B+ GPS")

# Page 17
with gtx45r.P3252 as c:
    (c.rs232 >> mfd.P4602.rs232_2).notes("Connext Format 4, 115200 baud")
    c.ethernet_out_1 >> gtn650xi.P1002.ethernet_in_1
    c.ethernet_in_1 >> gtn650xi.P1002.ethernet_out_1

# Page 18
with gtn650xi.P1004 as c:
    c.aircraft_power_a >> avionics_block_3.GTN650_nav
    c.aircraft_power_b >> avionics_block_3.GTN650_nav

with gtn650xi.P1001 as c:
    c.aircraft_power_a >> avionics_block_3.GTN650_nav
    c.aircraft_power_b >> avionics_block_3.GTN650_nav

    c.config_module_power >> gtn650_config.power
    c.config_module_gnd >> gtn650_config.ground
    c.config_module_data >> gtn650_config.data
    c.config_module_clock >> gtn650_config.clock

with gtn650xi.P1003 as c:
    c.aircraft_power_a >> avionics_block_3.GTN650_com
    c.aircraft_power_b >> avionics_block_3.GTN650_com
    c.aircraft_power_c >> avionics_block_3.GTN650_com

# Page 19
with gtn650xi.P1001 as c:
    (c.arinc_429_in_1 >> gad29.J292.arinc_tx_1_1).notes("GDU Format 2")
    (c.arinc_429_out_1 >> gad29.J292.arinc_rx_1).notes("Low + Garmin 429, SDI - LNAV1")

    (c.rs232_2 >> pfd.P4602.rs232_4).notes("Input & Output Connext Format 2, 38400 baud")
    (c.rs232_3 >> pfd.P4602.rs232_5).notes("Input & Output MapMX Format 2")


with gtn650xi.P1004 as c:
    c.vor_ils_arinc_429_out >> gad29.J292.arinc_rx_2

# Page 20
with gtn650xi.P1001 as c:
    c.fan >> gtn650_fan.control
    c.aircraft_gnd_a >> gnd
    c.aircraft_gnd_b >> gnd
    c.lighting_bus_1_lo.local_ground()

with gtn650xi.P1003 as c:
    c.aircraft_gnd_a >> gnd
    c.aircraft_gnd_b >> gnd
    c.aircraft_gnd_c >> gnd

with gtn650xi.P1004 as c:
    c.aircraft_gnd_c >> gnd
    c.aircraft_gnd_d >> gnd
    c.aircraft_gnd_e >> gnd

# Page 21

with gad29.J291 as c:
    c.aircraft_power_1 >> avionics_block_1.GAD29
    c.aircraft_power_2 >> avionics_block_1.GAD29
    c.ground >> gnd

# Page 22

# No additional pins

# Page 23

with pfd.P4602 as c:
    c.ground_1 >> gnd
    c.aircraft_power_1 >> avionics_block_1.PFD
    c.aircraft_power_2 >> avionics_block_1.PFD

    c.config_module_power_out >> gdu460_config.power
    c.config_module_ground >> gdu460_config.ground
    c.config_module_data >> gdu460_config.data
    c.config_module_clock >> gdu460_config.clock

# Page 24
with mfd.P4602 as c:
    c.ground_1 >> gnd
    c.aircraft_power_1 >> avionics_block_1.MFD
    c.aircraft_power_2 >> avionics_block_1.MFD
    (c.rs232_1 >> gea24.J241.rs232).ground(False)

# Page 25

with g5.J51 as c:
    c.ground >> gnd
    (c.aircraft_power_1 >> avionics_block_1.G5).notes("Lightning Protection Module")
    c.aircraft_power_2 >> avionics_block_2.G5
    c.can.note("Lightning Protection Module")

# Page 26
with gea24.J241 as c:
    c.ground >> gnd
    c.aircraft_power_1 >> avionics_block_1.GEA24
    c.aircraft_power_2 >> avionics_block_2.GEA24

# Page 27
with gea24.J242 as c:
    c.egt1 >> engine.Cylinder1.egt
    c.cht1 >> engine.Cylinder1.cht
    c.egt2 >> engine.Cylinder2.egt
    c.cht2 >> engine.Cylinder2.cht
    c.egt3 >> engine.Cylinder3.egt
    c.cht3 >> engine.Cylinder3.cht
    c.egt4 >> engine.Cylinder4.egt
    c.cht4 >> engine.Cylinder4.cht

# Page 28
with gea24.J243 as c:
    (c.fuel_pressure_5v >> fuel_pressure.gpio).drain()
    with Shield(drain=True, drain_remote=True):
        c.rpm_1.signal >> sds_ecu.tach
    (c.oil_pressure_5v >> oil_pressure.gpio).drain()
    (c.manifold_pressure_5v >> manifold_pressure.gpio).drain()
    with Shield(drain=True, drain_remote=True):
        c.fuel_flow.signal >> sds_ecu.fuel_flow

    with Shield(drain=True):
        c.oil_temp_high >> oil_temp.high
        c.oil_temp_low >> oil_temp.low

    c.shunt_1_high >> Fuse("Alternator Side", amps=1)
    c.shunt_1_low >> Fuse("Load Side", amps=1)

# Page 29

with gea24.J244 as c:
    c.fuel_quantity_1.signal >> left_fuel.power
    c.fuel_quantity_2.signal >> right_fuel.power
    (c.gp1 >> pitch_trim.position).drain()
    (c.gp2 >> roll_trim.position).drain()
    (c.gp3 >> flap_motor.position).drain()

    c.volts_1 >> Fuse("Main Bus", amps=1)
    c.volts_2 >> Fuse("Engine Bus", amps=1)

    c.discrete_in_4 >> gap26.signal
    c.discrete_out_1 >> master_warning.power
    c.discrete_out_2 >> master_caution.power

# Page 30
with gea24.J243 as c:
    with Shield(drain=True):
        c.gp_5v_out >> co2_sensor.power
        c.gp6_high >> co2_sensor.signal
        c.gp_gnd_1 >> co2_sensor.ground

    c.gp6_low.local_ground()

# Page 31

CanBusLine(
    name="CAN Bus",
    devices=[
        gmu11.J441,
        roll_servo.J281,
        mfd.P4602,
        gad29.J291,
        gtr20.J2001,
        g5.J51,
        gmc507.J7001,
        gma245.P2401,
        pfd.P4602,
        gea24.J241,
        gad27.J271,
        gsu25.J251,
        pitch_servo.J281,
        yaw_servo.J281,
    ],
)

# Page 32

with elt.DIN as c:
    with Shield(drain_remote=True):
        c.remote_switch >> avionics_block_3.elt
        c.ground >> gnd
        c.elt_rx >> gtn650xi.P1001.rs232_1.tx

    # TODO: c.rs232_test

harness = Harness("Avionics Harness", length_unit="in")
