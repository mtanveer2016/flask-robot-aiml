"""
AI Module Configuration
Centralizes all paths and settings for AI components
"""

import os

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Home directory - define this first!
HOME = os.path.expanduser("~")

# ================= Whisper.cpp Configuration =================
# Using the new whisper-cli (not the deprecated 'main')
WHISPER_CONFIG = {
    "model_path": os.path.join(HOME, "whisper.cpp/models/ggml-base.en.bin"),
    "whisper_cpp_path": os.path.join(HOME, "whisper.cpp/build/bin/whisper-cli"),
    "default_language": "en",
}

# ================= Piper TTS Configuration =================
PIPER_CONFIG = {
    "model_path": os.path.join(PROJECT_ROOT, "models/piper/en_US-amy-medium.onnx"),
    "piper_path": os.path.join(PROJECT_ROOT, "models/piper/piper"),
    "default_voice": "en_US-amy-medium",
}

# ================= Ollama Configuration =================
OLLAMA_CONFIG = {
    "base_url": "http://localhost:11434",
    "llm_model": "llama3.2:3b",
    "vision_model": "moondream",
}

# ================= Audio Settings =================
AUDIO_CONFIG = {
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav",
}
