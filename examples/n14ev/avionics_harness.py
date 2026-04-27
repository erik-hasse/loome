from examples.n14ev.fuses import avionics_block_1, avionics_block_2, avionics_block_3
from examples.n14ev.lrus import (
    copilot_lemo,
    copilot_stick,
    g5,
    gad27,
    gad29,
    gdl51r,
    gea24,
    gma245,
    gmc507,
    gmu11,
    gsu25,
    gtn650xi,
    gtr20,
    gtx45r,
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
    yaw_servo,
)
from loome import DPST, CanBusLine, GroundSymbol, Harness, Shield

gnd = GroundSymbol("GND")
local = GroundSymbol("local")
toga = DPST("TO/GA", momentary=True)

# Page 2
with gsu25.J251 as c:
    c.ground_a >> gnd
    c.aircraft_power_1 >> avionics_block_1.GSU25
    c.aircraft_power_2 >> avionics_block_2.GSU25
    c.rs232 >> pfd.P4601.rs232

with gsu25.J252 as c:
    with Shield(drain=local, drain_remote=local):
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

toga.com1 >> toga.com2
toga.com1 >> gnd

# Page 5

with yaw_servo.J281 as c:
    c.ground >> gnd
    c.power >> avionics_block_3.GSA28_yaw

# Page 6

with gdl51r as c:
    c.aircraft_power >> avionics_block_3.GDL51R
    c.ground >> gnd
    with Shield(drain_remote=local):
        c.music_out_left >> gma245.J2402.music_2_in_left
        c.music_out_common >> gma245.J2402.music_2_in_low
        c.music_out_right >> gma245.J2402.music_2_in_right

    c.rs232_1 >> pfd.P4602.rs232_1
    c.rs232_2 >> mfd.P4602.rs232_4

# Page 7
with gma245.P2401 as c:
    with Shield(drain=local):
        c.pilot_mic_key_in >> pilot_stick.push_to_talk
        c.pilot_mic_audio_in_high >> pilot_lemo.mic_high
        c.pilot_mic_audio_in_low >> pilot_lemo.mic_low

with gma245.J2402 as c:
    with Shield(drain=local):
        c.pilot_headset_audio_out_left >> pilot_lemo.audio_left
        c.pilot_headset_audio_out_right >> pilot_lemo.audio_right
        c.pilot_headset_audio_out_low >> pilot_lemo.ground

    with Shield(drain=local):
        c.copilot_headset_audio_out_left >> copilot_lemo.audio_left
        c.copilot_headset_audio_out_right >> copilot_lemo.audio_right
        c.copilot_headset_audio_out_low >> copilot_lemo.ground

    with Shield(drain=local):
        c.copilot_mic_key_in >> copilot_stick.push_to_talk
        c.copilot_mic_audio_in_high >> copilot_lemo.mic_high
        c.copilot_mic_audio_in_low >> copilot_lemo.mic_low

    # Page 8
    with Shield(drain=local):
        c.music_1_in_left >> music_in.tip
        c.music_1_in_right >> music_in.ring
        c.music_1_in_low >> music_in.sleeve

    c.aircraft_power_a >> avionics_block_3.GMA245
    c.aircraft_power_b >> avionics_block_3.GMA245
    c.ground_a >> gnd
    c.ground_b >> gnd

    c.lighting_bus_high >> c.lighting_bus_14v_high_28v_low

    c.com_swap >> pilot_stick.com_swap
    c.com_swap >> copilot_stick.com_swap

    c.play_key >> pilot_stick.replay
    c.play_key >> copilot_stick.replay


# Page 9
with gma245.P2401 as c:
    with Shield(drain=local):
        c.com_1_audio_in_high >> gtn650xi.P1003.com_audio_hi
        c.com_1_audio_low >> gtn650xi.P1003.com_audio_lo

    with Shield(drain=local):
        c.com_1_audio_low >> gtn650xi.P1003.mic_audio_in_lo
        c.com_1_mic_audio_out_high >> gtn650xi.P1003.com_mic_1_audio_in_hi
        c.com_1_mic_key_out >> gtn650xi.P1003.com_mic_1_key
    c.com_1_mic_key_out >> gtr20.J2001.tx_interlock_in

    with Shield(drain=local):
        c.nav_1_audio_in_high >> gtn650xi.P1004.vor_loc_audio_out_hi
        c.nav_1_audio_in_low >> gtn650xi.P1004.vor_loc_audio_out_lo

    with Shield(drain=local):
        c.alert_3_4_aux_3_audio_in_low >> gtn650xi.P1001.audio_out_lo
        c.alert_4_audio_in_high >> gtn650xi.P1001.audio_out_hi

    with Shield(drain=local):
        c.com_2_audio_in_high >> gtr20.J2001.receiver_out_high
        c.com_2_audio_low >> gtr20.J2001.receiver_audio_low

    with Shield(drain=local):
        c.com_2_audio_low >> gtr20.J2001.pilot_mic_low
        c.com_2_mic_audio_out_high >> gtr20.J2001.pilot_mic_in
        c.com_2_mic_key_out >> gtr20.J2001.pilot_ptt


# Page 10

with gtr20.J2001 as c:
    pass

# Page 15

gad27.J271.dc_lighting_1 >> mfd.P4602.lighting_bus_high_14V
mfd.P4602.lighting_bus_high_14V >> pfd.P4602.lighting_bus_high_14V
pfd.P4602.lighting_bus_high_14V >> gtn650xi.P1001.lighting_bus_1_hi
gtn650xi.P1001.lighting_bus_1_hi >> gmc507.J7001.lighting_bus_high
gmc507.J7001.lighting_bus_high >> gma245.J2402.lighting_bus_high


# ── harness ───────────────────────────────────────────────────────────────────

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

harness = Harness("Avionics Harness", length_unit="in")
