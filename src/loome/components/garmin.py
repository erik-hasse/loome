from enum import StrEnum

from loome import ARINC429, GPIO, RS232, CanBus, Component, Connector, GarminEthernet, Pin, Thermocouple
from loome.constants import Axis


class GAD27(Component):
    """Flap, Lights, Trim Controller"""

    def can_terminate(self) -> None:
        self.J271.can.low >> self.J271.can_term

    class J271(Connector):
        can = CanBus(1, 2)
        can_term = Pin(3, "Can Term")
        signal_ground = Pin(4, "Signal Ground")

        aircraft_power = Pin(7, "Power In")
        ground = Pin(8, "Power Ground")

        discrete_in_1 = Pin(9, "Discrete In 1")
        discrete_in_2 = Pin(10, "Discrete In 2")
        discrete_in_3 = Pin(11, "Discrete In 3")
        discrete_in_4 = Pin(12, "Discrete In 4")
        discrete_in_5 = Pin(13, "Discrete In 5")
        discrete_in_6 = Pin(14, "Discrete In 6")
        discrete_in_7 = Pin(15, "Discrete In 7")

        motor_disconnect = Pin(16, "Motor Disconnect")

        flap_up_1 = Pin(18, "Flap Up 1")
        abs_flap_pos_1 = Pin(18, "Absolute Flap Pos 1")
        flap_down_1 = Pin(19, "Flap Down 1")
        abs_flap_pos_2 = Pin(19, "Absolute Flap Pos 2")
        flap_up_2 = Pin(20, "Flap Up 2")
        abs_flap_pos_3 = Pin(20, "Absolute Flap Pos 3")
        flap_down_2 = Pin(21, "Flap Down 2")
        abs_flap_pos_4 = Pin(21, "Absolute Flap Pos 4")
        flap_limit_up = Pin(22, "Flap Limit Up")
        flap_limit_down = Pin(23, "Flap Limit Down")

        pilot_pitch_trim_up = Pin(24, "Pitch Trim Up")
        pilot_pitch_trim_down = Pin(25, "Pitch Trim Down")
        copilot_pitch_trim_up = Pin(26, "Pitch Trim Up")
        copilot_pitch_trim_down = Pin(27, "Pitch Trim Down")

        pilot_roll_trim_left = Pin(28, "Roll Trim Left")
        pilot_roll_trim_right = Pin(29, "Roll Trim Right")
        copilot_roll_trim_left = Pin(30, "Roll Trim Left")
        copilot_roll_trim_right = Pin(31, "Roll Trim Right")

        yaw_trim_left = Pin(32, "Yaw Trim Left")
        yaw_trim_right = Pin(33, "Yaw Trim Right")

        light_1_switch = Pin(34, "Light 1 Switch")
        light_2_switch = Pin(35, "Light 2 Switch")
        alternating_flash_on = Pin(36, "Alternating Flash On")

        output_12v = Pin(37, "Output 12V")

        lighting_bus_gnd = Pin(38, "Lighting Bus Ground")
        lighting_control_in_1 = Pin(39, "Lighting Control In 1")
        lighting_control_in_2 = Pin(40, "Lighting Control In 2")
        lighting_control_in_3 = Pin(41, "Lighting Control In 3")
        dc_lighting_1 = Pin(42, "DC Lighting 1")
        dc_lighting_2 = Pin(43, "DC Lighting 2")
        dc_lighting_3 = Pin(44, "DC Lighting 3")
        pwm_lighting_1 = Pin(45, "PWM Lighting 1")
        pwm_lighting_2 = Pin(46, "PWM Lighting 2")
        pwm_lighting_3 = Pin(47, "PWM Lighting 3")

        discrete_in_8 = Pin(48, "Discrete In 8")
        discrete_in_9 = Pin(49, "Discrete In 9  ")

    class J272(Connector):
        pitch_trim_power_in = Pin(1, "Pitch Trim Power In")
        pitch_trim_power_gnd = Pin(2, "Pitch Trim Power Ground")
        roll_trim_power_in = Pin(3, "Roll Trim Power In")
        roll_trim_power_gnd = Pin(4, "Roll Trim Power Ground")
        yaw_trim_power_in = Pin(5, "Yaw Trim Power In")
        yaw_trim_power_gnd = Pin(6, "Yaw Trim Power Ground")

        roll_trim_out_1 = Pin(9, "Roll Trim Out 1")
        roll_trim_out_2 = Pin(10, "Roll Trim Out 2")
        pitch_trim_out_1 = Pin(11, "Pitch Trim Out 1")
        pitch_trim_out_2 = Pin(12, "Pitch Trim Out 2")
        yaw_trim_out_1 = Pin(13, "Yaw Trim Out 1")
        yaw_trim_out_2 = Pin(14, "Yaw Trim Out 2")

    class TB273(Connector):
        keep_alive_power_in = Pin(1, "Keep Alive Power In")
        keep_alive_power_out = Pin(2, "Keep Alive Power Out")
        light_1_power = Pin(3, "Light 1 Power In")
        light_2_power = Pin(4, "Light 2 Power In")
        flap_power_in = Pin(5, "Flap Power In")
        flap_power_gnd = Pin(6, "Flap Power Ground")
        flap_power_out_1 = Pin(7, "Flap Power Out 1")
        flap_power_out_2 = Pin(8, "Flap Power Out 2")
        light_1_output = Pin(9, "Light 1 Output")
        light_2_output = Pin(10, "Light 2 Output")


