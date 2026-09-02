from flask import Flask, render_template
from motor import Ordinary_Car
import time

app = Flask(__name__)

# Initialize the motor controller
PWM = Ordinary_Car()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/forward")
def forward():
    print("Moving FORWARD")
    # Format: set_motor_model(left_rear, left_front, right_rear, right_front)
    # Positive values = forward, Negative = backward
    PWM.set_motor_model(1000, 1000, 1000, 1000)  # Forward at speed 1000
    return render_template("index.html")

@app.route("/backward")
def backward():
    print("Moving BACKWARD")
    PWM.set_motor_model(-1000, -1000, -1000, -1000)  # Backward at speed 1000
    return render_template("index.html")

@app.route("/left")
def left():
    print("Turning LEFT")
    # Left wheels backward, right wheels forward
    PWM.set_motor_model(-1500, -1500, 2000, 2000)
    return render_template("index.html")

@app.route("/right")
def right():
    print("Turning RIGHT")
    # Left wheels forward, right wheels backward
    PWM.set_motor_model(2000, 2000, -1500, -1500)
    return render_template("index.html")

@app.route("/stop")
def stop():
    print("STOPPING")
    PWM.set_motor_model(0, 0, 0, 0)
    return render_template("index.html")

# Optional: Add speed control
@app.route("/speed/<int:speed>")
def set_speed(speed):
    """Set speed for all motors (0-2000)"""
    print(f"Setting speed to {speed}")
    # You'll need to store current direction and apply new speed
    return {"status": "ok", "speed": speed}

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False, port=5002)
