from loome import GPIO, Component, Pin


class RayAllanTrim(Component):
    position = GPIO("Or", "Gr", "Bl", name="Position")  # positive, signal, ground
    trim_1 = Pin("Wh", "Trim 1")
    trim_2 = Pin("Gy", "Trim 2")


class Stick(Component):
    ap_disconnect = Pin(10, "AP Disconnect")