class _P4X01(Connector):
    can = CanBus(1, 2)
    rs232 = RS232(4, 5, 6)
    power_1 = Pin(7, "Power 1")
    power_2 = Pin(8, "Power 2")
    ground = Pin(9, "Ground")


class _P4X02(Connector):
    mono_audio_out_high = Pin(1, "Mono Audio Out High")
    mono_audio_out_low = Pin(18, "Mono Audio Out Low")
    stereo_audio_out_low_1 = Pin(2, "Stereo Audio Out Low 1")
    stereo_audio_out_low_2 = Pin(20, "Stereo Audio Out Low 2")
    stereo_audio_out_left = Pin(3, "Stereo Audio Out Left")
    stereo_audio_out_right = Pin(19, "Stereo Audio Out Right")

    cdu_system_id_program_1 = Pin(5, "CDU System ID Program 1")
    cdu_system_id_program_2 = Pin(4, "CDU System ID Program 2")
    cdu_system_id_program_3 = Pin(21, "CDU System ID Program 3")
    cdu_system_id_program_4 = Pin(42, "CDU System ID Program 4")
    cdu_system_id_program_5 = Pin(38, "CDU System ID Program 5")
    cdu_system_id_program_6 = Pin(38, "CDU System ID Program 6")

    rs232_1 = RS232(48, 47, 27, "RS-232 1")
    rs232_2 = RS232(30, 14, 34, "RS-232 2")
    rs232_3 = RS232(13, 29, 35, "RS-232 3")
    rs232_4 = RS232(40, 23, 36, "RS-232 4")
    rs232_5 = RS232(41, 24, 37, "RS-232 5")

    can = CanBus(46, 45)
    can_bus_term = Pin(28, "CAN Bus Term")

    signal_ground = Pin(44, "Signal Ground")

    aircraft_power_1 = Pin(32, "Aircraft Power 1")
    aircraft_power_2 = Pin(31, "Aircraft Power 2")
    ground_1 = Pin(15, "Ground 1")
    ground_2 = Pin(16, "Ground 2")

    config_module_power_out = Pin(17, "Config Module Power Out")
    config_module_ground = Pin(49, "Config Module Ground")
    config_module_data = Pin(50, "Config Module Data")
    config_module_clock = Pin(33, "Config Module Clock")

    lighting_bus_high_28V = Pin(22, "Lighting Bus High 28V")
    lighting_bus_high_14V = Pin(43, "Lighting Bus High 14V")


class GDUMode(StrEnum):
    PFD = "PFD"
    MFD = "MFD"


