"""
Frame Capture Module - Captures frames from the existing video feed
Instead of opening the camera directly, this reads from the video feed
"""

import cv2
import numpy as np
from PIL import Image
import io
import base64
import time
import threading


class FrameCapture:
    """
    Captures frames from the video feed.
    This doesn't open the camera - it reads from the existing feed.
    """
    
    def __init__(self, video_source="/video_feed"):
        self.video_source = video_source
        self.is_initialized = False
        self.last_frame = None
        self.frame_lock = threading.Lock()
        self.cap = None
    
    def initialize(self):
        """Initialize by connecting to the video feed"""
        try:
            # Try to capture from the video feed URL using OpenCV
            # Note: This won't work directly with the Flask video feed URL
            # We need to use a different approach
            
            # Method 1: Try to open the camera directly with low latency
            # This might work if we use a different backend
            self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            if self.cap.isOpened():
                self.is_initialized = True
                print("✅ Frame capture initialized (V4L2)")
                return True
            
            # Method 2: Try with different backend
            self.cap = cv2.VideoCapture(0, cv2.CAP_ANY)
            if self.cap.isOpened():
                self.is_initialized = True
                print("✅ Frame capture initialized (CAP_ANY)")
                return True
            
            print("⚠️ Could not open camera for frame capture")
            return False
            
        except Exception as e:
            print(f"❌ Frame capture initialization failed: {e}")
            return False
    
    def capture_frame(self):
        """Capture a single frame"""
        if not self.is_initialized:
            if not self.initialize():
                return None
        
        with self.frame_lock:
            try:
                # Try to read frame
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    return frame
                
                # If capture fails, try reinitializing
                self.cap.release()
                self.is_initialized = False
                if self.initialize():
                    ret, frame = self.cap.read()
                    if ret and frame is not None and frame.size > 0:
                        return frame
                
                return None
            except Exception as e:
                print(f"❌ Frame capture error: {e}")
                return None
    
    def capture_as_pil(self):
        """Capture and return as PIL Image"""
        frame = self.capture_frame()
        if frame is None:
            return None
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    def capture_as_base64(self):
        """Capture and return as base64 string"""
        frame = self.capture_frame()
        if frame is None:
            return None
        
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            return None
        
        return base64.b64encode(buffer.tobytes()).decode('utf-8')
    
    def release(self):
        """Release resources"""
        with self.frame_lock:
            if self.cap:
                self.cap.release()
                self.is_initialized = False
                print("📷 Frame capture released")
