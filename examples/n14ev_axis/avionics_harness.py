from examples.n14ev_axis.disconnects import (
    left_wing_handshake,
    left_wing_root,
    right_wing_handshake,
    right_wing_root_a,
    right_wing_root_b,
)
from examples.n14ev_axis.lights import (
    cabin_lights,
    left_7_stars,
    left_pos_strobe,
    master_caution,
    master_warning,
    right_7_stars,
    right_pos_strobe,
    tail_light,
)
from examples.n14ev_axis.lrus import (
    co2_sensor,
    copilot_lemo,
    copilot_stick,
    elt,
    engine,
    flap_motor,
    flyleds_controller,
    g5,
    gad27,
    gap26,
    gdl51r,
    gea24,
    gmc507,
    gmu11,
    gsa28_pitch,
    gsa28_roll,
    gsa28_yaw,
    gsu25,
    gtp59,
    gtr205xr,
    gtx45r,
    gtx_usb_config,
    mfd,
    mfd_config,
    pfd,
    pfd_config,
    pilot_lemo,
    pilot_stick,
    pitch_trim,
    roll_trim,
    sds_ecu,
)
from examples.n14ev_axis.power import (
    avionics_block_1,
    avionics_block_2,
    avionics_block_3,
    gnd,
    left_wing_gnd,
    main_block,
    right_wing_gnd,
)
from examples.n14ev_axis.sensors import fuel_pressure, left_fuel, manifold_pressure, oil_pressure, oil_temp, right_fuel
from examples.n14ev_axis.switches import (
    backlight_rheo,
    cabin_light_rheo,
    flaps,
    landing_light_switch,
    nav_strobe_switch,
    pitot_heat_switch,
    toga,
    wig_wag,
)
from loome import CanBusLine, Fuse, Harness, Shield, System

with System("AD"):
    with gsu25.J251 as c:
        c.ground_a >> gnd
        c.aircraft_power_1 >> avionics_block_1.GSU25
        c.aircraft_power_2 >> avionics_block_2.GSU25
        c.rs232 >> pfd.J1012.rs232_3

    with gsu25.J252 as c:
        with Shield(drain="block", drain_remote="block"):
            c.oat_probe_power >> gtp59.oat_probe_power
            c.oat_probe_high >> gtp59.oat_probe_sense
            c.oat_probe_low >> gtp59.oat_probe_low

    with gmu11.J441 as c:
        c.aircraft_power_1 >> avionics_block_1.GMU11
        c.aircraft_power_2 >> avionics_block_2.GMU11
        c.ground >> gnd

    (pitot_heat_switch.com >> main_block.pitot_heat).gauge(14)
    (pitot_heat_switch.no >> gap26.power).gauge(14).color("R")
    (gap26.ground >> gnd).gauge(14)
    gea24.J244.discrete_in_4 >> gap26.signal

with System("AP"):
    with gsa28_roll.J281 as c:
        c.ground >> gnd
        c.power >> avionics_block_3.GSA28_roll

    with gsa28_pitch.J281 as c:
        c.ground >> gnd
        c.power >> avionics_block_3.GSA28_pitch

    with gsa28_yaw.J281 as c:
        c.ground >> gnd
        c.power >> avionics_block_3.GSA28_yaw

    with gmc507.J7001 as c:
        c.aircraft_power_1 >> avionics_block_1.GMC507
        c.aircraft_power_2 >> avionics_block_2.GMC507
        c.ground >> gnd

    pilot_stick.ap_disconnect >> copilot_stick.ap_disconnect
    copilot_stick.ap_disconnect >> gsa28_pitch.J281.disconnect
    gsa28_pitch.J281.disconnect >> gsa28_yaw.J281.disconnect
    gsa28_yaw.J281.disconnect >> gsa28_roll.J281.disconnect

    toga.com >> gnd
    # Any one of these:
    # toga.no >> gea24.J244.discrete_in_1
    # toga.no >> gad27.J271.discrete_in_1
    # toga.no >> pfd.J1013.discrete_in_2
    toga.no >> gmc507.J7001.remote_go_around

