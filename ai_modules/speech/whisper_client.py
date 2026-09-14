"""
Whisper Speech-to-Text Client
Uses Whisper.cpp for local speech recognition
"""

import os
import subprocess
import tempfile
import re
from typing import Optional, Dict, Any

# Try to import config, but fallback to defaults if not available
try:
    from ..config import WHISPER_CONFIG
except ImportError:
    # Fallback defaults
    HOME = os.path.expanduser("~")
    WHISPER_CONFIG = {
        "model_path": os.path.join(HOME, "whisper.cpp/models/ggml-base.en.bin"),
        "whisper_cpp_path": os.path.join(HOME, "whisper.cpp/build/bin/whisper-cli"),
        "default_language": "en",
    }


class WhisperClient:
    """
    Client for Whisper.cpp speech-to-text.
    Uses the new whisper-cli command (the 'main' binary is deprecated).
    """
    
    def __init__(self, 
                 model_path: str = None,
                 whisper_cpp_path: str = None,
                 language: str = None):
        """
        Initialize Whisper client.
        
        Args:
            model_path: Path to the whisper model file
            whisper_cpp_path: Path to the whisper-cli executable
            language: Language code (en, es, fr, etc.)
        """
        # Use config values if not provided
        self.model_path = model_path or WHISPER_CONFIG["model_path"]
        self.whisper_cpp_path = whisper_cpp_path or WHISPER_CONFIG["whisper_cpp_path"]
        self.language = language or WHISPER_CONFIG["default_language"]
        
        # Expand paths (handles ~)
        self.model_path = os.path.expanduser(self.model_path)
        self.whisper_cpp_path = os.path.expanduser(self.whisper_cpp_path)
        
        self.last_transcript = ""
    
    def transcribe_file(self, audio_path: str, language: str = None) -> str:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to audio file (WAV format)
            language: Language code (en, es, fr, etc.)
        
        Returns:
            Transcribed text
        """
        # Use provided language or default
        lang = language or self.language
        
        # Check if files exist
        if not os.path.exists(self.whisper_cpp_path):
            return f"Error: whisper-cli not found at {self.whisper_cpp_path}"
        
        if not os.path.exists(self.model_path):
            return f"Error: Model not found at {self.model_path}"
        
        if not os.path.exists(audio_path):
            return f"Error: Audio file not found: {audio_path}"
        
        try:
            # Run whisper-cli with output options
            # -otxt: Save output to a .txt file
            cmd = [
                self.whisper_cpp_path,
                "-m", self.model_path,
                "-f", audio_path,
                "-l", lang,
                "--no-gpu",  # Use CPU (Raspberry Pi doesn't have CUDA)
                "-otxt"      # Output text file
            ]
            
            print(f"Running: {' '.join(cmd)}")
            
            # Run the command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=120  # 2 minute timeout for long audio
            )
            
            # Parse the output
            transcript = self._parse_transcription(result.stdout, result.stderr, audio_path)
            
            self.last_transcript = transcript
            return transcript
            
        except subprocess.TimeoutExpired:
            return "Error: Transcription timed out (audio may be too long)"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _parse_transcription(self, stdout: str, stderr: str, audio_path: str = None) -> str:
        """
        Parse the transcription from whisper-cli output.
        
        whisper-cli outputs lines like:
        [00:00:00.000 --> 00:00:04.220]   The birch canoe slid on the smooth planks.
        
        We extract just the transcribed text.
        """
        transcript_lines = []
        
        # Look for lines with timestamps
        # Pattern: [HH:MM:SS.mmm --> HH:MM:SS.mmm]   Text
        pattern = r'\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]\s*(.+)'
        
        for line in stdout.split('\n'):
            match = re.match(pattern, line)
            if match:
                text = match.group(1).strip()
                if text:
                    transcript_lines.append(text)
        
        # If we found transcript lines, join them
        if transcript_lines:
            return ' '.join(transcript_lines)
        
        # Fallback: check if there's a .txt file generated
        if audio_path:
            txt_path = audio_path + '.txt'
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, 'r') as f:
                        content = f.read()
                        # Remove timestamps from the txt file
                        lines = []
                        for line in content.split('\n'):
                            match = re.match(pattern, line)
                            if match:
                                lines.append(match.group(1).strip())
                        if lines:
                            return ' '.join(lines)
                        return content.strip()
                except:
                    pass
        
        # If we still have nothing, check stderr for errors
        if stderr:
            return f"Error: {stderr.strip()}"
        
        return "No transcription found"
    
    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe audio from bytes.
        
        Args:
            audio_bytes: Raw audio bytes (WAV format)
            sample_rate: Sample rate of audio (unused, kept for compatibility)
        
        Returns:
            Transcribed text
        """
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name
        
        try:
            result = self.transcribe_file(temp_path)
            return result
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            # Also clean up the .txt file that whisper-cli creates
            txt_path = temp_path + '.txt'
            if os.path.exists(txt_path):
                os.unlink(txt_path)
    
    def check_available(self) -> bool:
        """Check if whisper.cpp is available and configured."""
        model_exists = os.path.exists(self.model_path)
        binary_exists = os.path.exists(self.whisper_cpp_path)
        
        # Print debug info
        print(f"   Model path: {self.model_path} -> {'✅' if model_exists else '❌'}")
        print(f"   Binary path: {self.whisper_cpp_path} -> {'✅' if binary_exists else '❌'}")
        
        if not model_exists:
            print("   💡 Tip: Download model with:")
            print("      cd ~/whisper.cpp && bash models/download-ggml-model.sh base.en")
        if not binary_exists:
            print("   💡 Tip: Build whisper.cpp with:")
            print("      cd ~/whisper.cpp && mkdir -p build && cd build && cmake .. && make -j4")
        
        return model_exists and binary_exists
    
    def get_available_models(self) -> list:
        """Get available whisper models in the models directory."""
        model_dir = os.path.dirname(self.model_path)
        models = []
        if os.path.exists(model_dir):
            for f in os.listdir(model_dir):
                if f.endswith('.bin') and 'ggml' in f:
                    models.append(f)
        return models
    
    def set_model(self, model_name: str) -> bool:
        """
        Change the model being used.
        
        Args:
            model_name: Name of the model file (e.g., 'ggml-tiny.en.bin')
        
        Returns:
            True if successful, False otherwise
        """
        model_dir = os.path.dirname(self.model_path)
        new_path = os.path.join(model_dir, model_name)
        if os.path.exists(new_path):
            self.model_path = new_path
            return True
        return False
    
    def transcribe_microphone(self, duration: int = 5, sample_rate: int = 16000) -> str:
        """
        Record from microphone and transcribe.
        
        Args:
            duration: Recording duration in seconds
            sample_rate: Sample rate
        
        Returns:
            Transcribed text
        """
        import tempfile
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            # Record audio
            cmd = [
                'arecord',
                '-f', 'cd',
                '-t', 'wav',
                '-d', str(duration),
                '-r', str(sample_rate),
                temp_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Transcribe
            result = self.transcribe_file(temp_path)
            return result
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            txt_path = temp_path + '.txt'
            if os.path.exists(txt_path):
                os.unlink(txt_path)
