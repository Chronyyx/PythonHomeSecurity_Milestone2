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

import time
import logging
import adafruit_dht
import board


class DhtReader:
    def __init__(self, board_pin_str: str):
        pin_obj = getattr(board, board_pin_str, None)
        if pin_obj is None:
            raise RuntimeError(f"Invalid board pin '{board_pin_str}' for CircuitPython DHT")
        self._pin_obj = pin_obj

    def read(self):
        dht = None
        try:
            # create a fresh sensor for each read (more reliable under systemd / other libs)
            dht = adafruit_dht.DHT11(self._pin_obj, use_pulseio=False)
            time.sleep(2.0)  # required settle time
            temp = dht.temperature
            hum = dht.humidity
            if temp is None or hum is None:
                logging.warning("DHT11 read returned None values")
                return None, None
            return float(temp), float(hum)
        except Exception as e:
            logging.warning("DHT11 read exception: %s", e)
            return None, None
        finally:
            try:
                if dht is not None:
                    dht.exit()
            except Exception:
                pass


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
