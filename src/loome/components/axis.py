from loome import ARINC429, HSDB, RS232, CanBus, Component, Connector, DifferentialPair, Pin


class GDU116B(Component):
    class J1011(Connector):
        can = CanBus(1, 2)
        bat_power = Pin(3, "Battery Power")
        rs232_6 = RS232(4, 5, 6)
        power_out_1 = Pin(7, "Power Out 1")
        power_out_2 = Pin(8, "Power Out 2")
        ground = Pin(9, "Ground")

    class J1012(Connector):
        mono_audio_out_high = Pin(1, "Mono Audio Out High")
        mono_audio_out_low = Pin(18, "Mono Audio Out Low")

        hsdb_1 = HSDB(3, 2, 20, 19, name="HSDB 1")
        hsdb_2 = HSDB(5, 4, 7, 6, name="HSDB 2")
        hsdb_3 = HSDB(22, 21, 39, 38, name="HSDB 3")
        rs232_1 = RS232(48, 47, 34, name="RS232 1")
        rs232_2 = RS232(30, 14, 35, name="RS232 2")
        rs232_3 = RS232(13, 29, 36, name="RS232 3")
        rs232_4 = RS232(40, 23, 37, name="RS232 4")
        rs232_5 = RS232(41, 24, 44, name="RS232 5")

        config_module_power_out = Pin(17, "Config Module Power Out")
        config_module_ground = Pin(49, "Config Module Ground")
        config_module_data = Pin(50, "Config Module Data")
        config_module_clock = Pin(33, "Config Module Clock")

        ground_1 = Pin(9, "Ground 1")
        ground_2 = Pin(10, "Ground 2")
        power_1 = Pin(11, "Power 1")
        power_2 = Pin(12, "Power 2")
        ground_3 = Pin(15, "Ground 3")
        ground_4 = Pin(16, "Ground 4")
        power_3 = Pin(31, "Power 3")
        power_4 = Pin(32, "Power 4")

        reversionary_mode = Pin(25, "Reversionary Mode")
        lighting_bus_1 = Pin(26, "Lighting Bus 1")
        signal_ground = Pin(27, "Signal Ground")
        lighting_bus_2 = Pin(43, "Lighting Bus 2")

        can = CanBus(46, 45)
        can_bus_term = Pin(28, "CAN Bus Term")
        demo_mode = Pin(42, "Demo Mode")

    def can_terminate(self) -> None:
        self.J1012.can.low >> self.J1012.can_bus_term


