from loome import Fuse, FuseBlock, GroundSymbol


class DualFeedBlock(FuseBlock):
    G5 = Fuse("Standby EFIS", amps=5)
    GAD27 = Fuse("Elec Adapter", amps=2)
    GEA24 = Fuse("Engine Mon", amps=2)
    GMC507 = Fuse("AP Head", amps=2)
    GMU11 = Fuse("Magnetometer", amps=2)
    GSU25 = Fuse("Air Data", amps=2)
    GTX45R = Fuse("Xponder", amps=3)


class SingleFeedBlock(FuseBlock):
    GSA28_roll = Fuse("AP Roll", amps=5)
    GSA28_pitch = Fuse("AP Pitch", amps=5)
    GSA28_yaw = Fuse("AP Yaw", amps=5)
    GAD27_pitch_trim = Fuse("Pitch Trim", amps=5)
    GAD27_roll_trim = Fuse("Roll Trim", amps=5)
    GTR205xR = Fuse("COM 2", amps=10)
    GDL51R = Fuse("Sirius XM", amps=3)
    LEMO_pilot = Fuse("LEMO Pilot", amps=0.25)
    LEMO_copilot = Fuse("LEMO Copilot", amps=0.25)
    elt = Fuse("ELT", amps=1)

    # TODO: verify amperages
    PFD = Fuse("PFD", amps=7.5)
    MFD = Fuse("MFD", amps=7.5)
    PFD_NAVCOM = Fuse("NAVCOM", amps=7.5)
    annunciator = Fuse("Annunciator", amps=1)


class MainBus(FuseBlock):
    landing_lights = Fuse("Landing Lights", amps=20)
    taxi_lights = Fuse("Taxi Lights", amps=5)
    flaps = Fuse("Flaps", amps=10)
    pitot_heat = Fuse("Pitot Heat", amps=15)
    nav_lights = Fuse("Nav Lights", amps=5)
    strobe_lights = Fuse("Strobe Lights", amps=10)
    cabin_lights = Fuse("Cabin Lights", amps=1)


avionics_block_1 = DualFeedBlock("Left Dual")
avionics_block_2 = DualFeedBlock("Right Dual")
avionics_block_3 = SingleFeedBlock()
main_block = MainBus()
gnd = GroundSymbol("GND")
left_wing_gnd = GroundSymbol("Left Wing GND")
right_wing_gnd = GroundSymbol("Right Wing GND")