with System("AUD"):
    with pfd.J1015 as c:
        with Shield(drain="block"):
            c.pilot_headset_left >> pilot_lemo.audio_left
            c.pilot_headset_right >> pilot_lemo.audio_right
            c.pilot_headset_ground >> pilot_lemo.ground

        with Shield(drain="block"):
            c.copilot_headset_left >> copilot_lemo.audio_left
            c.copilot_headset_right >> copilot_lemo.audio_right
            c.copilot_headset_ground >> copilot_lemo.ground

        with Shield(drain="block"):
            c.mic_1_in >> pilot_lemo.mic_high
            c.mic_1_low >> pilot_lemo.mic_low
            c.mic_1_ptt >> pilot_stick.push_to_talk

        with Shield(drain="block"):
            c.mic_2_in >> copilot_lemo.mic_high
            c.mic_2_low >> copilot_lemo.mic_low
            c.mic_2_ptt >> copilot_stick.push_to_talk

    with gdl51r as c:
        c.aircraft_power >> avionics_block_3.GDL51R
        c.ground >> gnd
        c.rs232_1 >> pfd.J1012.rs232_4
        c.rs232_2 >> mfd.J1012.rs232_1
        with Shield(drain_remote="block"):
            c.music_out_left >> pfd.J1015.stereo_music_in_left
            c.music_out_right >> pfd.J1015.stereo_music_in_right
            c.music_out_common >> pfd.J1015.stereo_music_in_low

    with pfd.J1013 as c:
        c.discrete_in_1 >> pilot_stick.com_swap
        c.discrete_in_1 >> copilot_stick.com_swap

        c.discrete_in_2 >> pilot_stick.replay
        c.discrete_in_2 >> copilot_stick.replay


with System("COM"):
    with gtr205xr as c:
        c.hsdb >> pfd.J1012.hsdb_3
        c.ground_1 >> gnd
        c.ground_2 >> gnd
        c.ground_3 >> gnd
        c.power_1 >> avionics_block_3.GTR205xR
        c.power_2 >> avionics_block_3.GTR205xR
        c.power_3 >> avionics_block_3.GTR205xR

        with Shield(drain="block"):
            pfd.J1015.external_com_audio_in >> c.com_audio_out_high
            pfd.J1015.external_com_audio_in_low >> c.com_audio_out_low

        with Shield(drain="block"):
            pfd.J1015.external_com_mic_audio_out >> c.mic_1_audio_in_high
            pfd.J1015.external_com_mic_audio_out_low >> c.mic_1_audio_in_low
            pfd.J1015.external_com_ptt_key_out >> c.com_mic_1_key
            (pfd.J1015.external_com_interlock_out >> c.disc_4).notes("Configure to TX Interlock")

    with gad27.J271 as c:
        c.discrete_in_7 >> pilot_stick.frequency_swap
        c.discrete_in_7 >> copilot_stick.frequency_swap

with System("FCTL"):
    with gsa28_roll.J281 as c:
        c.trim_in_1 >> gad27.J272.roll_trim_out_1
        c.trim_in_2 >> gad27.J272.roll_trim_out_2
        with Shield(drain="block", drain_remote="ground"):
            c.trim_out_1 >> roll_trim.trim_1
            c.trim_out_2 >> roll_trim.trim_2

    with gsa28_pitch.J281 as c:
        c.trim_in_1 >> gad27.J272.pitch_trim_out_1
        c.trim_in_2 >> gad27.J272.pitch_trim_out_2
        with Shield(drain="block", drain_remote="ground"):
            c.trim_out_1 >> pitch_trim.trim_1
            c.trim_out_2 >> pitch_trim.trim_2

    with gad27.J271 as c:
        c.aircraft_power >> avionics_block_1.GAD27
        c.ground >> gnd
        c.flap_up_1 >> flaps.up
        c.flap_down_1 >> flaps.down
        c.pilot_pitch_trim_up >> pilot_stick.trim_up
        c.pilot_pitch_trim_down >> pilot_stick.trim_down
        c.pilot_roll_trim_left >> pilot_stick.trim_left
        c.pilot_roll_trim_right >> pilot_stick.trim_right
        c.copilot_pitch_trim_up >> copilot_stick.trim_up
        c.copilot_pitch_trim_down >> copilot_stick.trim_down
        c.copilot_roll_trim_left >> copilot_stick.trim_left
        c.copilot_roll_trim_right >> copilot_stick.trim_right

    with gad27.J272 as c:
        c.pitch_trim_power_gnd >> gnd
        c.roll_trim_power_gnd >> gnd

    with gad27.TB273 as c:
        c.keep_alive_power_in >> avionics_block_2.GAD27
        c.keep_alive_power_out >> gad27.J272.pitch_trim_power_in
        c.keep_alive_power_out >> gad27.J272.roll_trim_power_in

        (c.flap_power_in >> main_block.flaps).gauge(18)
        (c.flap_power_gnd >> gnd).gauge(18)
        (c.flap_power_out_1 >> flap_motor.extend).gauge(18)
        (c.flap_power_out_2 >> flap_motor.retract).gauge(18)

    with gea24.J244 as c:
        (c.gp1 >> pitch_trim.position).drain()
        (c.gp2 >> roll_trim.position).drain()
        (c.gp3 >> flap_motor.position).drain()

    flaps.com >> gnd