class GDU460(Component):
    """Display Unit, automatically connects CDU pins based on mode and display number"""

    def can_terminate(self) -> None:
        self.P4602.can.low >> self.P4602.can_bus_term

    def __init__(self, name: str, mode: GDUMode, number: int = 1):
        super().__init__(name)
        self.mode = mode
        self.number = number

        match mode, number:
            case GDUMode.PFD, 1:
                self.P4602.cdu_system_id_program_1.local_ground()
            case GDUMode.PFD, 2:
                self.P4602.cdu_system_id_program_2.local_ground()
            case GDUMode.PFD, 3:
                self.P4602.cdu_system_id_program_1.local_ground()
                self.P4602.cdu_system_id_program_2.local_ground()
                self.P4602.cdu_system_id_program_6.local_ground()
            case GDUMode.MFD, 2:
                self.P4602.cdu_system_id_program_1.local_ground()
                self.P4602.cdu_system_id_program_2.local_ground()
            case GDUMode.MFD, 3:
                self.P4602.cdu_system_id_program_1.local_ground()
                self.P4602.cdu_system_id_program_2.local_ground()
                self.P4602.cdu_system_id_program_5.local_ground()

    class P4601(_P4X01):
        pass

    class P4602(_P4X02):
        pass


class GEA24(Component):
    """EIS Interface"""

    def can_terminate(self) -> None:
        self.J241.can.terminate()

    class J241(Connector):
        can = CanBus(1, 2)
        rs232 = RS232(5, 4, 6)  # tx, rx, gnd
        aircraft_power_1 = Pin(7, "Aircraft Power 1")
        aircraft_power_2 = Pin(8, "Aircraft Power 2")
        ground = Pin(9, "Ground")

    class J242(Connector):
        egt1 = Thermocouple(25, 13, "EGT 1")
        egt2 = Thermocouple(23, 11, "EGT 2")
        egt3 = Thermocouple(21, 9, "EGT 3")
        egt4 = Thermocouple(19, 7, "EGT 4")
        egt5 = Thermocouple(17, 5, "EGT 5")
        egt6 = Thermocouple(15, 3, "EGT 6")
        cht1 = Thermocouple(24, 12, "CHT 1")
        cht2 = Thermocouple(22, 10, "CHT 2")
        cht3 = Thermocouple(20, 8, "CHT 3")
        cht4 = Thermocouple(18, 6, "CHT 4")
        cht5 = Thermocouple(16, 4, "CHT 5")
        cht6 = Thermocouple(14, 2, "CHT 6")

    class J243(Connector):
        fuel_pressure_12v = GPIO(3, 2, 1, "Fuel Pressure 12V")
        fuel_pressure_5v = GPIO(4, 2, 1, "Fuel Pressure 5V")

        rpm_1 = GPIO(9, 8, 7, "RPM 1")
        rpm_2 = GPIO(10, 6, 5, "RPM 2")

        manifold_pressure_12v = GPIO(14, 13, 23, "Manifold Pressure 12V")
        manifold_pressure_5v = GPIO(15, 13, 12, "Manifold Pressure 5V")

        oil_pressure_12v = GPIO(18, 17, 16, "Oil Pressure 12V")
        oil_pressure_5v = GPIO(19, 17, 16, "Oil Pressure 5V")

        fuel_flow = GPIO(25, 23, 22, "Fuel Flow")
        fuel_return = GPIO(24, 21, 20)

        gp_5v_out = Pin(26, "GP 5V Out")
        gp_gnd_1 = Pin(27, "GP Ground 1")
        gp7_low = Pin(28, "GP7 Low")
        gp7_high = Pin(29, "GP7 High")
        gp6_low = Pin(30, "GP6 Low")
        gp6_high = Pin(31, "GP6 High")

        oil_temp_low = Pin(32, "Oil Temp Low")
        oil_temp_high = Pin(33, "Oil Temp High")

        shunt_2_low = Pin(34, "Shunt 2 Low")
        shunt_2_high = Pin(35, "Shunt 2 High")
        shunt_1_low = Pin(36, "Shunt 1 Low")
        shunt_1_high = Pin(37, "Shunt 1 High")

    class J244(Connector):
        system_id_1a = Pin(1, "System ID 1A")
        system_id_1b = Pin(2, "System ID 1B/Ground")

        fuel_quantity_1 = GPIO(5, 6, 7, name="Fuel Quantity 1")
        fuel_quantity_2 = GPIO(8, 9, 10, name="Fuel Quantity 2")

        gp1 = GPIO(18, 19, 20, name="GP1")  # positive, signal, ground
        gp2 = GPIO(21, 22, 23, name="GP2")  # positive, signal, ground
        gp3 = GPIO(11, 12, 13, name="GP3")
        gp4 = GPIO(14, 15, 16, name="GP4")
        gp5 = GPIO(30, 31, 32, name="GP5")

        can2 = CanBus(17, 33)

        gp_5v_out_2 = Pin(24, "GP 5V Out 2")
        volts_1 = Pin(25, "Volts 1")
        gp_gnd_2 = Pin(26, "GP Ground 2")
        gp_5v_out_3 = Pin(27, "GP 5V Out 3")
        volts_2 = Pin(28, "Volts 2")
        gp_gnd_3 = Pin(29, "GP Ground 3")

        fuel_flow = GPIO(34, 36, 38, "Fuel Flow")
        fuel_return = GPIO(35, 37, 39, "Fuel Return")

        discrete_in_1 = Pin(40, "Discrete In 1")
        discrete_in_2 = Pin(41, "Discrete In 2")
        discrete_in_3 = Pin(42, "Discrete In 3")
        discrete_in_4 = Pin(43, "Discrete In 4")

        discrete_out_1 = Pin(44, "Discrete Out 1, Master Warning")
        discrete_out_2 = Pin(45, "Discrete Out 2, Master Caution")

        shunt_2_high = Pin(46, "Shunt 2 High")
        shunt_2_low = Pin(47, "Shunt 2 Low")

        gp_12v_out = Pin(50, "GP 12V Out")


