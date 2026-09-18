"""
AI Module Configuration
Centralizes all paths and settings for AI components
"""

import os

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")

# ================= Whisper.cpp Configuration =================
# Binary + libraries are baked into the image at /opt/whisper
# Model file stays on the host mount at /root/whisper.cpp/models
WHISPER_CONFIG = {
    "model_path": "/root/whisper.cpp/models/ggml-base.en.bin",
    "whisper_cpp_path": "/opt/whisper/whisper-cli",
    "default_language": "en",
}

# ================= Piper TTS Configuration =================
# Host's /home/aiml/piper is mounted at /app/models/piper
PIPER_CONFIG = {
    "model_path": "/app/models/piper/models/en_US-amy-medium.onnx",
    "piper_path": "/app/models/piper/piper",
    "default_voice": "en_US-amy-medium",
}

# ================= Ollama Configuration =================
OLLAMA_CONFIG = {
    "base_url": "http://localhost:11434",
    "llm_model": "llama3.2:3b",
    "vision_model": "moondream:latest",
}

# ================= Audio Settings =================
AUDIO_CONFIG = {
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav",
}
