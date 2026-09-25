"""
AI Routes for Flask Application
"""

import os
import json
import tempfile
import subprocess
import base64
import io
import time
from flask import Blueprint, request, jsonify, render_template, Response

from ai_modules import RobotAgent
from ai_modules.core.tool_registry import ToolRegistry

# Create blueprint
ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

# Global agent instance
agent = None


def init_agent(robot_functions=None, camera_instance=None):
    """
    Initialize the AI agent with optional camera instance.

    The camera_instance is expected to be a CameraManager from app.py
    (has .capture_frame(), .capture_pil(), .available, .release()).
    It is passed all the way down to ToolRegistry so the AI vision tools
    share the same camera as the MJPEG stream.
    """
    global agent
    agent = RobotAgent(camera_instance=camera_instance)

    # Inject the shared camera into the tool registry so vision tools
    # can use it (instead of trying to open picamera2 independently).
    if camera_instance is not None:
        agent.tools.camera = camera_instance

    if robot_functions:
        agent.set_robot_functions(robot_functions)

    return agent


def register_robot_tools(agent_instance, robot):
    """
    Register all robot functions as tools for the AI
    """
    tools = agent_instance.tools

    # ============ MOVEMENT TOOLS ============
    @tools.register("move_forward",
                    "Move the robot forward. Optionally specify speed (0-100). Do NOT use time/duration parameters.",
                    {"speed": {"type": "integer", "description": "Speed 0-100 (default 50)", "default": 50}})
    def move_forward(speed=50, **kwargs):
        """Move forward - ignores unknown params like 't'"""
        if 't' in kwargs:
            print(f"⚠️ Ignoring unknown parameter 't'={kwargs['t']}")
        if hasattr(robot, 'forward'):
            robot.forward(speed)
            return f"Moving forward at speed {speed}"
        return "Forward function not available"

    @tools.register("move_backward",
                    "Move the robot backward. Optionally specify speed (0-100). Do NOT use time/duration parameters.",
                    {"speed": {"type": "integer", "description": "Speed 0-100 (default 50)", "default": 50}})
    def move_backward(speed=50, **kwargs):
        if hasattr(robot, 'backward'):
            robot.backward(speed)
            return f"Moving backward at speed {speed}"
        return "Backward function not available"

    # ============ TIMED MOVEMENT TOOL ============
    @tools.register("move_for_time",
                    "Move the robot forward or backward for a specific number of seconds, then stop.",
                    {
                        "direction": {"type": "string", "enum": ["forward", "backward"],
                                     "description": "Direction to move", "default": "forward"},
                        "seconds": {"type": "number", "description": "How long to move (seconds)", "default": 2},
                        "speed": {"type": "integer", "description": "Speed 0-100 (default 50)", "default": 50}
                    })
    def move_for_time(direction="forward", seconds=2, speed=50, **kwargs):
        """Move for a specific duration, then stop"""
        try:
            if hasattr(robot, 'forward') and hasattr(robot, 'backward'):
                if direction == "backward":
                    robot.backward(speed)
                else:
                    robot.forward(speed)

                time.sleep(seconds)
                robot.stop()
                return f"Moved {direction} for {seconds} seconds at speed {speed}, then stopped"
            return "Movement functions not available"
        except Exception as e:
            return f"Move error: {str(e)}"

    @tools.register("turn_left",
                    "Turn the robot left. Specify angle in degrees (default 45).",
                    {"angle": {"type": "integer", "description": "Angle in degrees (default 45)", "default": 45}})
    def turn_left(angle=45, **kwargs):
        if hasattr(robot, 'turn_left'):
            robot.turn_left(angle)
            return f"Turning left {angle} degrees"
        return "Turn left function not available"

    @tools.register("turn_right",
                    "Turn the robot right. Specify angle in degrees (default 45).",
                    {"angle": {"type": "integer", "description": "Angle in degrees (default 45)", "default": 45}})
    def turn_right(angle=45, **kwargs):
        if hasattr(robot, 'turn_right'):
            robot.turn_right(angle)
            return f"Turning right {angle} degrees"
        return "Turn right function not available"

    @tools.register("stop_robot",
                    "Stop the robot immediately. No parameters needed.",
                    {})
    def stop_robot(**kwargs):
        if hasattr(robot, 'stop'):
            robot.stop()
            return "Robot stopped"
        return "Stop function not available"

    # ============ AUTONOMOUS MODE TOOLS ============
    @tools.register("follow_ball",
                    "Start ball following mode. No parameters needed.",
                    {})
    def follow_ball(**kwargs):
        if hasattr(robot, 'start_ball_follow'):
            robot.start_ball_follow()
            return "Ball following mode activated"
        return "Ball following not available"

    @tools.register("start_patrol",
                    "Start patrol mode. Specify shape: square, rectangle, zigzag, or circle.",
                    {"shape": {"type": "string", "enum": ["square", "rectangle", "zigzag", "circle"],
                              "description": "Patrol pattern shape (default: square)", "default": "square"}})
    def start_patrol(shape="square", **kwargs):
        if hasattr(robot, 'start_patrol'):
            robot.start_patrol(shape)
            return f"Patrol mode activated with {shape} pattern"
        return "Patrol not available"

    # ============ PERIPHERAL TOOLS ============
    @tools.register("beep_buzzer",
                    "Make the buzzer beep. Optionally specify duration in seconds (default 0.2).",
                    {"duration": {"type": "number", "description": "Beep duration in seconds (default 0.2)", "default": 0.2}})
    def beep_buzzer(duration=0.2, **kwargs):
        if hasattr(robot, 'beep'):
            robot.beep(duration)
            return f"Buzzer beeped for {duration}s"
        return "Buzzer not available"

    @tools.register("set_led",
                    "Set the LED color. Choose from: red, green, blue, yellow, white, off.",
                    {"color": {"type": "string", "enum": ["red", "green", "blue", "yellow", "white", "off"],
                              "description": "LED color"}})
    def set_led(color, **kwargs):
        if hasattr(robot, 'set_led'):
            robot.set_led(color)
            return f"LED set to {color}"
        return "LED not available"

    # ============ ULTRASONIC SENSOR TOOL ============
    @tools.register(
        "get_distance",
        "Get the current distance from the ultrasonic sensor. No parameters needed.",
        {}
    )
    def get_distance(**kwargs):
        """Get ultrasonic distance reading"""
        try:
            import ultrasonic
            sensor = ultrasonic.Ultrasonic()
            distance = sensor.get_distance()
            if distance is not None:
                return f"Distance: {distance}cm"
            return "Error reading ultrasonic sensor"
        except Exception as e:
            return f"Ultrasonic sensor error: {str(e)}"

    return tools


