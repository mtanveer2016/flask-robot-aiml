"""
Feed Capture - Captures from the Flask video feed URL
"""

import cv2
import numpy as np
import requests
from PIL import Image
import io
import base64
import time


def capture_from_feed(feed_url="http://localhost:5002/video_feed", timeout=10):
    """
    Capture a frame from the Flask video feed.
    
    Args:
        feed_url: URL of the video feed
        timeout: Timeout in seconds
    
    Returns:
        PIL Image or None
    """
    try:
        # Open connection to video feed
        stream = requests.get(feed_url, stream=True, timeout=timeout)
        
        # Read the first frame
        bytes_data = b''
        start_time = time.time()
        
        for chunk in stream.iter_content(chunk_size=8192):
            bytes_data += chunk
            a = bytes_data.find(b'\xff\xd8')
            b = bytes_data.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = bytes_data[a:b+2]
                # Convert to PIL Image
                image = Image.open(io.BytesIO(jpg))
                return image
            
            # Timeout protection
            if time.time() - start_time > timeout:
                break
        
        print("⚠️ Could not find a complete JPEG frame in the feed")
        return None
    except requests.exceptions.Timeout:
        print("❌ Feed capture timeout")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to video feed")
        return None
    except Exception as e:
        print(f"❌ Feed capture error: {e}")
        return None


def capture_from_camera_direct():
    """
    Fallback: Capture directly from camera using OpenCV.
    This tries to open the camera with different backends.
    """
    try:
        # Try different camera indices and backends
        for idx in [0, 1, 2]:
            for backend in [cv2.CAP_V4L2, cv2.CAP_ANY, cv2.CAP_GSTREAMER]:
                try:
                    cap = cv2.VideoCapture(idx, backend)
                    if cap.isOpened():
                        # Try to read a frame
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            cap.release()
                            # Convert to PIL
                            return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        cap.release()
                except:
                    continue
        
        return None
    except Exception as e:
        print(f"❌ Direct camera capture error: {e}")
        return None
