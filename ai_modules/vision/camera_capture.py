"""
Camera Capture Module - Captures from the video feed
"""

import cv2
import time
import numpy as np
from PIL import Image
import io
import base64
import threading


class CameraCapture:
    """Handles camera capture by reading from the video feed"""
    
    def __init__(self):
        self.cap = None
        self.is_initialized = False
        self.frame_width = 640
        self.frame_height = 480
        self.lock = threading.Lock()
    
    def initialize(self):
        """Initialize the camera using OpenCV"""
        try:
            # Try different camera indices
            for idx in [0, 1, -1]:
                try:
                    self.cap = cv2.VideoCapture(idx)
                    if self.cap.isOpened():
                        break
                except:
                    continue
            
            if not self.cap or not self.cap.isOpened():
                print("⚠️ Could not open camera with OpenCV")
                return False
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            
            # Test capture
            ret, frame = self.cap.read()
            if not ret or frame is None:
                print("⚠️ Test capture failed")
                return False
                
            self.is_initialized = True
            print("✅ Camera initialized for AI agent (OpenCV)")
            return True
        except Exception as e:
            print(f"❌ Camera initialization failed: {e}")
            return False
    
    def capture_frame(self):
        """Capture a single frame from the camera"""
        with self.lock:
            if not self.is_initialized:
                if not self.initialize():
                    return None
            
            try:
                # Try to read frame
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    return frame
                
                # If capture fails, try reinitializing
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
        """Release camera resources"""
        with self.lock:
            if self.cap and self.is_initialized:
                self.cap.release()
                self.is_initialized = False
                print("📷 Camera released")
