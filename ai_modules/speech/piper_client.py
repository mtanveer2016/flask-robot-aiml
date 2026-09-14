"""
Piper TTS Client - Text-to-Speech synthesis
"""

import os
import subprocess
import tempfile
from typing import Optional, Dict, Any
import base64
import wave
from ..config import PIPER_CONFIG


class PiperClient:
    """
    Client for Piper TTS (Text-to-Speech).
    Runs locally for privacy and low latency.
    """
    
    def __init__(self, 
                 model_path: str = PIPER_CONFIG["model_path"],
                 piper_path: str = PIPER_CONFIG["piper_path"]):
        self.model_path = model_path
        self.piper_path = piper_path
        self.last_audio = None
        self.voice = "en_US-amy-medium"
    
    def synthesize(self, text: str, output_path: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to speak
            output_path: Optional path to save audio
        
        Returns:
            Audio bytes (WAV format)
        """
        if not os.path.exists(self.piper_path):
            return b"Error: piper not found"
        
        if not os.path.exists(self.model_path):
            return b"Error: Piper model not found"
        
        try:
            if output_path:
                # Save to file
                cmd = [
                    self.piper_path,
                    "-m", self.model_path,
                    "-f", output_path,
                    "--output-raw"
                ]
                subprocess.run(cmd, input=text.encode('utf-8'), capture_output=True, timeout=30)
                with open(output_path, 'rb') as f:
                    return f.read()
            else:
                # Return bytes
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    temp_path = f.name
                
                cmd = [
                    self.piper_path,
                    "-m", self.model_path,
                    "-f", temp_path,
                    "--output-raw"
                ]
                subprocess.run(cmd, input=text.encode('utf-8'), capture_output=True, timeout=30)
                
                with open(temp_path, 'rb') as f:
                    audio_bytes = f.read()
                
                os.unlink(temp_path)
                self.last_audio = audio_bytes
                return audio_bytes
                
        except subprocess.TimeoutExpired:
            return b"Error: Synthesis timed out"
        except Exception as e:
            return f"Error: {str(e)}".encode('utf-8')
    
    def synthesize_to_base64(self, text: str) -> str:
        """Synthesize and return as base64 for web playback"""
        audio_bytes = self.synthesize(text)
        return base64.b64encode(audio_bytes).decode('utf-8')
    
    def check_available(self) -> bool:
        """Check if Piper is available"""
        return os.path.exists(self.piper_path) and os.path.exists(self.model_path)
    
    def get_voices(self) -> list:
        """Get available Piper voices"""
        model_dir = os.path.dirname(self.model_path)
        voices = []
        for f in os.listdir(model_dir):
            if f.endswith('.onnx'):
                voices.append(f.replace('.onnx', ''))
        return voices
    
    def set_voice(self, voice: str):
        """Change the voice model"""
        model_dir = os.path.dirname(self.model_path)
        new_path = os.path.join(model_dir, f"{voice}.onnx")
        if os.path.exists(new_path):
            self.model_path = new_path
            self.voice = voice
            return True
        return False
