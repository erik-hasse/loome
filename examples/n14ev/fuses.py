from loome import Fuse, FuseBlock


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


class SingleFeedBlock(FuseBlock):
    GAD27_elevator_trim = Fuse("GAD", amps=2)
    GTN650 = Fuse("GTN650", amps=5)
    GSA28_roll = Fuse("GSA28 Roll", amps=5)
    GSA28_pitch = Fuse("GSA28 Pitch", amps=5)
    GSA28_yaw = Fuse("GSA28 Yaw", amps=5)
    GTR20 = Fuse("GTR20", amps=7.5)
    GMA245 = Fuse("GMA245", amps=5)
    GDL51R = Fuse("GDL51R", amps=3)
    LEMO_pilot = Fuse("LEMO Pilot", amps=0.5)
    LEMO_copilot = Fuse("LEMO Copilot", amps=0.5)


avionics_block_1 = DualFeedBlock()
avionics_block_2 = DualFeedBlock()
avionics_block_3 = SingleFeedBlock()
