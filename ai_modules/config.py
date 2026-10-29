"""
AI Module Configuration
Centralizes all paths and settings for AI components
"""

import os

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")

# ================= Whisper.cpp Configuration =================
WHISPER_CONFIG = {
    "model_path": "/models/ggml-tiny.en-q5_1.bin",
    "whisper_cpp_path": "/opt/whisper/whisper-cli",
    "default_language": "en",
}

# ================= Piper TTS Configuration =================
PIPER_CONFIG = {
    "model_path": "/app/models/piper/models/en_US-amy-medium.onnx",
    "piper_path": "/app/models/piper/piper",
    "default_voice": "en_US-amy-medium",
}

# ================= Ollama Configuration =================
# Auto-detects which Ollama to use:
#   1. If OLLAMA_HOST env var is set -> use that
#   2. Try the desktop PC over Tailscale (fast) -> 10-second timeout
#   3. Fall back to the Pi's local Ollama (slow but always available)
PC_OLLAMA_TAILSCALE_IP = "100.116.38.102"   # Your PC's Tailscale IP
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
            timeout=10.0,
        )
        s.close()
        print(f"? Ollama: using PC at {PC_OLLAMA_TAILSCALE_IP}")
        return PC_OLLAMA_TAILSCALE_IP
    except OSError:
        pass

    # 3. Fall back to local Pi
    print("?? Ollama: PC unreachable, using local Pi")
    return "localhost"


# Get the active host once at startup
_ACTIVE_OLLAMA_HOST = _detect_ollama_host()

OLLAMA_CONFIG = {
    "base_url": f"http://{_ACTIVE_OLLAMA_HOST}:{OLLAMA_PORT}",
    "vision_base_url": f"http://{_ACTIVE_OLLAMA_HOST}:{OLLAMA_PORT}", 
    "llm_model": "llama3.2:3b",
    "vision_model": "moondream:latest",
    "keep_alive": -1,  # <-- INTEGER (-1), not string
}

# ================= Audio Settings =================
AUDIO_CONFIG = {
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav",
}