with System("LGHT"):
    with gad27.J271 as c:
        landing_light_switch.com2 >> gnd
        landing_light_switch.com1 >> main_block.taxi_lights
        (landing_light_switch.no1 >> left_7_stars.taxi).gauge(20).color("R")
        (landing_light_switch.no1 >> right_7_stars.taxi).gauge(20).color("R")

        c.light_1_switch >> landing_light_switch.no2
        c.light_2_switch >> landing_light_switch.no2
        c.alternating_flash_on >> wig_wag.no

    with gad27.TB273 as c:
        (c.light_1_output >> left_7_stars.landing).gauge(14).color("R")
        (c.light_2_output >> right_7_stars.landing).gauge(14).color("R")
        (c.light_1_power >> main_block.landing_lights).gauge(18)
        (c.light_2_power >> main_block.landing_lights).gauge(18)

    nav_strobe_switch.com1 >> main_block.nav_lights
    nav_strobe_switch.com2 >> main_block.strobe_lights

    with flyleds_controller as c:
        c.ground >> gnd
        with Shield(drain=c.left_shield, drain_remote=left_pos_strobe.position_neg):
            c.left_strobe_neg >> left_pos_strobe.strobe_neg
            c.left_strobe_pos >> left_pos_strobe.strobe_pos
            c.left_position_pos >> left_pos_strobe.position_pos

        with Shield(drain=c.tail_shield):
            c.tail_pos >> tail_light.power
            c.tail_neg >> tail_light.ground

        with Shield(drain=c.right_shield, drain_remote=right_pos_strobe.position_neg):
            c.right_strobe_neg >> right_pos_strobe.strobe_neg
            c.right_strobe_pos >> right_pos_strobe.strobe_pos
            c.right_position_pos >> right_pos_strobe.position_pos

        c.strobe_12v_in >> nav_strobe_switch.no1
        c.position_12v_in >> nav_strobe_switch.no2

    (left_7_stars.ground >> left_wing_gnd).gauge(14)
    (right_7_stars.ground >> right_wing_gnd).gauge(14)
    wig_wag.com >> gnd

with System("CAB"):
    # TODO: Axis lighting bus
    # with gma245.J2402 as c:
    #     c.lighting_bus_high >> c.lighting_bus_14v_high_28v_low
    #     c.lighting_bus_low.local_ground()

    with gad27.J271 as c:
        c.output_12v >> backlight_rheo.power
        c.lighting_bus_gnd >> backlight_rheo.ground
        c.lighting_control_in_1 >> backlight_rheo.out

        c.output_12v >> cabin_light_rheo.power
        c.lighting_bus_gnd >> cabin_light_rheo.ground
        c.lighting_control_in_2 >> cabin_light_rheo.out

        c.pwm_lighting_1 >> cabin_lights.power

    gad27.J271.dc_lighting_1 >> mfd.J1012.lighting_bus_2
    mfd.J1012.lighting_bus_2 >> gmc507.J7001.lighting_bus_high
    gmc507.J7001.lighting_bus_high >> pfd.J1012.lighting_bus_2
    cabin_lights.ground >> gnd
    master_warning.ground >> gnd
    master_caution.ground >> gnd

with System("POW"):
    # c.discrete_in_1 >> alt_regulator
    # c.discrete_in_2 >> monkworkz_active
    pass


with System("ADSB"):
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
        c.rs232_1 >> gsu25.J252.rs232_3

    with gtx45r.P3252 as c:
        c.hsdb_1 >> pfd.J1012.hsdb_2

with System("GPS"):
    with pfd.J1015 as c:
        c.power_1 >> avionics_block_3.PFD_NAVCOM
        c.power_2 >> avionics_block_3.PFD_NAVCOM
        c.power_3 >> avionics_block_3.PFD_NAVCOM
        c.ground_1 >> gnd
        c.ground_2 >> gnd
        c.ground_3 >> gnd


