#!/usr/bin/env python3
# Test battery reading without Prometheus dependencies

from adc import ADC
import time

def get_battery_voltage():
    """Read battery voltage from Freenove ADC"""
    try:
        adc = ADC()
        pcb_version = adc.pcb_version
        voltage = adc.read_adc(2) * (3 if pcb_version == 1 else 2)
        return round(voltage, 2)
    except Exception as e:
        print(f"Error reading battery: {e}")
        return None

def calculate_battery_percentage(voltage):
    """Calculate battery percentage"""
    if voltage is None:
        return None
    
    min_voltage = 6.0   # Empty
    max_voltage = 8.4   # Fully charged
    
    if voltage >= max_voltage:
        return 100
    elif voltage <= min_voltage:
        return 0
    
    percentage = ((voltage - min_voltage) / (max_voltage - min_voltage)) * 100
    return round(percentage, 1)

if __name__ == "__main__":
    print("Testing Freenove Battery Reader...")
    print("=" * 40)
    
    for i in range(5):
        voltage = get_battery_voltage()
        percentage = calculate_battery_percentage(voltage)
        
        if voltage:
            print(f"Reading {i+1}: {voltage}V ({percentage}%)")
        else:
            print(f"Reading {i+1}: Failed")
        
        time.sleep(1)
    
    print("=" * 40)
    print("Test complete")
