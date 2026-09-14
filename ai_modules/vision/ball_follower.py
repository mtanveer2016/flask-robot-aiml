"""
Ball Follower with Ultrasonic Safety
"""

import time
import cv2
import numpy as np
from collections import deque

# Import your existing ball detection classes
from app_aiagenticrobot import ImprovedBallDetector, BallFollowerPID


class SmartBallFollower:
    """Complete ball following system with ultrasonic safety"""
    
    def __init__(self, ultrasonic_sensor=None):
        self.detector = ImprovedBallDetector()
        self.pid = BallFollowerPID()
        self.ultrasonic = ultrasonic_sensor
        
        self.state = "SEARCHING"
        self.search_angle = 0
        self.search_direction = 1
        self.lost_counter = 0
        self.following_counter = 0
        
        # Safety settings
        self.SAFE_DISTANCE = 30  # cm - start slowing down
        self.STOP_DISTANCE = 15  # cm - emergency stop
        self.EXIT_DISTANCE = 10  # cm - exit ball follow mode
        
        self.obstacle_detected = False
        self.consecutive_obstacles = 0
        self.OBSTACLE_THRESHOLD = 3  # Number of readings before action
        
    def check_ultrasonic_safety(self):
        """Check ultrasonic sensor for obstacles"""
        if self.ultrasonic is None:
            return None
        
        try:
            distance = self.ultrasonic.get_distance()
            if distance is None:
                return None
            
            # Check distance thresholds
            if distance < self.EXIT_DISTANCE:
                self.consecutive_obstacles += 1
                if self.consecutive_obstacles >= self.OBSTACLE_THRESHOLD:
                    return "EXIT"  # Too close - exit ball follow
                return "STOP"  # Emergency stop
            
            elif distance < self.STOP_DISTANCE:
                self.consecutive_obstacles += 1
                if self.consecutive_obstacles >= self.OBSTACLE_THRESHOLD:
                    return "STOP"  # Stop but don't exit
                return "SLOW"
            
            elif distance < self.SAFE_DISTANCE:
                return "SLOW"
            
            else:
                # Safe - reset counter
                self.consecutive_obstacles = 0
                return "NORMAL"
                
        except Exception as e:
            print(f"Ultrasonic error: {e}")
            return None
    
    def process_frame(self, frame):
        """Process frame with ultrasonic safety"""
        # First check ultrasonic
        safety_status = self.check_ultrasonic_safety()
        
        # Detect ball
        frame = self.detector.detect_ball(frame)
        motor_commands = (0, 0)
        
        # ========== EXIT CONDITION ==========
        if safety_status == "EXIT":
            self.state = "EXITING"
            motor_commands = (0, 0)
            cv2.putText(frame, "⚠️ TOO CLOSE! Exiting ball follow...", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(frame, "🔴 Emergency Stop", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            return frame, motor_commands, "EXIT"
        
        # ========== EMERGENCY STOP ==========
        if safety_status == "STOP":
            self.state = "STOPPED"
            motor_commands = (0, 0)
            cv2.putText(frame, "⚠️ OBSTACLE DETECTED! STOPPED", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(frame, "Waiting for obstacle to clear...", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            return frame, motor_commands, "STOP"
        
        # Reset obstacle counter if safe
        if safety_status == "NORMAL":
            self.consecutive_obstacles = 0
        
        # ========== BALL FOLLOWING LOGIC ==========
        if self.detector.ball_detected:
            self.following_counter += 1
            self.lost_counter = 0
            
            if self.following_counter > 5:
                self.state = "FOLLOWING"
                
            ball_x, ball_y = self.detector.get_smoothed_position()
            ball_radius = self.detector.get_smoothed_radius()
            
            error_x = ball_x - 320
            error_y = ball_y - 240
            
            left_speed, right_speed = self.pid.get_follow_commands(ball_x, ball_radius)
            
            # Apply speed reduction if obstacle is close
            if safety_status == "SLOW":
                left_speed = int(left_speed * 0.4)
                right_speed = int(right_speed * 0.4)
                cv2.putText(frame, "⚠️ Obstacle ahead - slowing down", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            if abs(error_y) > 100:
                if error_y < -100:
                    left_speed += 100
                    right_speed += 100
                elif error_y > 100:
                    left_speed -= 50
                    right_speed -= 50
            
            motor_commands = (left_speed, right_speed)
            
            cv2.putText(frame, f"STATE: FOLLOWING", (10, 105), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(frame, f"ERROR: {error_x:.1f}", (10, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Display ultrasonic distance if available
            if self.ultrasonic:
                dist = self.ultrasonic.get_distance()
                if dist:
                    color = (0, 255, 0) if dist > 30 else (0, 255, 255) if dist > 15 else (0, 0, 255)
                    cv2.putText(frame, f"Distance: {dist}cm", (10, 150), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
        else:
            self.following_counter = 0
            self.lost_counter += 1
            
            if self.lost_counter > 10:
                self.state = "SEARCHING"
                self.pid.reset()
            
            if self.state == "SEARCHING":
                # Search pattern - rotate to find ball
                self.search_angle += self.search_direction * 15
                
                if abs(self.search_angle) > 180:
                    self.search_direction *= -1
                
                base_speed = 300
                turn = int(self.search_angle / 2)
                
                left_speed = -base_speed + turn
                right_speed = base_speed + turn
                motor_commands = (left_speed, right_speed)
                
                cv2.putText(frame, f"SEARCHING - Rotating...", (10, 105), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(frame, f"Search Angle: {self.search_angle}", (10, 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                
            elif self.state == "FOLLOWING":
                self.state = "LOST"
                motor_commands = (0, 0)
                cv2.putText(frame, "STATE: BALL LOST - STOPPED", (10, 105), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        cv2.putText(frame, f"Follower State: {self.state}", (10, 135), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        return frame, motor_commands, "NORMAL"
