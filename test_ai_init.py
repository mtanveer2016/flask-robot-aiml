#!/usr/bin/env python3
"""
Test AI Initialization Only
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Testing AI Initialization")
print("=" * 60)

print("\n1. Importing ai_routes...")
try:
    from ai_routes import init_agent, register_robot_tools
    print("   ✅ ai_routes imported")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    sys.exit(1)

print("\n2. Importing ai_modules...")
try:
    from ai_modules import RobotAgent
    print("   ✅ ai_modules imported")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    sys.exit(1)

print("\n3. Creating dummy hardware...")
class DummyPWM:
    def set_motor_model(self, *args): pass

class DummyBuzzer:
    def set_state(self, state): pass

class DummyLED:
    def ledIndex(self, *args): pass

pwm = DummyPWM()
buzzer = DummyBuzzer()
led = DummyLED()
print("   ✅ Hardware created")

print("\n4. Creating RobotController...")
class RobotController:
    def __init__(self, pwm, buzzer, led):
        self.pwm = pwm
        self.buzzer = buzzer
        self.led = led
    
    def forward(self, speed=50):
        return f"Forward {speed}"
    
    def stop(self):
        return "Stop"

robot_controller = RobotController(pwm, buzzer, led)
print("   ✅ RobotController created")

print("\n5. Initializing AI Agent...")
try:
    agent = init_agent()
    print("   ✅ Agent initialized")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n6. Registering tools...")
try:
    register_robot_tools(agent, robot_controller)
    print("   ✅ Tools registered")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n7. Results:")
print(f"   Agent: {agent}")
print(f"   LLM Model: {agent.llm.model}")
print(f"   Tools: {agent.tools.get_tool_names()}")
print(f"   Status: {agent.get_status()}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60);
