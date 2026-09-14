#!/usr/bin/env python3
"""
Test vision capabilities with the AI agent
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_modules import RobotAgent
from ai_modules.vision.camera_capture import CameraCapture

def test_camera():
    """Test camera capture"""
    print("📷 Testing camera...")
    camera = CameraCapture()
    if camera.initialize():
        frame = camera.capture_frame()
        if frame is not None:
            print("✅ Camera capture successful!")
            print(f"   Frame shape: {frame.shape}")
        else:
            print("❌ Failed to capture frame")
        camera.release()
    else:
        print("❌ Camera initialization failed")

def test_vision_tools():
    """Test vision tools with the AI agent"""
    print("\n🤖 Testing vision tools...")
    
    agent = RobotAgent()
    
    # Test see_camera
    print("\n📸 Testing see_camera...")
    try:
        result = agent.process_command("What do you see?")
        print(f"   Response: {result.get('response', 'No response')}")
        if result.get('tool_calls'):
            print(f"   Tools used: {[t['tool'] for t in result['tool_calls']]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test detect_object
    print("\n🔍 Testing detect_object...")
    try:
        result = agent.process_command("Find a ball")
        print(f"   Response: {result.get('response', 'No response')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

def test_moondream_direct():
    """Test Moondream directly with camera"""
    print("\n🧠 Testing Moondream directly...")
    from ai_modules.vision.moondream_client import MoondreamClient
    
    client = MoondreamClient()
    result = client.analyze_camera("Describe what you see in detail")
    print(f"   Description: {result}")

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 AI Vision Test")
    print("=" * 60)
    
    test_camera()
    test_vision_tools()
    # test_moondream_direct()
    
    print("\n" + "=" * 60)
    print("Test complete!")
