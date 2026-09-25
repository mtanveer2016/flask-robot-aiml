# ================= IMPORTS =================
from flask import Flask, render_template, jsonify, request, Response
from motor import Ordinary_Car
from buzzer import Buzzer
from led import Led
from ai_routes import ai_bp, init_agent, register_robot_tools
from ai_modules import RobotAgent
import threading
import time
import cv2
import numpy as np
import math
import json
from collections import deque
import heapq
from picamera2 import Picamera2
import random
import ultrasonic
import sys
import locale
from enum import Enum
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Gauge
from adc import ADC
import signal


# ================= FLASK APP =================
try:
    locale.setlocale(locale.LC_ALL, 'en_GB.UTF-8')
except locale.Error:
    pass

app = Flask(__name__)
metrics = PrometheusMetrics(app)


# ================= CAMERA MANAGER =================
class CameraManager:
    """
    Single shared camera instance with thread-safe access.
    Both the MJPEG stream (generate_frames) and the AI vision tool
    (see_camera -> moondream_client) use this same instance, so the
    camera is never opened twice and 'Device or resource busy' errors
    are avoided.
    """

    def __init__(self, size=(640, 480), framerate=30):
        self._lock = threading.Lock()
        self._picam2 = None
        self._available = False
        self._size = size

        try:
            self._picam2 = Picamera2()
            config = self._picam2.create_video_configuration(
                main={"size": size, "format": "RGB888"},
                controls={"FrameRate": framerate}
            )
            self._picam2.configure(config)
            self._picam2.start()
            time.sleep(1)  # let the sensor settle
            self._available = True
            print(f"✅ CameraManager: camera initialized at {size}")
        except Exception as e:
            self._available = False
            print(f"❌ CameraManager: camera init failed: {e}")

    @property
    def available(self):
        return self._available

    def capture_frame(self, timeout=2.0):
        """
        Thread-safe single-frame capture.
        Returns a BGR numpy array (OpenCV-compatible) or None on failure.
        """
        if not self._available:
            return None

        acquired = self._lock.acquire(timeout=timeout)
        if not acquired:
            print("⚠️ CameraManager: lock timeout — another capture in progress")
            return None
        try:
            frame = self._picam2.capture_array()
            # picamera2 with RGB888 returns RGB; convert to BGR for OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return frame
        except Exception as e:
            print(f"❌ CameraManager capture error: {e}")
            return None
        finally:
            self._lock.release()

    def capture_pil(self, timeout=2.0):
        """
        Same as capture_frame, but returns a PIL Image (RGB).
        Used by the Moondream vision client which expects PIL/np RGB.
        """
        frame_bgr = self.capture_frame(timeout=timeout)
        if frame_bgr is None:
            return None
        from PIL import Image
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def release(self):
        """Called on shutdown to release the camera cleanly."""
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
                print("✅ CameraManager: camera released")
            except Exception as e:
                print(f"⚠️ CameraManager release error: {e}")


# ================= Battery Monitoring =================

battery_voltage_gauge = Gauge('robot_battery_voltage',
                              'Current battery voltage in volts')
battery_percent_gauge = Gauge('robot_battery_percent',
                              'Current battery percentage remaining')


def get_battery_reading():
    """Read actual battery voltage from ADC"""
    try:
        adc = ADC()
        pcb_version = adc.pcb_version
        voltage = adc.read_adc(2) * (3 if pcb_version == 1 else 2)

        min_voltage = 6.0
        max_voltage = 8.4

        if voltage >= max_voltage:
            percentage = 100.0
        elif voltage <= min_voltage:
            percentage = 0.0
        else:
            percentage = ((voltage - min_voltage) / (max_voltage - min_voltage)) * 100

        return round(voltage, 2), round(percentage, 1)
    except Exception as e:
        print(f"Battery read error: {e}")
        return 7.4, 50.0


def update_battery_metrics():
    """Background thread to update battery metrics"""
    while True:
        voltage, percentage = get_battery_reading()
        battery_voltage_gauge.set(voltage)
        battery_percent_gauge.set(percentage)
        print(f"Battery updated: {voltage}V ({percentage}%)")
        time.sleep(30)


def update_battery():
    """Simulate battery updates (replace with actual ADC reading)"""
    voltage = 7.58
    percentage = 65.8
    battery_voltage_gauge.set(voltage)
    battery_percent_gauge.set(percentage)
    print(f"Battery: {voltage}V ({percentage}%)")
    threading.Timer(30, update_battery).start()


update_battery()


@app.route('/health')
def health():
    return "Robot OK"


@app.route('/metrics')
def metrics_endpoint():
    return metrics.expose_metrics()


battery_thread = threading.Thread(target=update_battery_metrics, daemon=True)
battery_thread.start()


# ================= ROBOT CONTROLLER CLASS =================
class RobotController:
    """Wrapper for robot control functions for the AI agent"""

    def __init__(self, pwm, buzzer, led):
        self.pwm = pwm
        self.buzzer = buzzer
        self.led = led
        self.current_mode = "manual"

    def forward(self, speed=50):
        speed_scaled = int((speed / 100) * 2000)
        self.pwm.set_motor_model(speed_scaled, speed_scaled, speed_scaled, speed_scaled)

    def backward(self, speed=50):
        speed_scaled = int((speed / 100) * 2000)
        self.pwm.set_motor_model(-speed_scaled, -speed_scaled, -speed_scaled, -speed_scaled)

    def turn_left(self, angle=45):
        self.pwm.set_motor_model(-500, -500, 500, 500)
        time.sleep(angle / 90)
        self.stop()

    def turn_right(self, angle=45):
        self.pwm.set_motor_model(500, 500, -500, -500)
        time.sleep(angle / 90)
        self.stop()

    def stop(self):
        self.pwm.set_motor_model(0, 0, 0, 0)

    def beep(self, duration=0.2):
        self.buzzer.set_state(True)
        time.sleep(duration)
        self.buzzer.set_state(False)

    def set_led(self, color):
        colors = {
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0),
            'white': (255, 255, 255),
            'off': (0, 0, 0)
        }
        if color in colors:
            r, g, b = colors[color]
            self.led.ledIndex(0xFF, r, g, b)

    def start_ball_follow(self):
        global current_mode
        current_mode = "ball_follow"

    def start_patrol(self, shape="square"):
        global current_mode, patrol_system
        patrol_system.generate_patrol_path(shape)
        patrol_system.active = True
        current_mode = "patrol"


