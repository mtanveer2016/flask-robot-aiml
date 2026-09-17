"""
Piper TTS Client - Text-to-Speech synthesis
"""

import os
import subprocess
import tempfile
from typing import Optional, Dict, Any
import base64
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
        
        print(f"📢 Piper binary: {self.piper_path}")
        print(f"📢 Piper model:  {self.model_path}")
    
    def synthesize(self, text: str, output_path: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to speak
            output_path: Optional path to save audio (WAV format)
        
        Returns:
            Audio bytes (WAV format)
        """
        if not os.path.exists(self.piper_path):
            print(f"❌ Piper binary not found: {self.piper_path}")
            return b""
        
        if not os.path.exists(self.model_path):
            print(f"❌ Piper model not found: {self.model_path}")
            return b""
        
        # Determine output path
        if output_path:
            target = output_path
            cleanup = False
        else:
            # Use a unique path in /tmp
            fd, target = tempfile.mkstemp(suffix='.wav', prefix='piper_')
            os.close(fd)  # Close the FD so Piper can write to it
            cleanup = True
        
        try:
            cmd = [
                self.piper_path,
                "-m", self.model_path,
                "-f", target
            ]
            
            print(f"🔊 Running Piper: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                input=text.encode('utf-8'),
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"❌ Piper error (rc={result.returncode})")
                print(f"   stderr: {result.stderr.decode()[:300]}")
                print(f"   stdout: {result.stdout.decode()[:300]}")
                return b""
            
            # Read the file
            if not os.path.exists(target):
                print(f"❌ Piper output file not created: {target}")
                return b""
            
            file_size = os.path.getsize(target)
            print(f"📁 Piper output file size: {file_size} bytes")
            
            if file_size == 0:
                print("❌ Piper output file is empty")
                print(f"   stderr: {result.stderr.decode()[:300]}")
                return b""
            
            with open(target, 'rb') as f:
                audio_bytes = f.read()
            
            print(f"✅ Piper generated {len(audio_bytes)} bytes (WAV header: {audio_bytes[:4]})")
            self.last_audio = audio_bytes
            return audio_bytes
            
        except subprocess.TimeoutExpired:
            print("❌ Piper timeout")
            return b""
        except Exception as e:
            print(f"❌ Piper exception: {e}")
            import traceback
            traceback.print_exc()
            return b""
        finally:
            if cleanup and os.path.exists(target):
                try:
                    os.unlink(target)
                except:
                    pass
    
    def synthesize_to_base64(self, text: str) -> str:
        """Synthesize and return as base64 for web playback"""
        audio_bytes = self.synthesize(text)
        if not audio_bytes:
            return ""
        return base64.b64encode(audio_bytes).decode('utf-8')
    
    def check_available(self) -> bool:
        """Check if Piper is available"""
        return os.path.exists(self.piper_path) and os.path.exists(self.model_path)
    
    def get_voices(self) -> list:
        """Get available Piper voices"""
        model_dir = os.path.dirname(self.model_path)
        voices = []
        if os.path.exists(model_dir):
            for f in os.listdir(model_dir):
                if f.endswith('.onnx'):
                    voices.append(f.replace('.onnx', ''))
        return voices
    
    def set_voice(self, voice: str) -> bool:
        """Change the voice model"""
        model_dir = os.path.dirname(self.model_path)
        new_path = os.path.join(model_dir, f"{voice}.onnx")
        if os.path.exists(new_path):
            self.model_path = new_path
            self.voice = voice
            return True
        return False
