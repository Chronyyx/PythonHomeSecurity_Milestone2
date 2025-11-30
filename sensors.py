import cv2
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from gpiozero import MotionSensor

# CircuitPython DHT stack
import adafruit_dht
import board
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

class PirReader:
    def __init__(self, pir_bcm: int, debounce_s: float = 1.0):
        # pull_up=False is often needed for PIRs connecting to 3.3v logic
        self.sensor = MotionSensor(pir_bcm, queue_len=1, sample_rate=100, threshold=0.5)
        self.debounce_s = debounce_s
        self._last_state = 0
        self._last_change = 0.0

    def read_state(self) -> int:
        # Returns 1 for motion, 0 for no motion
        val = 1 if self.sensor.motion_detected else 0
        return val

class DhtReader:
    def __init__(self, board_pin_str: str):
        # Map string "D4" to board.D4
        pin_obj = getattr(board, board_pin_str, None)
        if pin_obj is None:
            # Fallback or error
            logging.warning(f"Invalid pin {board_pin_str}, defaulting to D4")
            pin_obj = board.D4
        self._pin_obj = pin_obj
        self.dht = None

    def read(self):
        # Initialize on demand or keep persistent. 
        # Re-initializing often helps with DHT11 stability on Pi.
        try:
            if self.dht is None:
                self.dht = adafruit_dht.DHT11(self._pin_obj)
            
            # DHT11 needs time between reads, usually handled by caller logic
            # but we wrap in try-except for the specific runtime errors
            temp = self.dht.temperature
            hum = self.dht.humidity
            
            if temp is None or hum is None:
                return None, None
            return float(temp), float(hum)

        except RuntimeError as e:
            # Common DHT errors (checksum, timeout)
            logging.debug(f"DHT Read Error: {e}")
            return None, None
        except Exception as e:
            logging.error(f"DHT Critical Error: {e}")
            if self.dht:
                self.dht.exit()
                self.dht = None
            return None, None

class UsbCamera:
    def __init__(self, device_index: int = 0, width: int = 1280, height: int = 720, images_dir: str = "data/images"):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock() # Camera hardware is not thread safe

    def snapshot(self) -> Path:
        with self.lock:
            cap = cv2.VideoCapture(self.device_index)
            try:
                # Set properties (some cameras might take a moment to adjust exposure)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                
                if not cap.isOpened():
                    raise RuntimeError("USB camera not available")
                
                # Read a few frames to let auto-exposure settle
                for _ in range(5):
                    cap.read()
                
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("Failed to read frame from USB camera")
                
                ts = iso_now()
                filename = f"snapshot_{ts}.jpg"
                path = self.images_dir / filename
                
                # UploadCare / Neon logic would happen here in the future
                # upload_to_cloud(path)
                
                cv2.imwrite(str(path), frame)
                logging.info("Saved snapshot: %s", path)
                return filename
            finally:
                cap.release()



class RFIDReader:
    def __init__(self):
        # Suppress GPIO warnings
        GPIO.setwarnings(False)
        self.reader = SimpleMFRC522()

    def scan(self):
        try:
            id, _ = self.reader.read()
            print('ID: ', id)
            return id
            
        except Exception as e:
            logging.error(f"RFID Scan error: {e}")
            return None
