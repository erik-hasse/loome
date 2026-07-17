from loome.components.sds import SDSEM6


def test_em6_documented_connector_pinouts():
    ecu = SDSEM6("Primary EM-6")

    assert ecu.DB25[12] is ecu.DB25.tach_5v
    assert ecu.DB25[13] is ecu.DB25.starter
    assert ecu.DB25[22] is ecu.DB25.tach_12v
    assert ecu.DB25[24] is ecu.DB25.wideband_o2
    assert ecu.DB25["BLACK"] is ecu.DB25.computer_ground
    assert ecu.DB25["RED"] is ecu.DB25.aircraft_power

    assert ecu.Molex16[1] is ecu.Molex16.configurable_relay
    assert ecu.Molex16[2] is ecu.Molex16.fuel_flow
    assert ecu.Molex16[3] is ecu.Molex16.rpm_switch
    assert ecu.Molex16[8] is ecu.Molex16.ground_1
    assert ecu.Molex16[9] is ecu.Molex16.closed_loop_enable
    assert ecu.Molex16[10] is ecu.Molex16.octane_retard
    assert ecu.Molex16[11] is ecu.Molex16.fault_led
    assert ecu.Molex16[16] is ecu.Molex16.ground_2

    assert ecu.HallDB9[3] is ecu.HallDB9.ground
    assert ecu.HallDB9[4] is ecu.HallDB9.trigger
    assert ecu.HallDB9[5] is ecu.HallDB9.power_5v
    assert ecu.HallDB9[8] is ecu.HallDB9.sync


def test_em6_instances_have_independent_pins():
    primary = SDSEM6("Primary")
    backup = SDSEM6("Backup")

    primary.DB25.tach_5v >> backup.DB25.starter

    assert len(primary.DB25.tach_5v._connections) == 1
    assert len(backup.DB25.starter._connections) == 1
    assert backup.DB25.tach_5v._connections == []