class GMC507(Component):
    """Autopilot controller"""

    def _terminate(self) -> None:
        self.J7001.can_term_1 >> self.J7001.can_term_2

    class J7001(Connector):
        unit_id_1 = Pin(1, "Unit ID 1")
        unit_id_2 = Pin(2, "Unit ID 2")
        can = CanBus(3, 4)
        can_term_2 = Pin(6, "Can Terminator_2")
        aircraft_power_1 = Pin(7, "Aircraft Power 1")
        can_term_1 = Pin(8, "Can Term 1")
        aircraft_power_2 = Pin(9, "Aircraft Power 2")
        remote_go_around = Pin(10, "Remote Go-Around")
        lighting_bus_high = Pin(11, "Lighting Bus High")
        ground = Pin(15, "Ground")


class GMU11(Component):
    """Magnetometer"""

    def can_terminate(self):
        self.J441.can.terminate()

    class J441(Connector):
        can = CanBus(1, 2)
        unit_id = Pin(3, "Unit ID")
        signal_ground = Pin(6, "Signal Ground")
        aircraft_power_1 = Pin(7, "Aircraft Power 1")
        aircraft_power_2 = Pin(8, "Aircraft Power 2")
        ground = Pin(9, "Ground")


class _BaseJ281(Connector):
    can = CanBus(1, 2)
    can_term_1 = Pin(3, "Can Term 1")
    can_term_2 = Pin(4, "Can Term 2")

    id_strap_1 = Pin(5, "ID Strap 1")
    id_strap_2 = Pin(6, "ID Strap 2")

    ground = Pin(9, "Ground")
    power = Pin(10, "Power")
    trim_in_1 = Pin(11, "Trim In 1")
    trim_in_2 = Pin(12, "Trim In 2")
    trim_out_1 = Pin(13, "Trim Out 1")
    trim_out_2 = Pin(14, "Trim Out 2")
    disconnect = Pin(15, "Disconnect")


