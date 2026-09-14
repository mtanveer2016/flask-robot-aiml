import ultrasonic
import time

print("Testing Ultrasonic Sensor...")
print("Place hand in front of sensor to test")
print("-" * 40)

sensor = ultrasonic.Ultrasonic()

try:
    while True:
        distance = sensor.get_distance()
        if distance:
            print(f"Distance: {distance:.1f}cm")
        else:
            print("No reading")
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\nTest stopped")
