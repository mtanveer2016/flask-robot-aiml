from gpiozero import DistanceSensor, PWMSoftwareFallback, DistanceSensorNoEcho
import warnings
import time

class Ultrasonic:
    def __init__(self, trigger_pin: int = 27, echo_pin: int = 22, max_distance: float = 3.0):
        # Suppress the standard warnings so they don't clutter the logs
        warnings.filterwarnings("ignore", category=DistanceSensorNoEcho)
        warnings.filterwarnings("ignore", category=PWMSoftwareFallback)  
        
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self.max_distance = max_distance
        
        # queue_len=1 means it doesn't average the last 5 readings. 
        # This makes it much faster and less prone to missing the pulse.
        self.sensor = DistanceSensor(
            echo=self.echo_pin, 
            trigger=self.trigger_pin, 
            max_distance=self.max_distance,
            queue_len=1 
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def get_distance(self) -> float:
        """Get the distance measurement, return None if it fails."""
        try:
            # gpiozero raises DistanceSensorNoEcho if it misses the ping
            distance = self.sensor.distance * 100
            return round(float(distance), 1)
        except Exception as e:
            # Instead of printing a warning every time, just silently return None
            return None

    def close(self):
        self.sensor.close()
