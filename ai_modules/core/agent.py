"""
Robot Agent - Core AI agent that orchestrates all modules
"""

import json
import time
import threading
import base64
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

from .tool_registry import ToolRegistry
from ..llm.ollama_client import OllamaClient
from ..vision.moondream_client import MoondreamClient
from ..vision.camera_capture import CameraCapture
from ..speech.whisper_client import WhisperClient
from ..speech.piper_client import PiperClient


class AgentState(Enum):
    """Possible states of the AI agent"""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    ERROR = "error"


class RobotAgent:
    """
    Main AI agent that orchestrates all components.
    Uses Ollama for reasoning, Moondream for vision,
    Whisper for speech-to-text, and Piper for text-to-speech.
    """
    
    def __init__(self, camera_instance=None):
        """
        Initialize the AI agent.
        
        Args:
            camera_instance: Optional shared camera instance
        """
        # Initialize components
        self.llm = OllamaClient()
        self.vision = MoondreamClient()
        self.stt = WhisperClient()
        self.tts = PiperClient()
        self.tools = ToolRegistry()
        
        # Use provided camera or create new one
        if camera_instance is not None:
            self.camera = camera_instance
        else:
            self.camera = CameraCapture()
        
        self.state = AgentState.IDLE
        self.robot_functions = {}
        self.context = {
            "conversation": [],
            "last_command": "",
            "last_response": "",
            "robot_status": {}
        }
        
        # Register default tools
        self._register_default_tools()
        
        # Register vision tools
        self.tools.register_vision_tools()
        
        # Thread for background processing
        self._running = False
        self._thread = None
    
    def _register_default_tools(self):
        """Register default tool definitions"""
        pass
    
    def set_robot_functions(self, functions: Dict[str, Callable]):
        """Set the robot control functions for the agent"""
        self.robot_functions = functions
        self._register_robot_tools()
    
    def _register_robot_tools(self):
        """Register robot functions as tools for the LLM"""
        pass
    
    def _safe_json_safe(self, obj):
        """
        Convert any non-JSON-serializable objects to JSON-safe formats.
        Handles bytes, tuples, and nested structures.
        """
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode('utf-8')
        elif isinstance(obj, dict):
            return {k: self._safe_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._safe_json_safe(item) for item in obj]
        elif isinstance(obj, (int, float, str, bool)) or obj is None:
            return obj
        else:
            # Convert unknown types to string
            return str(obj)
    
    def _build_response_from_tools(self, results: List[Dict[str, Any]]) -> str:
        """
        Build a human-readable response from tool execution results.
        Used when the LLM returns an empty response.
        """
        if not results:
            return "Command processed."
        
        tool_messages = []
        for r in results:
            tool_name = r.get("tool", "unknown")
            tool_result = r.get("result", {})
            
            if tool_result.get("success"):
                result_msg = tool_result.get("result", "")
                if result_msg:
                    tool_messages.append(f"{result_msg}")
                else:
                    tool_messages.append(f"Executed {tool_name}")
            else:
                error_msg = tool_result.get("error", "unknown error")
                tool_messages.append(f"Failed {tool_name}: {error_msg}")
        
        return " ".join(tool_messages) if tool_messages else "Done."
    
    def process_command(self, command: str, image: Optional[Any] = None) -> Dict[str, Any]:
        """
        Process a user command through the AI pipeline.
        
        Args:
            command: User's text command
            image: Optional image for vision understanding
        
        Returns:
            Dict with response and actions
        """
        self.state = AgentState.THINKING
        
        try:
            # Get system prompt
            system_prompt = self._build_system_prompt()
            
            # If image provided, include vision context
            vision_context = ""
            if image:
                try:
                    from PIL import Image
                    import io
                    
                    if isinstance(image, str):
                        image_bytes = base64.b64decode(image)
                        image = Image.open(io.BytesIO(image_bytes))
                    
                    vision_context = self.vision.describe_image(image, 
                        "Describe the scene and identify any objects or obstacles.")
                except Exception as e:
                    print(f"Vision processing error: {e}")
                    vision_context = "Could not process image."
            
            # Build the full prompt
            full_prompt = command
            if vision_context:
                full_prompt = f"Vision context: {vision_context}\n\nUser command: {command}"
            
            # Get tools schema
            tools = self.tools.get_tools_schema()
            
            # Get response from LLM
            response = self.llm.chat(
                message=full_prompt,
                tools=tools if tools else None,
                system_prompt=system_prompt
            )
            
            # Check for tool calls
            tool_calls = response.get("tool_calls", [])
            results = []
            
            for tool_call in tool_calls:
                self.state = AgentState.EXECUTING
                tool_name = tool_call.get("function", {}).get("name")
                arguments = tool_call.get("function", {}).get("arguments", {})
                
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except:
                        arguments = {}
                
                result = self.tools.execute(tool_name, arguments)
                results.append({
                    "tool": tool_name,
                    "params": arguments,
                    "result": result
                })
            
            # ============ FIX: Ensure we always have a text response ============
            response_text = response.get("content", "").strip()
            
            if not response_text:
                # LLM returned empty - build response from tool results
                if results:
                    response_text = self._build_response_from_tools(results)
                else:
                    response_text = f"I understood '{command}' but didn't take any action."
                
                print(f"⚠️ LLM returned empty, using fallback: {response_text[:100]}")
            
            # Update context
            self.context["last_command"] = command
            self.context["last_response"] = response_text
            self.context["conversation"].append({
                "user": command,
                "assistant": response_text,
                "timestamp": time.time()
            })
            
            self.state = AgentState.IDLE
            
            # Build response dict
            result_dict = {
                "success": True,
                "response": response_text,
                "tool_calls": results,
                "state": self.state.value
            }
            
            return self._safe_json_safe(result_dict)
            
        except Exception as e:
            self.state = AgentState.ERROR
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "state": self.state.value
            }
    
    def process_voice(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Process voice input and respond with speech.
        
        Args:
            audio_data: Audio bytes (WAV format)
        
        Returns:
            Dict with transcription, response, and audio (base64 encoded)
        """
        self.state = AgentState.LISTENING
        
        try:
            # Transcribe audio
            print("🎤 Transcribing audio with Whisper...")
            transcription = self.stt.transcribe_bytes(audio_data)
            
            if not transcription or transcription.startswith("Error"):
                self.state = AgentState.ERROR
                return {
                    "success": False,
                    "error": transcription or "Transcription failed",
                    "state": self.state.value
                }
            
            print(f"✅ Transcribed: {transcription}")
            
            # Process command
            result = self.process_command(transcription)
            
            if result.get("success"):
                # Get response text - ensure it's not empty
                response_text = result.get("response", "").strip()
                if not response_text:
                    response_text = "Command executed."
                
                # Synthesize speech response
                self.state = AgentState.SPEAKING
                
                print(f"🔊 Synthesizing speech: {response_text[:100]}...")
                audio_response = self.tts.synthesize(response_text)
                
                # Encode bytes to base64 for JSON safety
                audio_base64 = None
                if audio_response and isinstance(audio_response, bytes):
                    try:
                        audio_base64 = base64.b64encode(audio_response).decode('utf-8')
                        print(f"✅ Audio encoded to base64: {len(audio_base64)} chars")
                    except Exception as e:
                        print(f"❌ Audio encoding error: {e}")
                
                self.state = AgentState.IDLE
                
                return {
                    "success": True,
                    "transcription": transcription,
                    "response": response_text,
                    "audio": audio_base64,
                    "state": self.state.value
                }
            else:
                self.state = AgentState.ERROR
                return {
                    "success": False,
                    "transcription": transcription,
                    "error": result.get("error", "Processing failed"),
                    "state": self.state.value
                }
                
        except Exception as e:
            self.state = AgentState.ERROR
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "state": self.state.value
            }
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM"""
        return """You are an AI assistant for a robot car. You can see through the robot's camera and control it.

**Your capabilities:**
1. **See**: Use `see_camera` to look through the robot's camera and describe what you see
2. **Detect**: Use `detect_object` to find specific objects (ball, person, obstacle, etc.)
3. **Navigate**: Use `navigate_to_object` to move towards a detected object
4. **Check**: Use `check_obstacles` to see if there are obstacles ahead
5. **Move**: Control the robot with `move_forward`, `turn_left`, `turn_right`, `stop`
6. **Follow**: Use `follow_ball` to track and follow a ball
7. **Patrol**: Use `start_patrol` to patrol an area

**IMPORTANT: Always respond with a short text message describing what you did.**
For example:
- If you called `move_forward`, respond with: "Moving the robot forward."
- If you called `stop_robot`, respond with: "Robot stopped."
- If you called `beep_buzzer`, respond with: "Buzzer beeped."
- If you called `set_led`, respond with: "LED set to red."

**Important Rules:**
1. Always check for obstacles before moving
2. When asked "what do you see?", use `see_camera` to look
3. When asked to find something, use `detect_object`
4. Always be safe - stop if you detect an obstacle close by
5. **ALWAYS provide a text response** - never return an empty message

**Example responses:**
- User: "What do you see?" -> Use `see_camera`, then respond with the description
- User: "Find the ball" -> Use `detect_object` with "ball", then respond with the result
- User: "Go to the ball" -> Use `navigate_to_object` with "ball", then respond with the action
- User: "Is it safe to move?" -> Use `check_obstacles`, then respond with the result
- User: "Stop" -> Use `stop_robot`, then respond with "Robot stopped."
"""
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the agent"""
        return {
            "state": self.state.value,
            "llm_available": self.llm.check_available(),
            "vision_available": True,
            "stt_available": self.stt.check_available(),
            "tts_available": self.tts.check_available(),
            "tools": self.tools.get_tool_names(),
            "last_command": self.context["last_command"],
            "last_response": self.context["last_response"],
            "conversation_length": len(self.context["conversation"])
        }
    
    def clear_history(self):
        """Clear conversation history"""
        self.llm.clear_history()
        self.context["conversation"] = []
