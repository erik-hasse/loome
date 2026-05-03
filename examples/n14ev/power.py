from loome import Fuse, FuseBlock, GroundSymbol


class DualFeedBlock(FuseBlock):
    G5 = Fuse("G5", amps=5)
    GAD27 = Fuse("GAD27", amps=2)
    GAD29 = Fuse("GAD29", amps=2)
    PFD = Fuse("PFD", amps=5)
    MFD = Fuse("MFD", amps=5)
    GEA24 = Fuse("GEA24", amps=2)
    GMC507 = Fuse("GMC507", amps=2)
    GMU11 = Fuse("GMU11", amps=2)
    GSU25 = Fuse("GSU25", amps=2)
    GTX45R = Fuse("GTX4R", amps=3)


class SingleFeedBlock(FuseBlock):
    GAD27_elevator_trim = Fuse("GAD", amps=2)
    GTN650_nav = Fuse("GTN650", amps=7.5)
    GTN650_com = Fuse("GTN650 COM", amps=10)
    GSA28_roll = Fuse("GSA28 Roll", amps=5)
    GSA28_pitch = Fuse("GSA28 Pitch", amps=5)
    GSA28_yaw = Fuse("GSA28 Yaw", amps=5)
    GTR20 = Fuse("GTR20", amps=7.5)
    GMA245 = Fuse("GMA245", amps=5)
    GDL51R = Fuse("GDL51R", amps=3)
    LEMO_pilot = Fuse("LEMO Pilot", amps=0.5)
    LEMO_copilot = Fuse("LEMO Copilot", amps=0.5)
    elt = Fuse("ELT", amps=1)


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