class GSA28(Component):
    """Autopilot Servo (pitch/yaw variant). If axis is provided, strap jumpers will be
    connected automatically."""

    def can_terminate(self) -> None:
        self.J281.can_term_1 >> self.J281.can_term_2

    def __init__(self, name: str, axis: Axis | None = None, is_trim: bool = False):
        super().__init__(name)
        self.axis = axis
        self.is_trim = is_trim

        match axis, is_trim:
            case Axis.ROLL, False:
                if type(self) is GSA28:
                    raise ValueError("Use GSA28RollServo instead")
            case Axis.PITCH, False:
                self.J281[5].connect(self.J281[8])
            case Axis.YAW, False:
                self.J281[6].connect(self.J281[7])
            case Axis.ROLL, True:
                self.J281[5].connect(self.J281[8])
                self.J281[6].connect(self.J281[7])
            case Axis.PITCH, True:
                self.J281[7].connect(self.J281[8])
            case Axis.YAW, True:
                raise ValueError("GSA 28 does not support yaw trim")

    class J281(_BaseJ281):
        id_strap_3 = Pin(7, "ID Strap 3")
        id_strap_4 = Pin(8, "ID Strap 4")


class GSA28RollServo(GSA28):
    """Autopilot Servo, roll variant — repurposes pins 7/8 as RS-232."""

    def __init__(self, name: str):
        super().__init__(name, Axis.ROLL, is_trim=False)

    class J281(_BaseJ281):
        rs232 = RS232(7, 8)


class GSU25(Component):
    """Air Data Unit"""

    def can_terminate(self) -> None:
        self.J251.can.terminate()

    class J251(Connector):
        can = CanBus(1, 2)
        rs232 = RS232(5, 4, None)
        aircraft_power_1 = Pin(7, "Aircraft Power 1")
        aircraft_power_2 = Pin(8, "Aircraft Power 2")
        ground_a = Pin(6, "Ground A")
        ground_b = Pin(9, "Ground B")

    class J252(Connector):
        oat_probe_power = Pin(1, "OAT Probe Power")
        oat_probe_high = Pin(2, "OAT Probe High")
        oat_probe_low = Pin(3, "OAT Probe Low")

        unit_id_1_ground = Pin(4, "Unit ID 1 Ground")
        unit_id_1 = Pin(5, "Unit ID 1")
        magnetometer_power_12v = Pin(6, "Magnetometer Power +12V")
        magnetometer_ground = Pin(7, "Magnetometer Ground")

        rs232_3 = RS232(9, 10, 11, name="RS-232 3")  # tx, rx, gnd

        rs485_rx_a = Pin(12, "RS-485 RX A")
        rs485_rx_b = Pin(13, "RS-485 RX B")

        ground = Pin(14, "Ground")
        rs232_2_tx = Pin(15, "RS-232 2 TX")


class _BaseJ292(Connector):
    arinc_tx_1_1 = ARINC429(24, 12, "out", name="ARINC TX 1B")
    arinc_tx_1_2 = ARINC429(25, 13, "out", name="ARINC TX 1B")
    arinc_tx_2_1 = ARINC429(18, 6, "out", name="ARINC TX 2 #1")
    arinc_tx_2_2 = ARINC429(19, 7, "out", name="ARINC TX 2 #1")
    can_term_1 = Pin(9, "Can Term 1")
    can_term_2 = Pin(21, "Can Term 2")
    arinc_rx_1 = ARINC429(23, 11, "in", name="ARINC RX 1")
    arinc_rx_2 = ARINC429(22, 10, "in", name="ARINC RX 2")
    arinc_rx_3 = ARINC429(17, 5, "in", name="ARINC RX 3")
    arinc_rx_4 = ARINC429(16, 4, "in", name="ARINC RX 4")


class GAD29C(Component):
    """ARINC Adapter"""

    def can_terminate(self) -> None:
        self.J292.can_term_1 >> self.J292.can_term_2

    class J291(Connector):
        can = CanBus(1, 2)
        ground = Pin(3, "Ground")
        aircraft_power_1 = Pin(7, "Power 1")
        aircraft_power_2 = Pin(8, "Power 2")

    class J292(_BaseJ292):
        ground_1 = Pin(14, "Ground 1")
        ground_2 = Pin(20, "Ground 2")


class GTP59(Component):
    """OAT Probe"""

    oat_probe_power = Pin("WHT", "OAT Probe Power")
    oat_probe_sense = Pin("BLU", "OAT Probe Sense")
    oat_probe_low = Pin("ORN", "OAT Probe Low")


