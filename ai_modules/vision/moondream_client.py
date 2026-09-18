"""
Moondream Vision Client - Handles image understanding
"""

import base64
import json
import requests
from typing import Dict, Any, Optional, List
from PIL import Image
import io
import time


class MoondreamClient:
    """
    Client for Moondream vision model.
    Moondream is a compact vision-language model for edge devices.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "moondream:latest"):
        self.base_url = base_url
        self.model = model
        self.last_image_description = ""
    
    def encode_image(self, image) -> str:
        """Encode image to base64, downscaling to save time"""
        if isinstance(image, str):
            with open(image, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        
        if isinstance(image, Image.Image):
            img = image
        else:
            img = Image.fromarray(image)
        
        # Downscale to max 448x448 (Moondream's native resolution)
        img.thumbnail((224, 224), Image.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=75)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def describe_image(self, image, prompt: str = "Describe what you see in this image") -> str:
        """
        Get a description of an image.
        
        Args:
            image: Image to analyze
            prompt: Question to ask about the image
        
        Returns:
            Description string
        """
        try:
            encoded = self.encode_image(image)
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": f"<image> {prompt}",
                        "images": [encoded]
                    }
                ],
                "stream": False,
                "options": {
                    "num_predict": 64,
                    "num_ctx": 2048,
                    "temperature": 0.7
                }
            }
            
            print(f"📷 Sending image to {self.model}...")
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=180
            )
            response.raise_for_status()
            
            result = response.json()
            description = result.get("message", {}).get("content", "")
            self.last_image_description = description
            print(f"✅ Moondream response: {description[:100]}...")
            return description
            
        except requests.exceptions.Timeout:
            print("⏱️ Moondream timeout")
            return "⏱️ Image analysis is taking too long. The model might be processing slowly on this device."
        except requests.exceptions.RequestException as e:
            print(f"❌ Moondream error: {e}")
            return f"Error describing image: {str(e)}"
    
    def detect_object(self, image, object_name: str) -> Dict[str, Any]:
        """
        Detect a specific object in the image.
        
        Args:
            image: Image to analyze
            object_name: Name of object to detect
        
        Returns:
            Dict with 'detected', 'position', 'confidence'
        """
        prompt = f"Where is the {object_name} in this image? Describe its location."
        description = self.describe_image(image, prompt)
        
        detected = object_name.lower() in description.lower()
        
        import re
        coords = re.findall(r'\((\d+)\s*,\s*(\d+)\)', description)
        
        result = {
            "detected": detected,
            "description": description,
            "position": None,
            "confidence": 0.7 if detected else 0.0
        }
        
        if coords:
            try:
                result["position"] = (int(coords[0][0]), int(coords[0][1]))
            except:
                pass
        
        return result
    
    def detect_objects(self, image, objects: List[str]) -> Dict[str, Any]:
        """
        Detect multiple objects in an image.
        
        Args:
            image: Image to analyze
            objects: List of object names to detect
        
        Returns:
            Dict with detection results for each object
        """
        results = {}
        for obj in objects:
            results[obj] = self.detect_object(image, obj)
        return results
    
    def analyze_scene(self, image, question: str) -> str:
        """
        Ask a specific question about an image.
        
        Args:
            image: Image to analyze
            question: Question about the image
        
        Returns:
            Answer string
        """
        return self.describe_image(image, question)
    
    # ================= FEED CAPTURE METHODS =================
    
    def analyze_from_feed_url(self, prompt: str = "Describe what you see in this image", feed_url: str = "http://localhost:5002/video_feed") -> str:
        """
        Analyze a frame from the Flask video feed URL.
        """
        try:
            from .feed_capture import capture_from_feed
            
            print("📷 Capturing from feed URL...")
            image = capture_from_feed(feed_url, timeout=10)
            if image is None:
                return "⚠️ Could not capture from video feed. Please make sure the server is running."
            
            print("📷 Analyzing frame from feed with Moondream...")
            result = self.describe_image(image, prompt)
            return result
        except Exception as e:
            return f"❌ Feed capture error: {str(e)}"
    
    def analyze_from_camera_direct(self, prompt: str = "Describe what you see in this image") -> str:
        """
        Analyze using direct camera capture as fallback.
        """
        try:
            from .feed_capture import capture_from_camera_direct
            
            print("📷 Capturing directly from camera...")
            image = capture_from_camera_direct()
            if image is None:
                return "⚠️ Could not capture image from camera. Please make sure it's connected."
            
            print("📷 Analyzing image with Moondream...")
            result = self.describe_image(image, prompt)
            return result
        except Exception as e:
            return f"❌ Camera capture error: {str(e)}"
    
    def analyze_from_feed(self, prompt: str = "Describe what you see in this image") -> str:
        """
        Analyze the current frame from the video feed using OpenCV.
        """
        try:
            from .frame_capture import FrameCapture
            
            print("📷 Capturing from frame capture...")
            frame_capture = FrameCapture()
            if not frame_capture.initialize():
                return "⚠️ Could not connect to video feed. Please make sure the camera is running."
            
            try:
                image = frame_capture.capture_as_pil()
                if image is None:
                    return "⚠️ Could not capture frame from video feed."
                
                print("📷 Analyzing frame with Moondream...")
                result = self.describe_image(image, prompt)
                return result
            finally:
                frame_capture.release()
        except Exception as e:
            return f"❌ Frame capture error: {str(e)}"
    
    # ================= CAMERA METHODS (Legacy) =================
    
    def analyze_camera(self, prompt: str = "Describe what you see in this image", camera_instance=None) -> str:
        """
        Analyze the current camera feed with Moondream.
        """
        try:
            from .camera_capture import CameraCapture
            
            if camera_instance is not None:
                camera = camera_instance
                if not camera.is_initialized:
                    camera.initialize()
            else:
                camera = CameraCapture()
                if not camera.initialize():
                    return "⚠️ Could not initialize camera. Please make sure the camera is connected."
            
            try:
                image = camera.capture_as_pil()
                if image is None:
                    return "⚠️ Could not capture image. The camera might be busy or disconnected."
                
                print("📷 Analyzing image with Moondream...")
                result = self.describe_image(image, prompt)
                return result
            except Exception as e:
                return f"❌ Error during capture: {str(e)}"
            finally:
                if camera_instance is None:
                    camera.release()
        except Exception as e:
            return f"❌ Camera error: {str(e)}"
    
    def detect_object_camera(self, object_name: str) -> dict:
        """
        Detect a specific object using the camera feed.
        """
        try:
            from .camera_capture import CameraCapture
            
            camera = CameraCapture()
            if not camera.initialize():
                return {"detected": False, "error": "Camera unavailable"}
            
            try:
                image = camera.capture_as_pil()
                if image is None:
                    return {"detected": False, "error": "Could not capture image"}
                
                return self.detect_object(image, object_name)
            finally:
                camera.release()
        except Exception as e:
            return {"detected": False, "error": str(e)}
    
    def analyze_obstacles(self) -> dict:
        """
        Analyze the camera feed for obstacles.
        """
        try:
            from .camera_capture import CameraCapture
            
            camera = CameraCapture()
            if not camera.initialize():
                return {"obstacles": [], "error": "Camera unavailable"}
            
            try:
                image = camera.capture_as_pil()
                if image is None:
                    return {"obstacles": [], "error": "Could not capture image"}
                
                prompt = "Describe any obstacles or objects that the robot should avoid. Include their approximate positions."
                description = self.describe_image(image, prompt)
                
                return {
                    "obstacles": description,
                    "has_obstacles": len(description) > 10
                }
            finally:
                camera.release()
        except Exception as e:
            return {"obstacles": [], "error": str(e)}
    
    def check_available(self) -> bool:
        """Check if Moondream is available (accepts both 'moondream' and 'moondream:latest')"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                # Match either "moondream" or "moondream:latest"
                available = any(
                    name == self.model or name.startswith(f"{self.model}:")
                    for name in model_names
                )
                print(f"📋 Available models: {model_names}")
                print(f"📋 Looking for: {self.model}")
                print(f"📋 Moondream available: {available}")
                return available
            return False
        except Exception as e:
            print(f"⚠️ Could not check Moondream availability: {e}")
            return False
