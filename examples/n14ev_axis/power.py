from loome import Fuse, FuseBlock, GroundSymbol


class DualFeedBlock(FuseBlock):
    G5 = Fuse("G5", amps=5)
    GAD27 = Fuse("GAD27", amps=2)
    GEA24 = Fuse("GEA24", amps=2)
    GMC507 = Fuse("GMC507", amps=2)
    GMU11 = Fuse("GMU11", amps=2)
    GSU25 = Fuse("GSU25", amps=2)
    GTX45R = Fuse("GTX4R", amps=3)


class SingleFeedBlock(FuseBlock):
    GAD27_elevator_trim = Fuse("GAD", amps=2)
    GSA28_roll = Fuse("GSA28 Roll", amps=5)
    GSA28_pitch = Fuse("GSA28 Pitch", amps=5)
    GSA28_yaw = Fuse("GSA28 Yaw", amps=5)
    GTR205xR = Fuse("GTR20", amps=10)
    GDL51R = Fuse("GDL51R", amps=3)
    LEMO_pilot = Fuse("LEMO Pilot", amps=0.5)
    LEMO_copilot = Fuse("LEMO Copilot", amps=0.5)
    elt = Fuse("ELT", amps=1)

    # TODO: verify amperages
    PFD = Fuse("PFD", amps=10)
    MFD = Fuse("MFD", amps=10)
    PFD_NAVCOM = Fuse("PFD NAVCOM", amps=10)


class MainBus(FuseBlock):
    landing_lights = Fuse("Landing Lights", amps=20)
    taxi_lights = Fuse("Taxi Lights", amps=5)
    flaps = Fuse("Flaps", amps=10)
    pitot_heat = Fuse("Pitot Heat", amps=15)
    nav_lights = Fuse("Nav Lights", amps=5)
    strobe_lights = Fuse("Strobe Lights", amps=10)


avionics_block_1 = DualFeedBlock("Left Dual")
avionics_block_2 = DualFeedBlock("Right Dual")
avionics_block_3 = SingleFeedBlock()
main_block = MainBus()
gnd = GroundSymbol("GND")
left_wing_gnd = GroundSymbol("Left Wing GND")
right_wing_gnd = GroundSymbol("Right Wing GND")
