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
        self.camera = None  # Set by init_agent() — a CameraManager from app.py

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

    # ==========================================================
    # Vision tools
    # ==========================================================

    def _capture_image_via_shared_camera(self):
        """
        Grab a single frame using the shared CameraManager set by
        init_agent(). Returns a PIL Image or None.
        """
        if self.camera is None:
            return None
        try:
            # Preferred: CameraManager.capture_pil() (returns RGB PIL Image)
            if hasattr(self.camera, 'capture_pil'):
                return self.camera.capture_pil()
            # Fallback: CameraManager.capture_frame() (BGR np array)
            if hasattr(self.camera, 'capture_frame'):
                frame = self.camera.capture_frame()
                if frame is None:
                    return None
                import cv2
                from PIL import Image
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                return Image.fromarray(rgb)
        except Exception as e:
            print(f"⚠️ Shared camera capture failed: {e}")
        return None

    def register_vision_tools(self):
        """Register vision-related tools for the AI agent"""

        # Import here to avoid circular imports
        try:
            from ..vision.moondream_client import MoondreamClient
            self.vision = MoondreamClient()
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
            Take a photo and analyze it.

            Method 0 (preferred): use the shared CameraManager injected by
              init_agent(). This shares the camera with the MJPEG stream,
              so there is no "device busy" conflict.
            Methods 1-3 are fallbacks in case Method 0 isn't available.
            """
            # ===== Method 0: shared CameraManager =====
            try:
                img = self._capture_image_via_shared_camera()
                if img is not None:
                    print("📷 Method 0 (shared manager): capturing image...")
                    result = self.vision.describe_image(img, prompt)
                    if result and not result.startswith(("⚠️", "❌", "Error")):
                        return result
                    else:
                        print(f"   Method 0 vision returned error: {result[:100]}")
                else:
                    print("   Method 0: no shared camera available, falling back")
            except Exception as e:
                print(f"   Method 0 failed: {e}")

            # ===== Method 1: feed URL =====
            try:
                print("📷 Method 1: Capturing from feed URL...")
                result = self.vision.analyze_from_feed_url(prompt)
                if not result.startswith(("⚠️", "❌", "Error")):
                    return result
            except Exception as e:
                print(f"   Method 1 failed: {e}")

            # ===== Method 2: direct camera =====
            try:
                print("📷 Method 2: Trying direct camera capture...")
                result = self.vision.analyze_from_camera_direct(prompt)
                if not result.startswith(("⚠️", "❌", "Error")):
                    return result
            except Exception as e:
                print(f"   Method 2 failed: {e}")

            # ===== Method 3: saved frame =====
            try:
                print("📷 Method 3: Trying frame capture...")
                result = self.vision.analyze_from_feed(prompt)
                if not result.startswith(("⚠️", "❌", "Error")):
                    return result
            except Exception as e:
                print(f"   Method 3 failed: {e}")

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
                # Prefer Method 0 (shared camera) too
                img = self._capture_image_via_shared_camera()
                if img is not None:
                    result = self.vision.describe_image(img, f"Where is the {object_name}?")
                    if result and not result.startswith(("⚠️", "❌", "Error")):
                        if object_name.lower() in result.lower():
                            return f"✅ Found {object_name}: {result}"
                        else:
                            return f"❌ Could not find {object_name} in the camera view"

                # Fall back to feed URL
                result = self.vision.analyze_from_feed_url(f"Where is the {object_name}?")
                if result and not result.startswith(("⚠️", "❌", "Error")):
                    if object_name.lower() in result.lower():
                        return f"✅ Found {object_name}: {result}"
                    else:
                        return f"❌ Could not find {object_name} in the camera view"

                # Fall back to direct camera
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

                # Prefer shared camera
                img = self._capture_image_via_shared_camera()
                if img is not None:
                    result = self.vision.describe_image(img, prompt)
                    if result and not result.startswith(("⚠️", "❌", "Error")):
                        if "obstacle" in result.lower() or "avoid" in result.lower():
                            return f"🚧 Obstacles detected: {result}"
                        else:
                            return f"✅ No obstacles detected. {result}"

                # Fall back
                result = self.vision.analyze_from_feed_url(prompt)
                if result and not result.startswith(("⚠️", "❌", "Error")):
                    if "obstacle" in result.lower() or "avoid" in result.lower():
                        return f"🚧 Obstacles detected: {result}"
                    else:
                        return f"✅ No obstacles detected. {result}"

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
                detect_result = detect_object(object_name)

                if "✅ Found" in detect_result:
                    prompt = f"Where is the {object_name}? Is it on the left, right, or center?"

                    # Try shared camera first
                    img = self._capture_image_via_shared_camera()
                    if img is not None:
                        result = self.vision.describe_image(img, prompt)
                        if result and not result.startswith(("⚠️", "❌", "Error")):
                            if "left" in result.lower():
                                return f"🔄 {object_name} is on the left. Turning left."
                            elif "right" in result.lower():
                                return f"🔄 {object_name} is on the right. Turning right."
                            elif "center" in result.lower() or "middle" in result.lower():
                                return f"⬆️ {object_name} is ahead! Moving forward."
                            else:
                                return f"📷 {object_name} detected. Moving forward to find it."

                    # Fall back to feed URL
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

                    return f"📷 {object_name} detected. Moving forward to find it."
                else:
                    return f"❌ Could not find {object_name} in the camera view"
            except Exception as e:
                return f"❌ Navigation error: {str(e)}"
