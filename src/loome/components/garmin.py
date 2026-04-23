from loome import GPIO, RS232, CanBus, Component, Connector, Pin
from loome.constants import Axis


class GAD27(Component):
    """Flap, Lights, Trim Controller"""

    class J271(Connector):
        can = CanBus(1, 2)
        can_term = Pin(3, "Can Term")
        signal_ground = Pin(4, "Signal Ground")

        power_in = Pin(7, "Power In")
        power_gndr = Pin(8, "Power Ground")

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
        discrete_in_16 = Pin(49, "Discrete In 16")

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


class GAD29(Component):
    class J291(Connector):
        can = CanBus(1, 2)
        ground = Pin(3, "Ground")
        power_1 = Pin(7, "Power 1")
        power_2 = Pin(8, "Power 2")

    class J282(Connector):
        # TODO
        pass


class GSU25(Component):
    """Air Data Unit"""

    class J251(Connector):
        ground = Pin(6, "Ground")
        power = Pin(7, "Power")
        backup_power = Pin(8, "Backup Power")

        can = CanBus(1, 2)
        rs232 = RS232(5, 4, 6, name="RS-232")  # tx, rx, gnd

    class J252(Connector):
        oat_probe_power = Pin(1, "OAT Probe Power")
        oat_probe_high = Pin(2, "OAT Probe High")
        oat_probe_low = Pin(3, "OAT Probe Low")

        rs232_3 = RS232(9, 10, 11, name="RS-232 3")  # tx, rx, gnd

        magnetometer_power = Pin(6, "Magnetometer Power")


class _P4X01(Connector):
    can = CanBus(1, 2)
    rs232 = RS232(4, 5, 6, name="RS-232")
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

    aircraft_power_1_ = Pin(32, "Aircraft Power 1")
    aircraft_power_2 = Pin(31, "Aircraft Power 2")
    ground_1 = Pin(15, "Ground 1")
    ground_2 = Pin(16, "Ground 2")

    config_module_power_out = Pin(17, "Config Module Power Out")
    config_module_ground = Pin(49, "Config Module Ground")
    config_module_data = Pin(50, "Config Module Data")
    config_module_clock = Pin(33, "Config Module Clock")

    lighting_bus_high_28V = Pin(22, "Lighting Bus High 28V")
    lighting_bus_high_14V = Pin(43, "Lighting Bus High 14V")


class GDU460(Component):
    """Display Unit"""

    class P4601(_P4X01):
        pass

    class P4602(_P4X02):
        pass


class OATProbe(Component):
    oat_probe_power = Pin(1, "OAT Probe Power")
    oat_probe_high = Pin(2, "OAT Probe High")
    oat_probe_low = Pin(3, "OAT Probe Low")


class GTX45R(Component):
    """Remote Transponder"""

    class P3251(Connector):
        rs232 = RS232(9, 31, 11, name="RS-232")  # tx, rx, gnd


class GMU11(Component):
    """Magnetometer"""

    class J441(Connector):
        power = Pin(8, "Power")
        backup_power = Pin(7, "Backup Power")
        ground = Pin(9, "Ground")
        can = CanBus(1, 2)


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
        rs232 = RS232(7, 8, name="RS-232")


class GEA24(Component):
    """EIS Interface"""

    class J244(Connector):
        gp1 = GPIO(18, 19, 20, name="GP1")  # positive, signal, ground
        gp2 = GPIO(21, 22, 23, name="GP2")  # positive, signal, ground


class GMC507(Component):
    """Autopilot controller"""

    class P7001(Connector):
        remote_go_around = Pin(10, "Remote Go-Around")


class GTN650Xi(Component):
    """GPS/NAV/COM"""

    class P1001(Connector):
        remote_go_around = Pin(37, "Remote Go-Around")
