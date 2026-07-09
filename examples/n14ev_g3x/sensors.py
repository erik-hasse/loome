from loome.components import GPIOSensor, HighLowSensor, SingleInputSensor

fuel_pressure = GPIOSensor("Fuel Pressure")
oil_pressure = GPIOSensor("Oil Pressure")
manifold_pressure = GPIOSensor("Manifold Pressure")
oil_temp = HighLowSensor("Oil Temperature")
left_fuel = SingleInputSensor("Left Fuel Quantity")
right_fuel = SingleInputSensor("Right Fuel Quantity")
