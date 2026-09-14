"""
Tool Registry - Manages all robot functions that the AI can call
"""

import json
import inspect
from typing import Dict, Any, Callable, List, Optional
from functools import wraps


class ToolRegistry:
    """
    Registry for robot tools/functions that the LLM can call.
    Each tool has a name, description, and parameter schema.
    """
    
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.functions: Dict[str, Callable] = {}
        self.vision = None
        self.camera = None
    
    def register(self, name: str, description: str, parameters: Dict[str, Any]):
        """
        Decorator to register a function as a tool.
        
        Usage:
            @tool_registry.register("move_forward", "Move robot forward", 
                                   {"speed": {"type": "integer", "description": "Speed 0-100"}})
            def move_forward(speed=50):
                robot.forward(speed)
        """
        def decorator(func: Callable):
            self.tools[name] = {
                "name": name,
                "description": description,
                "parameters": parameters
            }
            self.functions[name] = func
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Get the schema for all registered tools for Ollama"""
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": info["parameters"]
                }
            }
            for name, info in self.tools.items()
        ]
    
    def execute(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a tool by name with parameters"""
        if tool_name not in self.functions:
            return {"error": f"Tool '{tool_name}' not found"}
        
        try:
            result = self.functions[tool_name](**params)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_tool_names(self) -> List[str]:
        """Get list of all registered tool names"""
        return list(self.tools.keys())
    
    def get_tool_description(self, name: str) -> Optional[str]:
        """Get description of a specific tool"""
        if name in self.tools:
            return self.tools[name]["description"]
        return None
    
    def register_vision_tools(self):
        """Register vision-related tools for the AI agent"""
        
        # Import here to avoid circular imports
        try:
            from ..vision.moondream_client import MoondreamClient
            from ..vision.camera_capture import CameraCapture
            from ..vision.feed_capture import capture_from_feed, capture_from_camera_direct
            
            self.vision = MoondreamClient()
            self.camera = CameraCapture()
        except Exception as e:
            print(f"⚠️ Vision imports failed: {e}")
            return
        
        # ============ SEE CAMERA ============
        @self.register(
            "see_camera",
            "Take a picture with the robot's camera and describe what you see",
            {
                "prompt": {
                    "type": "string",
                    "description": "Optional specific question about the image",
                    "default": "Describe what you see in this image"
                }
            }
        )
        def see_camera(prompt="Describe what you see in this image"):
            """
            Take a photo and analyze it using multiple methods.
            Tries feed URL first, then direct camera capture.
            """
            result = "⚠️ No capture method succeeded"
            
            # Method 1: Try feed URL (most reliable if video feed is running)
            try:
                print("📷 Method 1: Capturing from feed URL...")
                result = self.vision.analyze_from_feed_url(prompt)
                
                # Check if successful (not an error message)
                if not result.startswith(("⚠️", "❌", "Error")):
                    return result
            except Exception as e:
                print(f"   Method 1 failed: {e}")
            
            # Method 2: Try direct camera capture
            try:
                print("📷 Method 2: Trying direct camera capture...")
                result = self.vision.analyze_from_camera_direct(prompt)
                
                # Check if successful
                if not result.startswith(("⚠️", "❌", "Error")):
                    return result
            except Exception as e:
                print(f"   Method 2 failed: {e}")
            
            # Method 3: Try frame capture
            try:
                print("📷 Method 3: Trying frame capture...")
                result = self.vision.analyze_from_feed(prompt)
                
                # Check if successful
                if not result.startswith(("⚠️", "❌", "Error")):
                    return result
            except Exception as e:
                print(f"   Method 3 failed: {e}")
            
            # All methods failed
            return f"⚠️ Could not capture image. Last error: {result}"
        
        # ============ DETECT OBJECT ============
        @self.register(
            "detect_object",
            "Detect a specific object using the robot's camera",
            {
                "object_name": {
                    "type": "string",
                    "description": "Name of the object to detect (e.g., 'ball', 'person', 'obstacle')"
                }
            }
        )
        def detect_object(object_name):
            """Detect a specific object"""
            try:
                # Try feed URL first
                result = self.vision.analyze_from_feed_url(f"Where is the {object_name}?")
                
                if result and not result.startswith(("⚠️", "❌", "Error")):
                    if object_name.lower() in result.lower():
                        return f"✅ Found {object_name}: {result}"
                    else:
                        return f"❌ Could not find {object_name} in the camera view"
                
                # Fallback to direct camera
                result = self.vision.analyze_from_camera_direct(f"Where is the {object_name}?")
                
                if result and not result.startswith(("⚠️", "❌", "Error")):
                    if object_name.lower() in result.lower():
                        return f"✅ Found {object_name}: {result}"
                    else:
                        return f"❌ Could not find {object_name} in the camera view"
                
                return f"❌ Could not detect {object_name}. Error: {result}"
            except Exception as e:
                return f"❌ Detection error: {str(e)}"
        
        # ============ CHECK OBSTACLES ============
        @self.register(
            "check_obstacles",
            "Check the camera for obstacles in front of the robot",
            {}
        )
        def check_obstacles():
            """Check for obstacles using camera"""
            try:
                prompt = "Describe any obstacles or objects that the robot should avoid."
                
                # Try feed URL first
                result = self.vision.analyze_from_feed_url(prompt)
                
                if result and not result.startswith(("⚠️", "❌", "Error")):
                    if "obstacle" in result.lower() or "avoid" in result.lower():
                        return f"🚧 Obstacles detected: {result}"
                    else:
                        return f"✅ No obstacles detected. {result}"
                
                # Fallback to direct camera
                result = self.vision.analyze_from_camera_direct(prompt)
                
                if result and not result.startswith(("⚠️", "❌", "Error")):
                    if "obstacle" in result.lower() or "avoid" in result.lower():
                        return f"🚧 Obstacles detected: {result}"
                    else:
                        return f"✅ No obstacles detected. {result}"
                
                return f"⚠️ Could not check obstacles. Error: {result}"
            except Exception as e:
                return f"❌ Obstacle check error: {str(e)}"
        
        # ============ NAVIGATE TO OBJECT ============
        @self.register(
            "navigate_to_object",
            "Navigate towards a detected object using camera guidance",
            {
                "object_name": {
                    "type": "string",
                    "description": "Name of the object to navigate to"
                }
            }
        )
        def navigate_to_object(object_name):
            """Navigate towards a detected object"""
            try:
                # First detect the object
                detect_result = detect_object(object_name)
                
                if "✅ Found" in detect_result:
                    # Simple navigation logic based on description
                    # Try to get more specific location
                    prompt = f"Where is the {object_name}? Is it on the left, right, or center?"
                    
                    # Try feed URL
                    result = self.vision.analyze_from_feed_url(prompt)
                    
                    if result and not result.startswith(("⚠️", "❌", "Error")):
                        if "left" in result.lower():
                            return f"🔄 {object_name} is on the left. Turning left."
                        elif "right" in result.lower():
                            return f"🔄 {object_name} is on the right. Turning right."
                        elif "center" in result.lower() or "middle" in result.lower():
                            return f"⬆️ {object_name} is ahead! Moving forward."
                        else:
                            return f"📷 {object_name} detected. Moving forward to find it."
                    
                    # Fallback to direct camera
                    result = self.vision.analyze_from_camera_direct(prompt)
                    
                    if result and not result.startswith(("⚠️", "❌", "Error")):
                        if "left" in result.lower():
                            return f"🔄 {object_name} is on the left. Turning left."
                        elif "right" in result.lower():
                            return f"🔄 {object_name} is on the right. Turning right."
                        elif "center" in result.lower() or "middle" in result.lower():
                            return f"⬆️ {object_name} is ahead! Moving forward."
                        else:
                            return f"📷 {object_name} detected. Moving forward to find it."
                    
                    return f"📷 {object_name} detected. Moving forward to find it."
                else:
                    return f"❌ Could not find {object_name} in the camera view"
            except Exception as e:
                return f"❌ Navigation error: {str(e)}"