class GTR20(Component):
    def can_terminate(self) -> None:
        self.J2001.can_term_a >> self.J2001.can_term_b

    class J2001(Connector):
        aircraft_power = Pin(1, "Aircraft Power 1")
        disconnect_1 = Pin(2, "Disconnect 1")
        tx_interlock_out = Pin(4, "Tx Interlock Out")
        tx_interlock_in = Pin(5, "Tx Interlock In")
        can = CanBus(7, 6)
        id_in = Pin(8, "ID In")
        aux_mono_in_2 = Pin(9, "Aux Mono In 2")
        receiver_out_high = Pin(10, "Receiver Out High")
        copilot_hs_right = Pin(11, "Copilot HS Right")
        copilot_hs_left = Pin(12, "Copilot HS Left")
        pilot_hs_right = Pin(13, "Pilot HS Right")
        pilot_hs_left = Pin(14, "Pilot HS Left")
        copilot_ptt = Pin(15, "Copilot PTT")
        copilot_mic_in = Pin(16, "Copilot Mic In")
        pilot_mic_in = Pin(17, "Pilot Mic In")
        music_in_right = Pin(18, "Music In Right")
        music_in_left = Pin(19, "Music In Left")
        ground = Pin(20, "Ground")
        disconnect_2 = Pin(22, "Disconnect 2")
        can_term_b = Pin(25, "CAN Term B")
        can_term_a = Pin(26, "CAN Term A")
        id_low = Pin(27, "ID Low")
        aux_2_low = Pin(28, "Aux 2 Low")
        receiver_audio_low = Pin(29, "Receiver Audio Low")
        copilot_hs_low = Pin(30, "Copilot HS Low")
        aux_1_low = Pin(31, "Aux 1 Low")
        aux_mono_in_1 = Pin(32, "Aux Mono In 1")
        pilot_hs_low = Pin(33, "Pilot HS Low")
        copilot_mic_low = Pin(34, "Copilot Mic Low")
        pilot_ptt = Pin(35, "Pilot PTT")
        pilot_mic_low = Pin(36, "Pilot Mic Low")
        music_low = Pin(37, "Music Low")


class GDL51R(Component):
    rs232_2 = RS232(5, 6, 11, name="RS 232 2")
    rs232_1 = RS232(7, 8, 12, name="RS 232 1")
    ground = Pin(9, "Ground")
    aircraft_power = Pin(10, "Aircraft Power")
    music_out_left = Pin(13, "Music Out Left")
    music_out_common = Pin(14, "Music Out Common")
    music_out_right = Pin(15, "Music Out Right")