# ================= AI Routes =================

@ai_bp.route('/status', methods=['GET'])
def ai_status():
    """Get AI agent status"""
    if agent is None:
        return jsonify({
            "status": "not_initialized",
            "message": "AI agent not initialized"
        }), 503

    return jsonify({
        "status": "ready",
        "agent": agent.get_status()
    })


@ai_bp.route('/command', methods=['POST'])
def ai_command():
    """Send a command to the AI agent."""
    if agent is None:
        return jsonify({"error": "AI agent not initialized"}), 503

    data = request.json
    command = data.get('command', '')
    image = data.get('image')

    if not command:
        return jsonify({"error": "No command provided"}), 400

    image_data = None
    if image:
        try:
            from PIL import Image
            image_bytes = base64.b64decode(image)
            image_data = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            return jsonify({"error": f"Failed to process image: {str(e)}"}), 400

    result = agent.process_command(command, image_data)
    return jsonify(result)


@ai_bp.route('/voice', methods=['POST'])
def ai_voice():
    """Process voice input from browser."""
    global agent

    print("\n" + "=" * 60)
    print("🎤 VOICE REQUEST RECEIVED")
    print("=" * 60)

    if agent is None:
        print("❌ AI agent not initialized")
        return jsonify({"error": "AI agent not initialized"}), 503

    if 'audio' not in request.files:
        print("❌ No audio file in request")
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']

    if audio_file.filename == '':
        print("❌ Empty filename")
        return jsonify({"error": "No audio file selected"}), 400

    audio_bytes = audio_file.read()
    print(f"📦 Received: {len(audio_bytes)} bytes")
    print(f"📄 Filename: {audio_file.filename}")
    print(f"📄 Content type: {audio_file.content_type}")

    if len(audio_bytes) < 1000:
        print("❌ Audio too short")
        return jsonify({"error": "Audio too short, please speak longer"}), 400

    # Check if it's webm format
    is_webm = (
        audio_file.filename.endswith('.webm') or
        'webm' in (audio_file.content_type or '') or
        audio_bytes[:4] == b'\x1a\x45\xdf\xa3'
    )

    if is_webm:
        print("🔄 Converting WebM to WAV...")

        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
            f.write(audio_bytes)
            webm_path = f.name

        wav_path = webm_path + '.wav'

        try:
            result = subprocess.run([
                'ffmpeg', '-i', webm_path,
                '-ar', '16000',
                '-ac', '1',
                '-f', 'wav',
                '-y',
                wav_path
            ], capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                print(f"❌ FFmpeg error: {result.stderr}")
                return jsonify({"error": "Audio conversion failed"}), 500

            with open(wav_path, 'rb') as f:
                audio_bytes = f.read()

            print(f"✅ Converted to WAV: {len(audio_bytes)} bytes")

        except FileNotFoundError:
            print("❌ FFmpeg not installed")
            return jsonify({"error": "ffmpeg not installed"}), 500
        except subprocess.TimeoutExpired:
            print("❌ FFmpeg timeout")
            return jsonify({"error": "Audio conversion timed out"}), 500
        except Exception as e:
            print(f"❌ Conversion error: {e}")
            return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
        finally:
            if os.path.exists(webm_path):
                os.unlink(webm_path)
            if os.path.exists(wav_path):
                os.unlink(wav_path)

    # Process voice with AI agent
    print("🧠 Processing voice with AI agent...")
    try:
        result = agent.process_voice(audio_bytes)

        print(f"✅ Success: {result.get('success')}")
        print(f"✅ Transcription: {result.get('transcription', 'N/A')}")
        print(f"✅ Response: {str(result.get('response', 'N/A'))[:200]}")
        print(f"✅ Has audio: {result.get('audio') is not None}")

        # Safety net: convert bytes to base64 if still present
        if result.get('audio') and isinstance(result['audio'], bytes):
            result['audio'] = base64.b64encode(result['audio']).decode('utf-8')
            print(f"✅ Audio re-encoded to base64")

        return jsonify(result)

    except Exception as e:
        print(f"❌ Processing error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500


@ai_bp.route('/vision/describe', methods=['POST'])
def ai_vision_describe():
    """Describe an image."""
    if agent is None:
        return jsonify({"error": "AI agent not initialized"}), 503

    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['image']

    try:
        from PIL import Image
        image = Image.open(io.BytesIO(image_file.read()))
        description = agent.vision.describe_image(image)
        return jsonify({"description": description})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route('/vision/detect', methods=['POST'])
def ai_vision_detect():
    """Detect objects in an image."""
    if agent is None:
        return jsonify({"error": "AI agent not initialized"}), 503

    data = request.json
    objects = data.get('objects', [])

    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    image_file = request.files['image']

    try:
        from PIL import Image
        image = Image.open(io.BytesIO(image_file.read()))
        results = agent.vision.detect_objects(image, objects)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route('/history', methods=['GET'])
def ai_history():
    """Get conversation history"""
    if agent is None:
        return jsonify({"error": "AI agent not initialized"}), 503

    return jsonify({
        "history": agent.context["conversation"],
        "count": len(agent.context["conversation"])
    })


@ai_bp.route('/history/clear', methods=['POST'])
def ai_clear_history():
    """Clear conversation history"""
    if agent is None:
        return jsonify({"error": "AI agent not initialized"}), 503

    agent.clear_history()
    return jsonify({"success": True, "message": "History cleared"})


@ai_bp.route('/settings', methods=['POST'])
def ai_settings():
    """Update AI settings"""
    if agent is None:
        return jsonify({"error": "AI agent not initialized"}), 503

    data = request.json
    model = data.get('model')

    if model:
        agent.llm.set_model(model)
        return jsonify({"success": True, "model": model})

    return jsonify({"error": "Invalid settings"}), 400


# ================= Web Interface =================

@ai_bp.route('/chat', methods=['GET'])
def ai_chat_page():
    """AI Chat interface page"""
    return render_template('ai/chat.html')


@ai_bp.route('/voice_interface', methods=['GET'])
def ai_voice_page():
    """AI Voice interface page"""
    return render_template('ai/voice.html')


@ai_bp.route('/dashboard', methods=['GET'])
def ai_dashboard():
    """AI Dashboard page"""
    return render_template('ai/dashboard.html')
