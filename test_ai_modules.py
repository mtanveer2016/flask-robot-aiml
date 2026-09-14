#!/usr/bin/env python3
"""
Test script for AI modules
"""

import time
import sys

def test_ollama():
    print("Testing Ollama...")
    from ai_modules.llm.ollama_client import OllamaClient
    
    client = OllamaClient()
    if client.check_available():
        print("✅ Ollama is running")
        models = client.list_models()
        print(f"   Available models: {models}")
        
        # Test a simple chat
        response = client.chat("Hello! Tell me a short joke about robots.")
        print(f"   Response: {response.get('content', 'No response')}")
        return True
    else:
        print("❌ Ollama is not running. Start with: ollama serve")
        return False

def test_whisper():
    print("Testing Whisper...")
    from ai_modules.speech.whisper_client import WhisperClient
    
    client = WhisperClient()
    if client.check_available():
        print("✅ Whisper is available")
        print(f"   Model: {client.model_path}")
        print(f"   Binary: {client.whisper_cpp_path}")
        return True
    else:
        print("❌ Whisper not configured properly")
        print("   Make sure whisper.cpp is built and models are downloaded")
        return False

def test_piper():
    print("Testing Piper...")
    from ai_modules.speech.piper_client import PiperClient
    
    client = PiperClient()
    if client.check_available():
        print("✅ Piper is available")
        print(f"   Model: {client.model_path}")
        print(f"   Binary: {client.piper_path}")
        return True
    else:
        print("❌ Piper not configured properly")
        return False

def test_vision():
    print("Testing Vision (Moondream)...")
    from ai_modules.vision.moondream_client import MoondreamClient
    
    client = MoondreamClient()
    print("✅ Moondream client created")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("Testing AI Modules")
    print("=" * 50)
    
    results = []
    results.append(("Ollama", test_ollama()))
    results.append(("Whisper", test_whisper()))
    results.append(("Piper", test_piper()))
    results.append(("Moondream", test_vision()))
    
    print("\n" + "=" * 50)
    print("Results:")
    for name, result in results:
        print(f"  {name}: {'✅ PASSED' if result else '❌ FAILED'}")