# ================= HARDWARE INITIALIZATION =================
print("Initializing hardware...")
PWM = Ordinary_Car()
buzzer = Buzzer()
led = Led()
print("✅ Hardware initialized")


# ================= ULTRASONIC SENSOR WRAPPER =================
class UltrasonicSensor:
    """Wrapper for the ultrasonic sensor with error handling"""

    def __init__(self):
        try:
            self.sensor = ultrasonic.Ultrasonic()
            self.available = True
            print("✅ Ultrasonic sensor initialized")
        except Exception as e:
            print(f"❌ Ultrasonic sensor error: {e}")
            self.available = False

    def get_distance(self):
        if not self.available:
            return None
        try:
            distance = self.sensor.get_distance()
            if distance and 2 <= distance <= 400:
                return round(distance, 1)
            return None
        except Exception as e:
            print(f"Ultrasonic read error: {e}")
            return None


ultrasonic_sensor = UltrasonicSensor()


# ================= CAMERA SETUP (uses CameraManager) =================
camera_manager = CameraManager(size=(640, 480))
camera_available = camera_manager.available


# ================= AI AGENT INITIALIZATION =================
print("Initializing AI Agent...")

robot_controller = RobotController(PWM, buzzer, led)
# Pass the SHARED camera manager so the AI vision tool uses the same
# camera instance as the MJPEG stream. This prevents "device busy".
ai_agent = init_agent(camera_instance=camera_manager)
register_robot_tools(ai_agent, robot_controller)
app.register_blueprint(ai_bp)

print(f"✅ AI Agent initialized")
print(f"   - LLM: {ai_agent.llm.model}")
print(f"   - Tools available: {ai_agent.tools.get_tool_names()}")


# ================= GLOBAL STATE =================
current_speed = 1000
is_moving = False
current_mode = "manual"
autonomous_active = False
current_mission = None


