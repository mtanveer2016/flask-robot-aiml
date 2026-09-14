#!/usr/bin/env python3
"""
Test hardware directly without Flask/K3s
"""

import time
import sys
import os

print("=" * 60)
print("Hardware Test")
print("=" * 60)

# ================= TEST 1: GPIO =================
print("\n1. Testing GPIO...")
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    
    # Test a few common pins
    test_pins = [17, 18, 22, 23, 24, 25]
    for pin in test_pins:
        try:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.05)
            GPIO.output(pin, GPIO.LOW)
            print(f"   ✅ Pin {pin} works")
        except Exception as e:
            print(f"   ❌ Pin {pin} failed: {e}")
    
    GPIO.cleanup()
    print("✅ GPIO test passed")
except Exception as e:
    print(f"❌ GPIO test failed: {e}")

# ================= TEST 2: BUZZER =================
print("\n2. Testing Buzzer...")
try:
    from buzzer import Buzzer
    buzzer = Buzzer()
    print("✅ Buzzer initialized")
    
    # Try to beep
    print("   🔔 Beeping...")
    buzzer.set_state(True)
    time.sleep(0.5)
    buzzer.set_state(False)
    print("✅ Buzzer test passed")
except Exception as e:
    print(f"❌ Buzzer test failed: {e}")

# ================= TEST 3: LED =================
print("\n3. Testing LED...")
try:
    from led import Led
    led = Led()
    print("✅ LED initialized")
    
    print("   🔴 Red")
    led.ledIndex(0xFF, 255, 0, 0)
    time.sleep(0.5)
    
    print("   🟢 Green")
    led.ledIndex(0xFF, 0, 255, 0)
    time.sleep(0.5)
    
    print("   🔵 Blue")
    led.ledIndex(0xFF, 0, 0, 255)
    time.sleep(0.5)
    
    print("   ⚫ Off")
    led.ledIndex(0xFF, 0, 0, 0)
    
    print("✅ LED test passed")
except Exception as e:
    print(f"❌ LED test failed: {e}")

# ================= TEST 4: MOTOR =================
print("\n4. Testing Motor...")
try:
    from motor import Ordinary_Car
    pwm = Ordinary_Car()
    print("✅ Motor initialized")
    
    print("   🚗 Moving forward (1 second)...")
    pwm.set_motor_model(500, 500, 500, 500)
    time.sleep(1)
    pwm.set_motor_model(0, 0, 0, 0)
    print("✅ Motor test passed")
except Exception as e:
    print(f"❌ Motor test failed: {e}")

# ================= TEST 5: CAMERA =================
print("\n5. Testing Camera...")
try:
    from picamera2 import Picamera2
    picam2 = Picamera2()
    config = picam2.create_video_configuration(main={"size": (640, 480)})
    picam2.configure(config)
    picam2.start()
    time.sleep(1)
    
    frame = picam2.capture_array()
    picam2.stop()
    print(f"✅ Camera test passed (frame shape: {frame.shape})")
except Exception as e:
    print(f"❌ Camera test failed: {e}")

# ================= TEST 6: I2C =================
print("\n6. Testing I2C Devices...")
try:
    import smbus2
    bus = smbus2.SMBus(1)
    
    # Scan for I2C devices
    devices = []
    for addr in range(0x03, 0x78):
        try:
            bus.write_quick(addr)
            devices.append(hex(addr))
        except:
            pass
    
    if devices:
        print(f"✅ I2C devices found: {', '.join(devices)}")
    else:
        print("❌ No I2C devices found")
except Exception as e:
    print(f"❌ I2C test failed: {e}")

print("\n" + "=" * 60)
print("Hardware Test Complete")
print("=" * 60)