class GMA245(Component):
    def can_terminate(self) -> None:
        self.P2401.can.terminate()

    class P2401(Connector):
        transceiver_3_audio_in = Pin(3, "Transceiver 3 Audio In")
        transceiver_3_audio_low = Pin(4, "Transceiver 3 Audio Low")
        transceiver_3_mic_out_high = Pin(5, "Transceiver 3 Mic Out High")
        receiver_4_audio_in_high = Pin(7, "Receiver 4 Audio In")
        receiver_4_audio_in_low = Pin(8, "Receiver 4 Audio In")
        com_1_audio_in_high = Pin(9, "Com 1 Audio In High")
        com_1_audio_low = Pin(10, "Com 1 Audio Low")
        com_1_mic_audio_out_high = Pin(11, "Com 1 Mic Audio Out High")
        com_1_mic_key_out = Pin(12, "Com 1 Mic Key Out")
        com_2_audio_in_high = Pin(13, "Com 2 Audio In High")
        com_2_audio_low = Pin(14, "Com 2 Audio Low")
        com_2_mic_audio_out_high = Pin(15, "Com 2 Mic Audio Out High")
        pilot_ics_key = Pin(16, "Pilot ICS Key")
        nav_1_audio_in_high = Pin(17, "Nav 1 Audio In High")
        nav_1_audio_in_low = Pin(18, "Nav 1 Audio In Low")
        nav_2_audio_in_high = Pin(19, "Nav 2 Audio In High")
        nav_2_audio_in_low = Pin(20, "Nav 2 Audio In Low")
        receiver_3_audio_in_high = Pin(21, "Receiver 3 Audio In High")
        receiver_3_audio_in_low = Pin(22, "Receiver 3 Audio In Low")
        receiver_5_audio_in_high = Pin(23, "Receiver 5 Audio In High")
        com_active_out = Pin(24, "Com Active Out")
        alert_3_audio_in_high = Pin(29, "Alert 3 Audio In High")
        com_2_mic_key_out = Pin(30, "Com 2 Mic Key Out")
        alert_1_audio_in_high = Pin(31, "Alert 1 Audio In High")
        alert_1_audio_in_low = Pin(32, "Alert 1 Audio In Low")
        pilot_mic_audio_in_high = Pin(33, "Pilot Mic Audio In High")
        pilot_mic_key_in = Pin(34, "Pilot Mic Key In")
        pilot_mic_audio_in_low = Pin(35, "Pilot Mic Audio In Low")
        can = CanBus(36, 37)
        pass_headset_audio_out_left = Pin(40, "Pass Headset Audio Out Left")
        pass_headset_audio_out_right = Pin(41, "Pass Headset Audio Out Right")
        pass_headset_audio_low = Pin(42, "Pass Headset Audio Out Low")
        alert_3_4_aux_3_audio_in_low = Pin(43, "Alert 3, 4, Aux 3 Audio In Low")
        alert_4_audio_in_high = Pin(44, "Alert 4, Audio In High")

    class J2402(Connector):
        pilot_headset_audio_out_low = Pin(1, "Pilot Headset Audio Out Low")
        copilot_headset_audio_out_low = Pin(2, "Copilot Headset Audio Out Low")
        copilot_headset_audio_out_left = Pin(3, "Copilot Headset Audio Out Left")
        copilot_headset_audio_out_right = Pin(4, "Copilot Headset Audio Out Right")
        lighting_bus_low = Pin(5, "Lighting Bus Low")
        lighting_bus_14v_high_28v_low = Pin(6, "Lighting Bus 14v High/28v Low")
        lighting_bus_high = Pin(7, "Lighting Bus High")
        aircraft_power_a = Pin(8, "Aircraft Power")
        aircraft_power_b = Pin(9, "Aircraft Power")
        ground_a = Pin(10, "Ground A")
        ground_b = Pin(11, "Ground B")
        passenger_ics_key = Pin(13, "Passenger ICS Key")
        alert_2_low = Pin(14, "Alert 2 Low")
        alert_2_audio_in_high = Pin(15, "Alert 2 Audio In High")
        pilot_headset_audio_out_left = Pin(16, "Pilot Headset Audio Out Left")
        com_swap = Pin(20, "Com Swap")
        ground = Pin(21, "Ground")
        play_key = Pin(22, "Play Key")
        music_1_in_left = Pin(23, "Music 1 In Left")
        music_1_in_right = Pin(24, "Music 1 In Right")
        music_1_in_low = Pin(25, "Music 1 In Low")
        music_2_in_left = Pin(26, "Music 2 In Left")
        music_2_in_right = Pin(27, "Music 2 In Right")
        music_2_in_low = Pin(28, "Music 2 In Low")
        failsafe_warn_audio_in_high = Pin(29, "Failsafe Warn Audio In High")
        copilot_ics_key = Pin(30, "Copilot ICS Key")
        pilot_headset_audio_out_right = Pin(31, "Pilot Headset Audio Out Right")
        copilot_mic_audio_in_high = Pin(32, "Copilot Mic Audio In High")
        copilot_mic_key_in = Pin(33, "Copilot Mic Key In")
        copilot_mic_audio_in_low = Pin(34, "Copilot Mic Audio In")
        pass_1_mic_audio_in_high = Pin(35, "Pass 1 Mic Audio In High")
        pass_1_mic_audio_in_low = Pin(36, "Pass 1 Mic Audio In Low")
        pass_2_mic_audio_in_high = Pin(37, "Pass 2 Mic Audio In High")
        pass_2_mic_audio_in_low = Pin(38, "Pass 2 Mic Audio In Low")
        pass_3_mic_audio_in_high = Pin(39, "Pass 3 Mic Audio In High")
        pass_3_mic_audio_in_low = Pin(40, "Pass 3 Mic Audio In Low")
        pass_4_mic_audio_in_high = Pin(41, "Pass 4 Mic Audio In High")
        pass_4_mic_audio_in_low = Pin(42, "Pass 4 Mic Audio In Low")
        speaker_audio_out_low = Pin(43, "Speaker Audio Out Low")
        speaker_audio_out_high = Pin(44, "Speaker Audio Out High")