# ================= BALL FOLLOWING SYSTEM =================
class ImprovedBallDetector:
    """Enhanced ball detector with better tracking and prediction"""

    def __init__(self):
        self.lower_orange = np.array([5, 100, 100])
        self.upper_orange = np.array([15, 255, 255])
        self.lower_orange2 = np.array([0, 120, 120])
        self.upper_orange2 = np.array([20, 255, 255])

        self.ball_position = (320, 240)
        self.ball_detected = False
        self.ball_radius = 0
        self.frame_center = (320, 240)

        self.position_history = deque(maxlen=5)
        self.radius_history = deque(maxlen=5)

        self.predicted_x = 320
        self.last_seen_time = 0
        self.ball_velocity_x = 0

        self.frame_width = 640
        self.frame_height = 480
        self.confidence = 0

    def detect_ball(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        mask1 = cv2.inRange(hsv, self.lower_orange, self.upper_orange)
        mask2 = cv2.inRange(hsv, self.lower_orange2, self.upper_orange2)
        mask = cv2.bitwise_or(mask1, mask2)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=2)
        mask = cv2.dilate(mask, kernel, iterations=3)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        self.ball_detected = False
        best_contour = None
        best_area = 0

        if contours:
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 100:
                    continue
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                if circularity > 0.5 and area > best_area:
                    best_area = area
                    best_contour = contour

            if best_contour is not None:
                ((x, y), radius) = cv2.minEnclosingCircle(best_contour)
                self.ball_position = (int(x), int(y))
                self.ball_radius = int(radius)
                self.ball_detected = True
                self.confidence = min(1.0, best_area / 5000)

                self.position_history.append(self.ball_position)
                self.radius_history.append(self.ball_radius)

                if len(self.position_history) >= 2:
                    prev_x = self.position_history[-2][0]
                    curr_x = self.ball_position[0]
                    self.ball_velocity_x = curr_x - prev_x

                self.last_seen_time = time.time()

                cv2.circle(frame, self.ball_position, self.ball_radius, (0, 255, 0), 2)
                cv2.circle(frame, self.ball_position, 5, (0, 0, 255), -1)

                cv2.rectangle(frame, (10, 10), (10 + int(self.confidence * 100), 30), (0, 255, 0), -1)
                cv2.putText(frame, f"Confidence: {int(self.confidence * 100)}%", (10, 45),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        else:
            self.confidence = max(0, self.confidence - 0.05)
            if time.time() - self.last_seen_time < 1.0:
                self.predicted_x += self.ball_velocity_x * 0.5
                self.ball_position = (int(self.predicted_x), self.ball_position[1])
                cv2.circle(frame, self.ball_position, 20, (0, 255, 255), 2)
                cv2.putText(frame, "Predicting...", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        cv2.putText(frame, f"Ball Pos: ({self.ball_position[0]}, {self.ball_position[1]})", (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, f"Ball Radius: {self.ball_radius}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame

    def get_smoothed_position(self):
        if len(self.position_history) > 0:
            avg_x = sum(p[0] for p in self.position_history) / len(self.position_history)
            avg_y = sum(p[1] for p in self.position_history) / len(self.position_history)
            return (int(avg_x), int(avg_y))
        return self.ball_position

    def get_smoothed_radius(self):
        if len(self.radius_history) > 0:
            return sum(self.radius_history) / len(self.radius_history)
        return self.ball_radius


class BallFollowerPID:
    """PID controller for smooth ball following"""

    def __init__(self):
        self.kp = 0.8
        self.ki = 0.02
        self.kd = 0.1
        self.kp_speed = 0.5
        self.ki_speed = 0.01
        self.kd_speed = 0.05
        self.prev_error = 0
        self.integral = 0
        self.prev_speed_error = 0
        self.speed_integral = 0
        self.max_output = 1000
        self.min_output = -1000
        self.max_speed = 800
        self.min_speed = 200
        self.target_x = 320
        self.target_radius = 60

    def compute_turn(self, ball_x, dt=0.1):
        error = self.target_x - ball_x
        error = max(-320, min(320, error))
        self.integral += error * dt
        self.integral = max(-500, min(500, self.integral))
        derivative = (error - self.prev_error) / dt if dt > 0 else 0
        output = (self.kp * error) + (self.ki * self.integral) + (self.kd * derivative)
        self.prev_error = error
        output = max(self.min_output, min(self.max_output, output))
        return output

    def compute_speed(self, ball_radius, dt=0.1):
        error = self.target_radius - ball_radius
        if ball_radius > 0:
            self.speed_integral += error * dt
            self.speed_integral = max(-100, min(100, self.speed_integral))
            derivative = (error - self.prev_speed_error) / dt if dt > 0 else 0
            base_speed = 500
            adjustment = (self.kp_speed * error) + (self.ki_speed * self.speed_integral) + (self.kd_speed * derivative)
            speed = base_speed + adjustment
            self.prev_speed_error = error
        else:
            speed = 200
        speed = max(self.min_speed, min(self.max_speed, speed))
        return int(speed)

    def get_follow_commands(self, ball_x, ball_radius):
        dt = 0.033
        turn = self.compute_turn(ball_x, dt)
        forward_speed = self.compute_speed(ball_radius, dt)
        turn_scaled = turn * (forward_speed / 800)
        left_speed = forward_speed - turn_scaled
        right_speed = forward_speed + turn_scaled
        left_speed = max(-1000, min(1000, left_speed))
        right_speed = max(-1000, min(1000, right_speed))
        return int(left_speed), int(right_speed)

    def reset(self):
        self.prev_error = 0
        self.integral = 0
        self.prev_speed_error = 0
        self.speed_integral = 0


class SmartBallFollower:
    """Complete ball following system with search patterns"""

    def __init__(self):
        self.detector = ImprovedBallDetector()
        self.pid = BallFollowerPID()
        self.state = "SEARCHING"
        self.search_angle = 0
        self.search_direction = 1
        self.lost_counter = 0
        self.following_counter = 0

    def process_frame(self, frame):
        frame = self.detector.detect_ball(frame)
        motor_commands = (0, 0)

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
        else:
            self.following_counter = 0
            self.lost_counter += 1

            if self.lost_counter > 10:
                self.state = "SEARCHING"
                self.pid.reset()

            if self.state == "SEARCHING":
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

        return frame, motor_commands


ball_follower = SmartBallFollower()


# ================= OBSTACLE DETECTOR =================
class ObstacleDetector:
    """Detects obstacles using REAL ultrasonic sensor"""

    def __init__(self):
        self.front_distance = 100
        self.left_distance = 100
        self.right_distance = 100
        self.obstacle_detected = False
        self.obstacle_side = None
        self.safe_distance = 30
        self.danger_distance = 20

    def update_distances(self):
        distance = ultrasonic_sensor.get_distance()
        if distance is not None:
            self.front_distance = distance
            if distance < self.safe_distance:
                self.obstacle_detected = True
                self.obstacle_side = 'front'
            else:
                self.obstacle_detected = False
                self.obstacle_side = None
        else:
            self.front_distance = 100
            self.obstacle_detected = False
            self.obstacle_side = None

    def get_obstacle_status(self):
        return {
            'detected': self.obstacle_detected,
            'side': self.obstacle_side,
            'front_distance': self.front_distance,
            'left_distance': self.left_distance,
            'right_distance': self.right_distance
        }


# ============ LED DANCE SYSTEM =================
class DancePattern(Enum):
    RAINBOW = "rainbow"
    STROBE = "strobe"
    BREATHING = "breathing"
    RANDOM = "random"
    CHASE = "chase"
    HEARTBEAT = "heartbeat"
    DISCO = "disco"


class LEDDanceController:
    """Controls LED dance patterns with optional music sync"""

    def __init__(self, led_instance):
        self.led = led_instance
        self.is_dancing = False
        self.dance_thread = None
        self.current_pattern = DancePattern.RAINBOW
        self.bpm = 120
        self.brightness = 255
        self.colors = [
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
            (255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 255, 255)
        ]
        self.current_color_index = 0

    def start_dance(self, pattern="rainbow", bpm=120, duration=None):
        if self.is_dancing:
            self.stop_dance()
        self.current_pattern = DancePattern(pattern.lower())
        self.bpm = bpm
        self.is_dancing = True
        self.dance_thread = threading.Thread(target=self._dance_loop, args=(duration,))
        self.dance_thread.daemon = True
        self.dance_thread.start()
        return True

    def stop_dance(self):
        self.is_dancing = False
        if self.dance_thread:
            self.dance_thread.join(timeout=0.5)
        self.led.ledIndex(0xFF, 0, 0, 0)

    def _dance_loop(self, duration=None):
        start_time = time.time()
        while self.is_dancing:
            if duration and (time.time() - start_time) > duration:
                break
            delay = 60.0 / self.bpm
            if self.current_pattern == DancePattern.RAINBOW:
                self._rainbow_pattern()
            elif self.current_pattern == DancePattern.STROBE:
                self._strobe_pattern()
            elif self.current_pattern == DancePattern.BREATHING:
                self._breathing_pattern()
            elif self.current_pattern == DancePattern.RANDOM:
                self._random_pattern()
            elif self.current_pattern == DancePattern.CHASE:
                self._chase_pattern()
            elif self.current_pattern == DancePattern.HEARTBEAT:
                self._heartbeat_pattern()
            elif self.current_pattern == DancePattern.DISCO:
                self._disco_pattern()
            time.sleep(delay)
        self.is_dancing = False

    def _rainbow_pattern(self):
        for i, color in enumerate(self.colors):
            if not self.is_dancing:
                break
            bf = self.brightness / 255.0
            self.led.ledIndex(0xFF, int(color[0] * bf), int(color[1] * bf), int(color[2] * bf))
            time.sleep(0.05)

    def _strobe_pattern(self):
        for _ in range(2):
            if not self.is_dancing:
                break
            self.led.ledIndex(0xFF, 255, 255, 255)
            time.sleep(0.03)
            self.led.ledIndex(0xFF, 0, 0, 0)
            time.sleep(0.03)

    def _breathing_pattern(self):
        steps = 20
        for i in range(steps):
            if not self.is_dancing:
                break
            intensity = int((i / steps) * self.brightness)
            self.led.ledIndex(0xFF, intensity, intensity, intensity)
            time.sleep(0.02)
        for i in range(steps):
            if not self.is_dancing:
                break
            intensity = int(((steps - i) / steps) * self.brightness)
            self.led.ledIndex(0xFF, intensity, intensity, intensity)
            time.sleep(0.02)

    def _random_pattern(self):
        c = random.choice(self.colors)
        bf = self.brightness / 255.0
        self.led.ledIndex(0xFF, int(c[0] * bf), int(c[1] * bf), int(c[2] * bf))

    def _chase_pattern(self):
        self.current_color_index = (self.current_color_index + 1) % len(self.colors)
        c = self.colors[self.current_color_index]
        bf = self.brightness / 255.0
        self.led.ledIndex(0xFF, int(c[0] * bf), int(c[1] * bf), int(c[2] * bf))

    def _heartbeat_pattern(self):
        self.led.ledIndex(0xFF, 255, 0, 0)
        time.sleep(0.1)
        self.led.ledIndex(0xFF, 50, 0, 0)
        time.sleep(0.1)
        self.led.ledIndex(0xFF, 255, 0, 0)
        time.sleep(0.1)
        self.led.ledIndex(0xFF, 0, 0, 0)

    def _disco_pattern(self):
        c = random.choice(self.colors)
        bf = self.brightness / 255.0
        self.led.ledIndex(0xFF, int(c[0] * bf), int(c[1] * bf), int(c[2] * bf))
        if random.random() < 0.3:
            time.sleep(0.02)
            self.led.ledIndex(0xFF, 255, 255, 255)

    def set_bpm(self, bpm):
        self.bpm = max(40, min(200, bpm))

    def set_brightness(self, brightness):
        self.brightness = max(0, min(255, brightness))


led_dance_controller = LEDDanceController(led)


# ================= LED DANCE ROUTES =================
@app.route("/led_dance")
@app.route("/led-dance")
def led_dance_page():
    return render_template("led_dance.html")


@app.route("/api/led/dance/start", methods=["POST"])
def start_led_dance():
    data = request.json
    pattern = data.get("pattern", "rainbow")
    bpm = data.get("bpm", 120)
    duration = data.get("duration", None)
    valid_patterns = [p.value for p in DancePattern]
    if pattern not in valid_patterns:
        return jsonify({"success": False, "error": f"Invalid pattern. Choose from: {valid_patterns}"})
    success = led_dance_controller.start_dance(pattern, bpm, duration)
    return jsonify({"success": success, "pattern": pattern, "bpm": bpm, "duration": duration})


@app.route("/api/led/dance/stop", methods=["POST"])
def stop_led_dance():
    led_dance_controller.stop_dance()
    return jsonify({"success": True})


@app.route("/api/led/dance/status", methods=["GET"])
def get_led_dance_status():
    return jsonify({
        "is_dancing": led_dance_controller.is_dancing,
        "current_pattern": led_dance_controller.current_pattern.value if led_dance_controller.current_pattern else None,
        "bpm": led_dance_controller.bpm,
        "brightness": led_dance_controller.brightness
    })


@app.route("/api/led/dance/patterns", methods=["GET"])
def get_dance_patterns():
    patterns = [{"id": p.value, "name": p.value.capitalize()} for p in DancePattern]
    return jsonify({"patterns": patterns})


@app.route("/api/led/dance/bpm/<int:bpm>", methods=["POST"])
def set_dance_bpm(bpm):
    bpm = max(40, min(200, bpm))
    led_dance_controller.set_bpm(bpm)
    return jsonify({"success": True, "bpm": led_dance_controller.bpm})


@app.route("/api/led/dance/brightness/<int:brightness>", methods=["POST"])
def set_dance_brightness(brightness):
    brightness = max(0, min(255, brightness))
    led_dance_controller.set_brightness(brightness)
    return jsonify({"success": True, "brightness": led_dance_controller.brightness})


@app.route("/api/led/dance/sync-to-beats", methods=["POST"])
def sync_to_beats():
    data = request.json
    beat_detected = data.get("beat", False)
    if beat_detected and led_dance_controller.is_dancing:
        original_color = led_dance_controller.current_pattern
        led.ledIndex(0xFF, 255, 255, 255)
        threading.Timer(0.05, lambda: led_dance_controller.start_dance(
            original_color.value if original_color else "rainbow",
            led_dance_controller.bpm)).start()
    return jsonify({"success": True})


# ================= OBSTACLE AVOIDANCE =================
class ObstacleAvoidance:
    def __init__(self):
        self.detector = ObstacleDetector()
        self.state = "NORMAL"
        self.avoid_direction = None
        self.avoid_start_time = 0
        self.avoid_duration = 1.5
        self.turn_speed = 400

    def get_avoidance_commands(self):
        self.detector.update_distances()
        if not self.detector.obstacle_detected:
            self.state = "NORMAL"
            return None
        front_dist = self.detector.front_distance
        if front_dist < self.detector.danger_distance:
            self.state = "AVOIDING"
            return (0, 0)
        elif front_dist < self.detector.safe_distance:
            self.state = "TURNING"
            return (-self.turn_speed, self.turn_speed)
        return None

    def get_visualization_info(self):
        return {'state': self.state, 'obstacle': self.detector.get_obstacle_status()}


# ================= PATROL SYSTEM =================
class PatrolMission:
    def __init__(self):
        self.patrol_path = []
        self.current_segment = 0
        self.active = False
        self.patrol_state = "MOVING"
        self.obstacle_avoidance = ObstacleAvoidance()
        self.last_position = (0, 0)
        self.stuck_counter = 0
        self.patrol_speed = 600

    def generate_patrol_path(self, shape="square"):
        if shape == "square":
            self.patrol_path = [(100, 0), (100, 100), (0, 100), (0, 0)]
        elif shape == "rectangle":
            self.patrol_path = [(150, 0), (150, 80), (0, 80), (0, 0)]
        elif shape == "zigzag":
            self.patrol_path = [(100, 0), (100, 50), (0, 100), (0, 150), (100, 200)]
        else:
            self.patrol_path = [(50, 0), (35, 35), (0, 50), (-35, 35),
                                (-50, 0), (-35, -35), (0, -50), (35, -35)]
        self.current_segment = 0

    def get_patrol_commands(self, current_x, current_y, current_angle):
        avoidance_cmd = self.obstacle_avoidance.get_avoidance_commands()
        if avoidance_cmd is not None:
            self.patrol_state = "AVOIDING"
            return avoidance_cmd
        self.patrol_state = "MOVING"
        if not self.patrol_path:
            return (0, 0)
        target_x, target_y = self.patrol_path[self.current_segment]
        dx = target_x - current_x
        dy = target_y - current_y
        distance = math.sqrt(dx * dx + dy * dy)
        if distance < 15:
            self.current_segment = (self.current_segment + 1) % len(self.patrol_path)
            return (0, 0)
        target_angle = math.degrees(math.atan2(dy, dx))
        angle_error = target_angle - current_angle
        while angle_error > 180:
            angle_error -= 360
        while angle_error < -180:
            angle_error += 360
        base_speed = 400 if distance < 40 else self.patrol_speed
        turn_gain = 4
        turn = int(angle_error * turn_gain)
        turn = max(-400, min(400, turn))
        left_speed = base_speed - turn
        right_speed = base_speed + turn
        return (left_speed, right_speed)


# ================= WAYPOINT NAVIGATION =================
class Waypoint:
    def __init__(self, x, y, action="navigate", description="", duration=0):
        self.x = x
        self.y = y
        self.action = action
        self.description = description
        self.duration = duration


class PathPlanner:
    def __init__(self):
        self.waypoints = []
        self.current_waypoint_index = 0
        self.navigation_active = False
        self.car_x = 0
        self.car_y = 0
        self.car_theta = 0
        self.reached_threshold = 15
        self.obstacle_avoidance = ObstacleAvoidance()
        self.navigation_state = "NORMAL"
        self.avoid_timeout = 0
        self.recovery_path = []

    def add_waypoint(self, x, y, action="navigate", description="", duration=0):
        waypoint = Waypoint(x, y, action, description, duration)
        self.waypoints.append(waypoint)
        return len(self.waypoints) - 1

    def clear_waypoints(self):
        self.waypoints.clear()
        self.current_waypoint_index = 0
        self.navigation_active = False

    def get_current_waypoint(self):
        if 0 <= self.current_waypoint_index < len(self.waypoints):
            return self.waypoints[self.current_waypoint_index]
        return None

    def calculate_distance(self, waypoint):
        dx = waypoint.x - self.car_x
        dy = waypoint.y - self.car_y
        return math.sqrt(dx * dx + dy * dy)

    def is_waypoint_reached(self, waypoint):
        return self.calculate_distance(waypoint) <= self.reached_threshold

    def get_navigation_commands(self):
        waypoint = self.get_current_waypoint()
        if not waypoint or not self.navigation_active:
            return 0, 0
        avoidance_cmd = self.obstacle_avoidance.get_avoidance_commands()
        if avoidance_cmd is not None:
            self.navigation_state = "AVOIDING"
            return avoidance_cmd
        self.navigation_state = "NORMAL"
        if self.is_waypoint_reached(waypoint):
            self.move_to_next_waypoint()
            return 0, 0
        dx = waypoint.x - self.car_x
        dy = waypoint.y - self.car_y
        target_angle = math.degrees(math.atan2(dy, dx))
        angle_error = target_angle - self.car_theta
        while angle_error > 180:
            angle_error -= 360
        while angle_error < -180:
            angle_error += 360
        distance = self.calculate_distance(waypoint)
        if distance < 30:
            base_speed = 350
        elif distance < 80:
            base_speed = 500
        else:
            base_speed = 700
        if abs(angle_error) > 45:
            base_speed = int(base_speed * 0.6)
        turn_gain = 4.5
        turn = int(angle_error * turn_gain)
        turn = max(-450, min(450, turn))
        left_speed = base_speed - turn
        right_speed = base_speed + turn
        return left_speed, right_speed

    def move_to_next_waypoint(self):
        if self.current_waypoint_index < len(self.waypoints) - 1:
            self.current_waypoint_index += 1
            buzzer.set_state(True)
            threading.Timer(0.1, lambda: buzzer.set_state(False)).start()
            return True
        else:
            self.navigation_active = False
            PWM.set_motor_model(0, 0, 0, 0)
            return False


# ================= MISSION SYSTEM =================
class Mission:
    def __init__(self, name):
        self.name = name
        self.actions = []
        self.current_action = 0
        self.active = False

    def add_action(self, action_type, params):
        self.actions.append({"type": action_type, "params": params})

    def execute_action(self, action):
        if action["type"] == "move":
            distance = action["params"].get("distance", 50)
            speed = action["params"].get("speed", 800)
            move_distance(distance, speed)
        elif action["type"] == "turn":
            angle = action["params"].get("angle", 90)
            turn_angle(angle)
        elif action["type"] == "beep":
            buzzer.set_state(True)
            threading.Timer(0.2, lambda: buzzer.set_state(False)).start()
        elif action["type"] == "ball_search":
            global current_mode
            current_mode = "ball_follow"


def move_distance(distance_cm, speed=800):
    time_needed = abs(distance_cm) / (speed / 100)
    PWM.set_motor_model(speed, speed, speed, speed)
    time.sleep(time_needed)
    PWM.set_motor_model(0, 0, 0, 0)


def turn_angle(angle_deg):
    turn_time = abs(angle_deg) / 60
    if angle_deg > 0:
        PWM.set_motor_model(-500, -500, 500, 500)
    else:
        PWM.set_motor_model(500, 500, -500, -500)
    time.sleep(turn_time)
    PWM.set_motor_model(0, 0, 0, 0)


def create_patrol_mission():
    mission = Mission("Patrol Route")
    mission.add_action("move", {"distance": 100, "speed": 600})
    mission.add_action("turn", {"angle": 90})
    mission.add_action("move", {"distance": 100, "speed": 600})
    mission.add_action("turn", {"angle": 90})
    mission.add_action("move", {"distance": 100, "speed": 600})
    mission.add_action("turn", {"angle": 90})
    mission.add_action("move", {"distance": 100, "speed": 600})
    mission.add_action("beep", {})
    return mission


def create_ball_hunt_mission():
    mission = Mission("Ball Hunt")
    mission.add_action("ball_search", {"duration": 30})
    mission.add_action("beep", {})
    return mission


path_planner = PathPlanner()
patrol_system = PatrolMission()
current_mission = None


# ================= GRACEFUL SHUTDOWN =================
def cleanup(signum, frame):
    print(f"🛑 Received signal {signum}, shutting down...")
    try:
        camera_manager.release()
    except Exception as e:
        print(f"Camera cleanup error: {e}")
    sys.exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)


# ================= FLASK ROUTES =================
@app.route("/")
def index():
    return render_template("autonomous_index.html")


@app.route("/manual")
def manual_control():
    return render_template("manual_control.html")


@app.route("/calibrate")
def calibrate():
    return render_template("callibration.html")


@app.route("/autonomous")
def autonomous():
    return render_template("autonomous_dashboard.html")


@app.route("/enhancedautonomous")
def enhancedautonomous():
    return render_template("enhancedautonomous.html")


# ================= MOTOR CONTROL ROUTES =================
@app.route("/forward")
def forward():
    global is_moving, current_mode
    if current_mode == "manual":
        PWM.set_motor_model(current_speed, current_speed, current_speed, current_speed)
        is_moving = True
    return "OK"


@app.route("/backward")
def backward():
    global is_moving, current_mode
    if current_mode == "manual":
        PWM.set_motor_model(-current_speed, -current_speed, -current_speed, -current_speed)
        is_moving = True
    return "OK"


@app.route("/left")
def left():
    global is_moving, current_mode
    if current_mode == "manual":
        PWM.set_motor_model(-current_speed, -current_speed, current_speed, current_speed)
        is_moving = True
    return "OK"


@app.route("/right")
def right():
    global is_moving, current_mode
    if current_mode == "manual":
        PWM.set_motor_model(current_speed, current_speed, -current_speed, -current_speed)
        is_moving = True
    return "OK"


@app.route("/stop")
def stop():
    global is_moving
    PWM.set_motor_model(0, 0, 0, 0)
    is_moving = False
    return "OK"


@app.route("/speed/<int:speed>")
def speed(speed):
    global current_speed
    current_speed = min(max(speed, 0), 2000)
    return jsonify({"status": "ok", "speed": current_speed})


@app.route("/beep")
def beep():
    buzzer.set_state(True)
    threading.Timer(0.2, lambda: buzzer.set_state(False)).start()
    return jsonify({"status": "ok"})


@app.route("/led/<color>")
def set_led(color):
    colors = {'red': (255, 0, 0), 'green': (0, 255, 0), 'blue': (0, 0, 255),
              'yellow': (255, 255, 0), 'white': (255, 255, 255)}
    if color in colors:
        r, g, b = colors[color]
        led.ledIndex(0xFF, r, g, b)
    return jsonify({"status": "ok", "color": color})


# ================= AUTONOMOUS MODE ROUTES =================
@app.route("/api/mode/set", methods=["POST"])
def set_mode():
    global current_mode, autonomous_active, ball_follower, patrol_system
    data = request.json
    mode = data.get("mode")
    if mode in ["manual", "ball_follow", "waypoint_nav", "patrol", "obstacle_avoid"]:
        current_mode = mode
        if mode == "manual":
            autonomous_active = False
            PWM.set_motor_model(0, 0, 0, 0)
        else:
            autonomous_active = True
            if mode == "ball_follow":
                ball_follower = SmartBallFollower()
                print("Ball following mode activated")
            elif mode == "patrol":
                patrol_system.active = True
                patrol_system.generate_patrol_path("square")
                print("Patrol mode activated")
            elif mode == "obstacle_avoid":
                print("Obstacle avoidance mode activated")
        return jsonify({"success": True, "mode": current_mode})
    return jsonify({"success": False, "error": "Invalid mode"})


@app.route("/api/patrol/start", methods=["POST"])
def start_patrol():
    global current_mode, patrol_system
    data = request.json
    shape = data.get("shape", "square")
    patrol_system.generate_patrol_path(shape)
    patrol_system.active = True
    current_mode = "patrol"
    return jsonify({"success": True, "shape": shape})


@app.route("/api/patrol/stop", methods=["POST"])
def stop_patrol():
    global patrol_system
    patrol_system.active = False
    PWM.set_motor_model(0, 0, 0, 0)
    return jsonify({"success": True})


@app.route("/api/obstacle/status", methods=["GET"])
def get_obstacle_status():
    obstacle_info = path_planner.obstacle_avoidance.get_visualization_info()
    return jsonify(obstacle_info)


@app.route("/api/ball/detect", methods=["GET"])
def ball_detection_status():
    return jsonify({
        "detected": ball_follower.detector.ball_detected,
        "position": ball_follower.detector.ball_position,
        "radius": ball_follower.detector.ball_radius,
        "confidence": ball_follower.detector.confidence,
        "state": ball_follower.state
    })


@app.route("/api/ball/calibrate", methods=["POST"])
def calibrate_ball():
    global ball_follower
    data = request.json
    h_min = data.get('h_min', 5)
    h_max = data.get('h_max', 15)
    s_min = data.get('s_min', 100)
    s_max = data.get('s_max', 255)
    v_min = data.get('v_min', 100)
    v_max = data.get('v_max', 255)
    ball_follower.detector.lower_orange = np.array([h_min, s_min, v_min])
    ball_follower.detector.upper_orange = np.array([h_max, s_max, v_max])
    return jsonify({"success": True})


@app.route("/api/ball/settings", methods=["GET"])
def get_ball_settings():
    return jsonify({
        "h_min": int(ball_follower.detector.lower_orange[0]),
        "h_max": int(ball_follower.detector.upper_orange[0]),
        "s_min": int(ball_follower.detector.lower_orange[1]),
        "s_max": int(ball_follower.detector.upper_orange[1]),
        "v_min": int(ball_follower.detector.lower_orange[2]),
        "v_max": int(ball_follower.detector.upper_orange[2]),
        "kp": ball_follower.pid.kp,
        "ki": ball_follower.pid.ki,
        "kd": ball_follower.pid.kd,
        "state": ball_follower.state
    })


@app.route("/api/ball/tune", methods=["POST"])
def tune_ball_follower():
    global ball_follower
    data = request.json
    if 'kp' in data:
        ball_follower.pid.kp = data['kp']
    if 'ki' in data:
        ball_follower.pid.ki = data['ki']
    if 'kd' in data:
        ball_follower.pid.kd = data['kd']
    return jsonify({"success": True})


@app.route("/api/waypoint/add", methods=["POST"])
def add_waypoint():
    data = request.json
    x = data.get("x", 0)
    y = data.get("y", 0)
    action = data.get("action", "navigate")
    description = data.get("description", "")
    duration = data.get("duration", 0)
    waypoint_id = path_planner.add_waypoint(x, y, action, description, duration)
    return jsonify({"success": True, "waypoint_id": waypoint_id})


@app.route("/api/waypoint/clear", methods=["POST"])
def clear_waypoints():
    path_planner.clear_waypoints()
    return jsonify({"success": True})


@app.route("/api/waypoint/list", methods=["GET"])
def list_waypoints():
    waypoints_list = []
    for i, wp in enumerate(path_planner.waypoints):
        waypoints_list.append({
            "index": i, "x": wp.x, "y": wp.y,
            "action": wp.action, "description": wp.description, "duration": wp.duration
        })
    return jsonify({"waypoints": waypoints_list})


@app.route("/api/waypoint/remove/<int:index>", methods=["DELETE"])
def remove_waypoint(index):
    if 0 <= index < len(path_planner.waypoints):
        path_planner.waypoints.pop(index)
        if path_planner.current_waypoint_index >= index:
            path_planner.current_waypoint_index = max(0, path_planner.current_waypoint_index - 1)
    return jsonify({"success": True})


@app.route("/api/navigation/start", methods=["POST"])
def start_navigation():
    if len(path_planner.waypoints) > 0:
        path_planner.navigation_active = True
        path_planner.current_waypoint_index = 0
        global current_mode
        current_mode = "waypoint_nav"
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No waypoints defined"})


@app.route("/api/navigation/stop", methods=["POST"])
def stop_navigation():
    path_planner.navigation_active = False
    PWM.set_motor_model(0, 0, 0, 0)
    return jsonify({"success": True})


@app.route("/api/mission/start/<mission_name>", methods=["POST"])
def start_mission(mission_name):
    global current_mission, current_mode
    if mission_name == "patrol":
        current_mission = create_patrol_mission()
    elif mission_name == "ball_hunt":
        current_mission = create_ball_hunt_mission()
    else:
        return jsonify({"success": False, "error": "Unknown mission"})
    current_mission.active = True
    current_mode = "mission"
    thread = threading.Thread(target=execute_mission)
    thread.start()
    return jsonify({"success": True, "mission": mission_name})


def execute_mission():
    global current_mission
    if current_mission:
        for action in current_mission.actions:
            if not current_mission.active:
                break
            current_mission.execute_action(action)
        current_mission.active = False
        PWM.set_motor_model(0, 0, 0, 0)


@app.route("/api/mission/stop", methods=["POST"])
def stop_mission():
    global current_mission
    if current_mission:
        current_mission.active = False
    return jsonify({"success": True})


@app.route("/api/status", methods=["GET"])
def get_status():
    obstacle_info = path_planner.obstacle_avoidance.get_visualization_info()
    return jsonify({
        "mode": current_mode,
        "autonomous_active": autonomous_active,
        "moving": is_moving,
        "speed": current_speed,
        "ball_detected": ball_follower.detector.ball_detected,
        "ball_confidence": ball_follower.detector.confidence,
        "ball_state": ball_follower.state,
        "waypoints_count": len(path_planner.waypoints),
        "navigation_active": path_planner.navigation_active,
        "navigation_state": path_planner.navigation_state,
        "mission_active": current_mission.active if current_mission else False,
        "patrol_active": patrol_system.active,
        "patrol_state": patrol_system.patrol_state,
        "obstacle": obstacle_info
    })


# ================= VIDEO STREAMING =================
def generate_frames():
    global current_mode, ball_follower, autonomous_active, path_planner, patrol_system

    frame_counter = 0
    print("🎥 Video stream generator started!")

    while True:
        try:
            if not camera_available:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "Camera Not Available", (50, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(frame, "Check camera connection", (50, 280),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            else:
                frame = camera_manager.capture_frame()
                if frame is None:
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "Camera Error", (50, 240),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            motor_commands = (0, 0)

            # Get ultrasonic reading for display
            try:
                ultrasonic_distance = ultrasonic_sensor.get_distance()
                if ultrasonic_distance:
                    cv2.putText(frame, f"Distance: {ultrasonic_distance}cm", (10, 130),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    if ultrasonic_distance < 10:
                        cv2.putText(frame, "TOO CLOSE!", (10, 155),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    elif ultrasonic_distance < 30:
                        cv2.putText(frame, "Getting Close", (10, 155),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                else:
                    cv2.putText(frame, "Sensor Error!", (10, 130),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            except:
                pass

            if current_mode == "ball_follow":
                try:
                    frame, motor_commands = ball_follower.process_frame(frame)
                    left_speed, right_speed = motor_commands
                    PWM.set_motor_model(left_speed, left_speed, right_speed, right_speed)
                    cv2.putText(frame, "BALL FOLLOWING MODE", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(frame, f"Motor L: {left_speed} R: {right_speed}", (10, 150),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.rectangle(frame, (280, 200), (360, 280), (0, 255, 0), 2)
                    cv2.line(frame, (0, 240), (640, 240), (255, 255, 0), 1)
                except Exception as e:
                    print(f"Ball follow error: {e}")
                    PWM.set_motor_model(0, 0, 0, 0)
            elif current_mode == "patrol":
                if patrol_system.active:
                    left_speed, right_speed = patrol_system.get_patrol_commands(0, 0, 0)
                    PWM.set_motor_model(left_speed, left_speed, right_speed, right_speed)
                    cv2.putText(frame, "PATROL MODE", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(frame, f"State: {patrol_system.patrol_state}", (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    cv2.putText(frame, f"Segment: {patrol_system.current_segment + 1}/{len(patrol_system.patrol_path)}",
                                (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                else:
                    cv2.putText(frame, "PATROL MODE (INACTIVE)", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            elif current_mode == "waypoint_nav":
                if path_planner.navigation_active:
                    left_speed, right_speed = path_planner.get_navigation_commands()
                    PWM.set_motor_model(left_speed, left_speed, right_speed, right_speed)
                    cv2.putText(frame, "WAYPOINT NAVIGATION", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(frame, f"State: {path_planner.navigation_state}", (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    current_wp = path_planner.get_current_waypoint()
                    if current_wp:
                        cv2.putText(frame, f"Target: ({current_wp.x}, {current_wp.y})", (10, 70),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                        cv2.putText(frame, f"Distance: {path_planner.calculate_distance(current_wp):.1f}cm",
                                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                else:
                    cv2.putText(frame, "WAYPOINT NAVIGATION (INACTIVE)", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            elif current_mode == "obstacle_avoid":
                avoidance_cmd = path_planner.obstacle_avoidance.get_avoidance_commands()
                if avoidance_cmd is not None:
                    left_speed, right_speed = avoidance_cmd
                    PWM.set_motor_model(left_speed, left_speed, right_speed, right_speed)
                cv2.putText(frame, "OBSTACLE AVOIDANCE MODE", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                obstacle_info = path_planner.obstacle_avoidance.get_visualization_info()
                cv2.putText(frame, f"State: {obstacle_info['state']}", (10, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                if obstacle_info['obstacle']['detected']:
                    side = obstacle_info['obstacle']['side']
                    cv2.putText(frame, f"OBSTACLE DETECTED - {side.upper()}!", (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    cv2.putText(frame, f"Front: {obstacle_info['obstacle']['front_distance']:.1f}cm",
                                (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            elif current_mode == "manual":
                cv2.putText(frame, "MANUAL MODE", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            elif current_mode == "mission":
                cv2.putText(frame, f"MISSION: {current_mission.name if current_mission else 'None'}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            cv2.putText(frame, f"Speed Setting: {current_speed}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            mode_colors = {
                "manual": (255, 255, 255),
                "ball_follow": (0, 255, 0),
                "waypoint_nav": (255, 255, 0),
                "patrol": (255, 255, 0),
                "obstacle_avoid": (0, 255, 255),
                "mission": (0, 255, 255)
            }
            color = mode_colors.get(current_mode, (255, 255, 255))
            cv2.rectangle(frame, (5, 5), (200, 110), color, 2)

            if frame is not None and frame.size > 0:
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        except Exception as e:
            print(f"Video stream error: {e}")
            time.sleep(0.05)
            continue

        time.sleep(0.033)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ================= ULTRASONIC ROUTES =================
@app.route("/api/ultrasonic/distance", methods=["GET"])
def get_ultrasonic_distance():
    try:
        distance = ultrasonic_sensor.get_distance()
        if distance is not None:
            return jsonify({
                "distance": distance,
                "status": "critical" if distance < 10 else "warning" if distance < 30 else "safe"
            })
        return jsonify({"distance": None, "status": "error"})
    except:
        return jsonify({"distance": None, "status": "error"})


@app.route("/api/ultrasonic/stream")
def ultrasonic_stream():
    def generate():
        while True:
            try:
                distance = ultrasonic_sensor.get_distance()
                data = {
                    "distance": distance,
                    "status": "critical" if distance and distance < 10 else "warning" if distance and distance < 30 else "safe"
                }
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(0.2)
            except:
                time.sleep(0.5)
                continue
    return Response(generate(), mimetype='text/event-stream')


# ================= MAIN ENTRY POINT =================
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 Autonomous Robot Car System with Enhanced Navigation")
    print("=" * 60)
    print("Access URLs:")
    print("  - Main Dashboard: http://0.0.0.0:5002/")
    print("  - Manual Control: http://0.0.0.0:5002/manual")
    print("  - Calibration Tool: http://0.0.0.0:5002/calibrate")
    print("  - AI Chat: http://0.0.0.0:5002/ai/chat")
    print("=" * 60)
    app.run(host="0.0.0.0", debug=False, port=5002)
