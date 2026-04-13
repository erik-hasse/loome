from loome import Component, Connector, Fuse, GroundSymbol, Harness, OffPageReference, Pin
from loome.model import Shielded


class GSU25(Component):
    class J251(Connector):
        ground = Pin(6, "Ground")
        power = Pin(7, "Power")
        backup_power = Pin(8, "Backup Power")

        with Shielded():
            can_high = Pin(1, "CAN High")
            can_low = Pin(2, "CAN Low")
        with Shielded():
            rs232_in = Pin(4, "RS-232 In")
            rs232_out = Pin(5, "RS-232 Out")

    class J252(Connector):
        with Shielded():
            oat_probe_power = Pin(1, "OAT Probe Power")
            oat_probe_high = Pin(2, "OAT Probe High")
            oat_probe_low = Pin(3, "OAT Probe Low")

        with Shielded():
            rs232_3_rx = Pin(10, "RS-232 3 RX")
            rs232_3_tx = Pin(9, "RS-232 3 TX")
            rs232_3_gnd = Pin(11, "RS-232 3 GND")

        magnetometer_power = Pin(6, "Magnetometer Power")


class GDU460(Component):
    class P4601(Connector):
        with Shielded():
            rs232_out = Pin(4, "RS-232 Out")
            rs232_in = Pin(5, "RS-232 In")


class OATProbe(Component):
    with Shielded():
        oat_probe_power = Pin(1, "OAT Probe Power")
        oat_probe_high = Pin(2, "OAT Probe High")
        oat_probe_low = Pin(3, "OAT Probe Low")


class GTX45R(Component):
    class P3251(Connector):
        with Shielded():
            rs232_1_out = Pin(9, "RS-232 1 Out")
            rs232_1_in = Pin(31, "RS-232 1 In")
            rs232_1_gnd = Pin(11, "RS-232 1 GND")


class GMU11(Component):
    power = Pin(8, "Power")
    backup_power = Pin(7, "Backup Power")

    ground = Pin(9, "Ground")

    with Shielded():
        can_high = Pin(1, "CAN High")
        can_low = Pin(2, "CAN Low")


gnd = GroundSymbol("CHASSIS_GND")
can_bus = OffPageReference("CAN_BUS", label="To CAN Bus")
pfd = GDU460("GDU 460 PFD")

air_data_fuse = Fuse("air_data", "Air Data", 5)
air_data_backup_fuse = Fuse("air_data_backup", "Air Data Backup", 5)

# Class-level connections — pin numbers are automatic from Pin definitions
GSU25.J251.power.connect(air_data_fuse)
GSU25.J251.backup_power.connect(air_data_backup_fuse)
GSU25.J251.ground.connect(gnd, color="N")
GSU25.J251.can_high.connect(can_bus)
GSU25.J251.can_low.connect(can_bus)
GSU25.J251.rs232_in.connect(pfd.P4601.rs232_out)
GSU25.J251.rs232_out.connect(pfd.P4601.rs232_in)

GSU25.J252.oat_probe_power.connect(OATProbe.oat_probe_power)
GSU25.J252.oat_probe_low.connect(OATProbe.oat_probe_low)
GSU25.J252.oat_probe_high.connect(OATProbe.oat_probe_high)
GSU25.J252.rs232_3_rx.connect(GTX45R.P3251.rs232_1_out)
GSU25.J252.rs232_3_tx.connect(GTX45R.P3251.rs232_1_in)
GSU25.J252.rs232_3_gnd.connect(GTX45R.P3251.rs232_1_gnd)
GSU25.J252.magnetometer_power.connect(GMU11.power)

GMU11.backup_power.connect(air_data_backup_fuse)
GMU11.ground.connect(gnd, color="N")
GMU11.can_low.connect(can_bus)
GMU11.can_high.connect(can_bus)


harness = Harness("Avionics Harness")
harness.add(
    GSU25("GSU 25"),
    pfd,
    OATProbe("OAT Probe"),
    GTX45R("GTX45R"),
    GMU11("GMU 11"),
    gnd,
    can_bus,
    air_data_fuse,
    air_data_backup_fuse,
)
