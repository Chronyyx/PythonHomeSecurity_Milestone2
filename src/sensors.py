"""
Sensors: PIR, DHT11, USB camera (OpenCV).
This version supports ONLY CircuitPython `adafruit_dht`.
"""
import cv2, time, logging
from datetime import datetime, timezone
from pathlib import Path
from gpiozero import MotionSensor

# CircuitPython DHT stack
import adafruit_dht
import board

def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

class PirReader:
    def __init__(self, pir_bcm: int, debounce_s: float = 1.0):
        self.sensor = MotionSensor(pir_bcm, queue_len=1, sample_rate=100, threshold=0.5)
        self.debounce_s = debounce_s
        self._last_state = 0
        self._last_change = 0.0

    def read_state(self) -> int:
        state = 1 if self.sensor.motion_detected else 0
        now = time.time()
        if state != self._last_state and (now - self._last_change) >= self.debounce_s:
            self._last_state = state
            self._last_change = now
        return self._last_state

class DhtReader:
    def __init__(self, dht_bcm: int):
        # Map BCM pin to board pin for CircuitPython
        bcm_to_board = {
            4: getattr(board, "D4", None),
            17: getattr(board, "D17", None),
            27: getattr(board, "D27", None),
            22: getattr(board, "D22", None),
            5: getattr(board, "D5", None),
            6: getattr(board, "D6", None),
            12: getattr(board, "D12", None),
            13: getattr(board, "D13", None),
            16: getattr(board, "D16", None),
            18: getattr(board, "D18", None),
            23: getattr(board, "D23", None),
            24: getattr(board, "D24", None),
            25: getattr(board, "D25", None),
        }
        pin_obj = bcm_to_board.get(dht_bcm)
        if pin_obj is None:
            raise RuntimeError(f"Unsupported DHT BCM pin {dht_bcm} for CircuitPython mapping")
        # Use DHT11; change to DHT22 if you upgrade the sensor
        self._dht = adafruit_dht.DHT11(pin_obj, use_pulseio=False)

    def read(self):
        # CircuitPython lib requires delays and can raise RuntimeError intermittently
        try:
            time.sleep(2.0)
            temp = self._dht.temperature
            hum = self._dht.humidity
            if temp is None or hum is None:
                logging.warning("DHT11 read returned None values")
                return None, None
            return float(temp), float(hum)
        except Exception as e:
            logging.warning("DHT11 read exception: %s", e)
            return None, None

class UsbCamera:
    def __init__(self, device_index: int = 0, width: int = 1280, height: int = 720, images_dir: str = "data/images"):
        self.cap = None
        self.device_index = device_index
        self.width = width
        self.height = height
        self.images_dir = Path(images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _ensure(self):
        if self.cap is None:
            cap = cv2.VideoCapture(self.device_index)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            if not cap.isOpened():
                raise RuntimeError("USB camera not available")
            self.cap = cap

    def snapshot(self) -> Path:
        self._ensure()
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("Failed to read frame from USB camera")
        ts = iso_now()
        path = self.images_dir / f"snapshot_{ts}.jpg"
        cv2.imwrite(str(path), frame)
        logging.info("Saved snapshot: %s", path)
        return path

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