class GDU116C(GDU116B):
    class J1013(Connector):
        power = Pin(1, "Power")
        ground = Pin(22, "Ground")

        hsdb_4 = HSDB(21, 42, 20, 41, name="HSDB 4")
        rs232_7 = RS232(58, 57, 59, name="RS232 7")
        rs232_8 = RS232(61, 60, 62, name="RS232 8")

        arinc_in_1 = ARINC429(2, 23, direction="in", name="ARINC In 1")
        arinc_in_2 = ARINC429(3, 24, direction="in", name="ARINC In 2")
        arinc_in_3 = ARINC429(4, 25, direction="in", name="ARINC In 3")
        arinc_in_4 = ARINC429(5, 26, direction="in", name="ARINC In 4")
        arinc_in_5 = ARINC429(6, 27, direction="in", name="ARINC In 5")
        arinc_in_6 = ARINC429(7, 28, direction="in", name="ARINC In 6")

        arinc_out_1 = ARINC429(43, 44, direction="out", name="ARINC Out 1")
        arinc_out_2 = ARINC429(45, 46, direction="out", name="ARINC Out 2")
        arinc_out_3 = ARINC429(47, 48, direction="out", name="ARINC Out 3")

        rs485_422_1 = DifferentialPair(31, 10, name="RS485/422 1")
        rs485_422_2 = DifferentialPair(32, 11, name="RS485/422 2")
        rs485_422_3 = DifferentialPair(50, 49, name="RS485/422 3")

        discrete_in_1 = Pin(12, "Discrete In 1")
        discrete_in_2 = Pin(13, "Discrete In 2")
        discrete_in_3 = Pin(14, "Discrete In 3")
        discrete_in_4 = Pin(33, "Discrete In 4")
        discrete_in_5 = Pin(34, "Discrete In 5")
        discrete_in_6 = Pin(35, "Discrete In 6")
        discrete_in_7 = Pin(51, "Active Hi/Lo Discrete In 7")
        discrete_in_8 = Pin(52, "Active Hi/Lo Discrete In 8")
        discrete_in_9 = Pin(53, "Active Hi Discrete In 9")
        discrete_in_10 = Pin(54, "Active Hi Discrete In 10")

        discrete_out_1 = Pin(15, "Discrete Out 1")
        discrete_out_2 = Pin(16, "Discrete Out 2")
        discrete_out_3 = Pin(17, "Discrete Out 3")
        discrete_out_4 = Pin(36, "Discrete Out 4")
        discrete_out_5 = Pin(37, "Discrete Out 5")
        discrete_out_6 = Pin(38, "Discrete Out 6")
        discrete_out_7 = Pin(55, "Discrete Out 7")
        discrete_out_8 = Pin(56, "Discrete Out 8")

        pps_io_1_high = Pin(18, "PPS IO 1 High")
        pps_io_1_low = Pin(39, "PPS IO 1 Low")
        pps_io_2_high = Pin(19, "PPS IO 2 High")
        pps_io_2_low = Pin(40, "PPS IO 2 Low")

    class J1015(Connector):
        power_1 = Pin(1, "Power 1")
        power_2 = Pin(18, "Power 2")
        power_3 = Pin(35, "Power 3")
        ground_1 = Pin(2, "Ground 1")
        ground_2 = Pin(19, "Ground 2")
        ground_3 = Pin(36, "Ground 3")

        pilot_headset_left = Pin(3, "Headset 1 (Pilot) Left")
        pilot_headset_right = Pin(20, "Headset 1 (Pilot) Right")
        pilot_headset_ground = Pin(37, "Headset 1 (Pilot) Ground")
        copilot_headset_left = Pin(4, "Headset 2 (Copilot) Left")
        copilot_headset_right = Pin(21, "Headset 2 (Copilot) Right")
        copilot_headset_ground = Pin(38, "Headset 2 (Copilot) Ground")
        passengers_headset_left = Pin(5, "Headset 3/4 (Passengers) Left")
        passengers_headset_right = Pin(22, "Headset 3/4 (Passengers) Right")
        passengers_headset_ground = Pin(39, "Headset 3/4 (Passengers) Ground")

        mic_1_in = Pin(6, "Mic 1 In")
        mic_1_low = Pin(23, "Mic 1 Low")
        mic_2_in = Pin(7, "Mic 2 In")
        mic_2_low = Pin(24, "Mic 2 Low")
        mic_3_in = Pin(8, "Mic 3 In")
        mic_3_low = Pin(25, "Mic 3 Low")
        mic_4_in = Pin(9, "Mic 4 In")
        mic_4_low = Pin(26, "Mic 4 Low")

        mic_1_ptt = Pin(40, "Mic 1 PTT (Pilot, Audio Panel)/Com PTT")
        mic_2_ptt = Pin(41, "Mic 2 PTT (Copilot)")
        external_com_ptt_key_out = Pin(45, "External Com PTT Key Out")
        external_com_interlock_out = Pin(46, "External Com Interlock Out")

        alert_audio_in_1 = Pin(10, "Alert Audio In 1")
        alert_audio_in_low = Pin(27, "Alert Audio In Low")
        external_nav_audio_in = Pin(11, "External Nav Audio In")
        external_nav_audio_in_low = Pin(28, "External Nav Audio In Low")
        external_com_audio_in = Pin(12, "External Com Audio In")
        external_com_audio_in_low = Pin(29, "External Com Audio In Low")
        external_com_mic_audio_out = Pin(13, "External Com Mic Audio Out")
        external_com_mic_audio_out_low = Pin(30, "External Com Mic Audio Out Low")
        speaker_out = Pin(14, "Speaker Out")
        nav_audio_out = Pin(15, "Nav Audio Out")
        speaker_out_low = Pin(31, "Speaker Out Low")

        stereo_music_in_left = Pin(42, "Stereo Music In Left")
        stereo_music_in_right = Pin(43, "Stereo Music In Right")
        stereo_music_in_low = Pin(44, "Stereo Music In Low")

        discrete_in_1 = Pin(47, "Discrete In 1")
        discrete_in_2 = Pin(48, "Discrete In 2")
        discrete_in_3 = Pin(49, "Discrete In 3")
        discrete_in_4 = Pin(50, "Discrete In 4")
        discrete_in_5 = Pin(32, "Discrete In 5")
        discrete_in_6 = Pin(33, "Discrete In 6")


class GDU116NC(GDU116C):
    pass