class GAP2620(Component):
    power = Pin("Red", "Power")
    ground = Pin("Blk", "Ground")
    signal = Pin("Blu", "Signal")


class _BaseP3251(Connector):
    alt_encoder_clock = Pin(1, "Alt Encoder Clock")
    usb_data_high = Pin(2, "USB Data High")
    arinc_429_out = ARINC429(5, 6, "out", name="ARINC 429 Out")
    rs232_1 = RS232(9, 31, 52, name="RS232 1")
    rs232_2 = RS232(8, 30, 51, name="RS232 2")
    rs232_3 = RS232(7, 29, 50, name="RS232 3")
    external_standby_select = Pin(14, "External Standby Select")
    transponder_fail_1 = Pin(17, "Transponder Fail 1")
    external_suppression = Pin(18, "External Suppression")
    ground_1 = Pin(20, "Ground 1")
    aircraft_power_1a = Pin(21, "Aircraft Power 1A")
    alt_encoder_data = Pin(22, "Alt Encoder Data")
    alt_encoder_ground = Pin(23, "Alt Encoder Ground")
    usb_data_low = Pin(24, "USB Data Low")
    arinc_429_in_1 = ARINC429(27, 28, "in", name="ARINC 429 In 1")
    external_ident_select = Pin(36, "External Identity Select")
    power_control = Pin(38, "Power Control")
    ground_2 = Pin(41, "Ground 2")
    aircraft_power_1b = Pin(42, "Aircraft Power 1B")
    alt_encoder_power = Pin(43, "Alt Encoder Power")
    usb_vbus_power = Pin(44, "USB Vbus Power")
    usb_ground = Pin(45, "USB Ground")
    arinc_429_in_2 = ARINC429(48, 49, "in", name="ARINC 429 In 2")
    power_config = Pin(59, "Power Config")
    aircraft_power_2a = Pin(61, "Aircraft Power 2a")
    aircraft_power_2b = Pin(62, "Aircraft Power 2b")


class GTX45R(Component):
    """Remote Transponder"""

    class P3251(_BaseP3251):
        time_mark_a = Pin(4, "Time Mark A")
        time_mark_b = Pin(26, "Time Mark B")
        gps_keep_alive = Pin(60, "GPS Keep Alive")

    class P3252(Connector):
        ethernet_out_1 = GarminEthernet(6, 1, "out", name="Ethernet Out 1")
        ethernet_in_1 = GarminEthernet(7, 2, "in", name="Ethernet In 1")
        ethernet_out_2 = GarminEthernet(8, 3, "out", name="Ethernet Out 2")
        ethernet_in_2 = GarminEthernet(9, 4, "in", name="Ethernet In 2")
        rs232 = RS232(5, 10, 15)
        rs422_a = Pin(11, "RS 422 A")
        rs422_b = Pin(12, "RS 422 B")


class G5(Component):
    def can_terminate(self) -> None:
        self.J51.can.terminate()

    class J51(Connector):
        can = CanBus(1, 2)
        unit_id = Pin(3, "Unit ID")
        rs232 = RS232(5, 4, 6)
        aircraft_power_1 = Pin(7, "Aircraft Power 1")
        aircraft_power_2 = Pin(8, "Aircraft Power 2")
        ground = Pin(9, "Ground")


class ConfigModule(Component):
    render = False
    power = Pin("RED", "Power")
    ground = Pin("BLK", "Ground")
    data = Pin("YLW", "Data")
    clock = Pin("WHT", "Clock")
