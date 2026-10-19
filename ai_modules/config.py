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
#    "model_path": "/root/whisper.cpp/models/ggml-base.en.bin",
#    "model_path": "/root/whisper.cpp/models/ggml-tiny.en-q5_1.bin",
    "model_path": "/models/ggml-tiny.en-q5_1.bin",
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
#OLLAMA_CONFIG = {
#    "base_url": "http://localhost:11434",
#    "llm_model": "llama3.2:3b",
#    "vision_model": "moondream:latest",

# ================= Ollama Configuration =================
# Auto-detects which Ollama to use:
#   1. If OLLAMA_HOST env var is set ? use that
#   2. Try the desktop PC over Tailscale (fast) — 3-second timeout
#   3. Fall back to the Pi's local Ollama (slow but always available)
#
# Set the PC's Tailscale IP below.
PC_OLLAMA_TAILSCALE_IP = "100.116.38.102"   # <-- CHANGE THIS
OLLAMA_PORT = 11434

import socket as _socket

def _detect_ollama_host():
    import os as _os

    # 1. Explicit override via env var
    if _os.environ.get("OLLAMA_HOST"):
        return _os.environ["OLLAMA_HOST"]

    # 2. Try the PC over Tailscale
    try:
        s = _socket.create_connection(
            (PC_OLLAMA_TAILSCALE_IP, OLLAMA_PORT),
            timeout=1.0,
        )
        s.close()
        print(f"? Ollama: using PC at {PC_OLLAMA_TAILSCALE_IP}")
        return PC_OLLAMA_TAILSCALE_IP
    except OSError:
        pass

    # 3. Fall back to local Pi
    print("??  Ollama: PC unreachable, using local Pi")
    return "localhost"


OLLAMA_CONFIG = {
    "base_url": f"http://{_detect_ollama_host()}:{OLLAMA_PORT}",
    "llm_model": "llama3.2:3b",
    "vision_model": "moondream:latest",
}
}

# ================= Audio Settings =================
AUDIO_CONFIG = {
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav",
}
