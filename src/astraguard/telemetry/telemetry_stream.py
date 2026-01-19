import json
import time
import random
import sys
import math

def generate_telemetry():
    """Generate simulated telemetry data."""
    start_time = time.time()
    
    while True:
        current_time = time.time()
        elapsed = current_time - start_time
        
        # Simulate sine wave voltage with noise
        voltage = 8.0 + 0.5 * math.sin(elapsed * 0.1) + random.uniform(-0.1, 0.1)
        
        # Simulate current
        current = 1.2 + 0.2 * math.cos(elapsed * 0.2) + random.uniform(-0.05, 0.05)
        
        # Simulate temperature rising slowly
        temperature = 25.0 + 5.0 * math.sin(elapsed * 0.05) + random.uniform(-0.5, 0.5)
        
        # Simulate gyro
        gyro = 0.0 + 0.02 * math.sin(elapsed * 0.5) + random.uniform(-0.01, 0.01)
        
        # Simulate wheel speed
        wheel_speed = 5000 + 100 * math.sin(elapsed * 0.1) + random.uniform(-50, 50)
        
        # Inject occasional faults
        fault_injected = False
        if random.random() < 0.01:  # 1% chance of fault
            fault_type = random.choice(["voltage_drop", "temp_spike", "gyro_drift"])
            if fault_type == "voltage_drop":
                voltage = 6.5
            elif fault_type == "temp_spike":
                temperature = 45.0
            elif fault_type == "gyro_drift":
                gyro = 0.2
            fault_injected = True
            
        data = {
            "timestamp": current_time,
            "voltage": voltage,
            "current": current,
            "temperature": temperature,
            "gyro": gyro,
            "wheel_speed": wheel_speed
        }
        
        message = {
            "data": data,
            "fault": fault_injected
        }
        
        print(json.dumps(message))
        sys.stdout.flush()
        
        time.sleep(0.5)  # 2 Hz

if __name__ == "__main__":
    try:
        generate_telemetry()
    except KeyboardInterrupt:
        pass
