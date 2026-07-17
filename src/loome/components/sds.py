from loome.model import Component, Connector, Pin


class SDSEM6(Component):
    """SDS EM-6 ECU connections documented in aircraft manual version 14.9.

    The supplied DB25 harness has several pre-terminated sensor and actuator
    branches whose ECU pin numbers are not published in the manual. This model
    intentionally includes only the DB25 positions and harness leads that the
    manual identifies explicitly.
    """

    class DB25(Connector):
        # The manual identifies these two harness leads by color, but does not
        # publish their DB25 cavity numbers.
        computer_ground = Pin("BLACK", "Computer Ground (20 AWG)")
        aircraft_power = Pin("RED", "Switched 12V ECU Power (20 AWG, 2A)")

        tach_5v = Pin(12, "5V Tachometer Output")
        starter = Pin(13, "Starter Input (+12V)")
        tach_12v = Pin(22, "12V Tachometer Output")
        wideband_o2 = Pin(24, "Wideband O2 Analog Input (0-5V)")

    class Molex16(Connector):
        configurable_relay = Pin(1, "Configurable Relay Output (Ground-switched)")
        fuel_flow = Pin(2, "Fuel Flow Pulse Output")
        rpm_switch = Pin(3, "RPM Switch Output (Ground-switched)")

        ground_1 = Pin(8, "ECU Ground 1")
        closed_loop_enable = Pin(9, "Closed Loop Enable / Alternate Starter Input (Ground-switched)")
        octane_retard = Pin(10, "Octane Retard / Alternate Starter Input (Ground-switched)")
        fault_led = Pin(11, "Fault LED Output (Ground-switched)")
        ground_2 = Pin(16, "ECU Ground 2")

    class HallDB9(Connector):
        ground = Pin(3, "Hall Sensor Ground")
        trigger = Pin(4, "Hall Sensor Trigger")
        power_5v = Pin(5, "Hall Sensor +5V")
        sync = Pin(8, "Hall Sensor Sync")
