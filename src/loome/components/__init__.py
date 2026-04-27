from loome import GPIO, Component, Pin


class RayAllanTrim(Component):
    position = GPIO("Or", "Gr", "Bl", name="Position")  # positive, signal, ground
    trim_1 = Pin("Wh", "Trim 1")
    trim_2 = Pin("Gy", "Trim 2")


class Stick(Component):
    ap_disconnect = Pin(1, "AP Disconnect")
    push_to_talk = Pin(2, "Push to Talk")
    com_swap = Pin(3, "COM Swap")
    replay = Pin(4, "Replay")


class LEMO(Component):
    power = Pin(1, "Power")
    ground = Pin(2, "Ground")
    audio_left = Pin(3, "Audio Left")
    audio_right = Pin(4, "Audio Right")
    mic_high = Pin(5, "Mic High")
    mic_low = Pin(6, "Mic Low")


class TRS(Component):
    tip = Pin("T", "Tip")
    ring = Pin("R", "Ring")
    sleeve = Pin("S", "Sleeve")