with System("EFIS"):
    with pfd.J1012 as c:
        c.hsdb_1 >> mfd.J1012.hsdb_1
        c.config_module_power_out >> pfd_config.power
        c.config_module_ground >> pfd_config.ground
        c.config_module_data >> pfd_config.data
        c.config_module_clock >> pfd_config.clock

        c.power_1 >> avionics_block_3.PFD
        c.power_2 >> avionics_block_3.PFD
        c.power_3 >> avionics_block_3.PFD

    with mfd.J1012 as c:
        c.config_module_power_out >> mfd_config.power
        c.config_module_ground >> mfd_config.ground
        c.config_module_data >> mfd_config.data
        c.config_module_clock >> mfd_config.clock

        c.power_1 >> avionics_block_3.MFD
        c.power_2 >> avionics_block_3.MFD
        c.power_3 >> avionics_block_3.MFD

with System("EIS"):
    (pfd.J1012.rs232_1 >> gea24.J241.rs232).ground(False)

    with gea24.J241 as c:
        c.ground >> gnd
        c.aircraft_power_1 >> avionics_block_1.GEA24
        c.aircraft_power_2 >> avionics_block_2.GEA24

    with gea24.J242 as c:
        c.egt1 >> engine.Cylinder1.egt
        c.cht1 >> engine.Cylinder1.cht
        c.egt2 >> engine.Cylinder2.egt
        c.cht2 >> engine.Cylinder2.cht
        c.egt3 >> engine.Cylinder3.egt
        c.cht3 >> engine.Cylinder3.cht
        c.egt4 >> engine.Cylinder4.egt
        c.cht4 >> engine.Cylinder4.cht

    with gea24.J243 as c:
        (c.fuel_pressure_5v >> fuel_pressure.gpio).drain()
        with Shield(drain="block", drain_remote="block"):
            c.rpm_1.signal >> sds_ecu.tach
        (c.oil_pressure_5v >> oil_pressure.gpio).drain()
        (c.manifold_pressure_5v >> manifold_pressure.gpio).drain()
        with Shield(drain="block", drain_remote="block"):
            c.fuel_flow.signal >> sds_ecu.fuel_flow

        with Shield(drain="block"):
            c.oil_temp_high >> oil_temp.high
            c.oil_temp_low >> oil_temp.low

        c.shunt_1_high >> Fuse("Alternator Side", amps=1)
        c.shunt_1_low >> Fuse("Load Side", amps=1)

        with Shield(drain="block"):
            c.gp_5v_out >> co2_sensor.power
            c.gp6_high >> co2_sensor.signal
            c.gp_gnd_1 >> co2_sensor.ground

        c.gp6_low.local_ground()

    with gea24.J244 as c:
        c.fuel_quantity_1.signal >> left_fuel.power
        c.fuel_quantity_2.signal >> right_fuel.power

        c.volts_1 >> Fuse("Main Bus", amps=1)
        c.volts_2 >> Fuse("Engine Bus", amps=1)

        c.discrete_out_1 >> master_warning.power
        c.discrete_out_2 >> master_caution.power


with System("EMR"):
    with g5.J51 as c:
        c.ground >> gnd
        (c.aircraft_power_1 >> avionics_block_1.G5).notes("Lightning Protection Module")
        c.aircraft_power_2 >> avionics_block_2.G5
        c.can.note("Lightning Protection Module")

    with elt.DIN as c:
        with Shield(drain_remote="block"):
            c.remote_switch >> avionics_block_3.elt
            c.ground >> gnd
            c.elt_rx >> pfd.J1012.rs232_2.tx

        # TODO: c.rs232_test

can_bus = CanBusLine(
    name="CAN Bus",
    devices=[
        # Wing
        gmu11.J441,
        gsa28_roll.J281,
        # Panel
        mfd.J1012,
        g5.J51,
        gmc507.J7001,
        pfd.J1012,
        # Behind Panel
        gea24.J241,
        gad27.J271,
        gsu25.J251,
        # Tail
        gsa28_pitch.J281,
        gsa28_yaw.J281,
    ],
)


harness = Harness(
    "Avionics Harness",
    length_unit="in",
    default_system=None,
    components=[
        gsu25,
        gtp59,
        gmu11,
        gsa28_roll,
        gmc507,
        gsa28_pitch,
        toga,
        gsa28_yaw,
        gdl51r,
        pilot_lemo,
        copilot_lemo,
        gtr205xr,
        gad27,
        landing_light_switch,
        flap_motor,
        roll_trim,
        pitch_trim,
        gap26,
        gtx45r,
        pfd,
        mfd,
        g5,
        gea24,
        elt,
        flyleds_controller,
    ],
    disconnects=[
        left_wing_root,
        left_wing_handshake,
        right_wing_handshake,
        right_wing_root_a,
        right_wing_root_b,
    ],
    can_buses=[can_bus],
)
