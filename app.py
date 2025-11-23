import os
import json
import time
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS

# Import our modules
from sensors import PirReader, DhtReader, UsbCamera
from actuators import Actuators
from adafruit_io import AdafruitIOClient
from rfid_reader import RFIDReader
import RPi.GPIO as GPIO

# ============================================================================
# CONFIGURATION & ENUMS
# ============================================================================

class SystemMode(Enum):
    DISARMED = "disarmed"
    ARMED = "armed"
    PRE_ALARM = "pre_alarm"
    ALARM = "alarm"

class LEDState(Enum):
    OFF = "off"
    SLOW_BLINK = "slow_blink"  # Disarmed
    SOLID = "solid"            # Pre-alarm
    FAST_BLINK = "fast_blink"  # Alarm

def load_config(path="config/config.json"):
    # Ensure config directory exists
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, path)
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Environment overrides
    if os.getenv("ADAFRUIT_IO_USERNAME"):
        config["adafruit_io"]["username"] = os.getenv("ADAFRUIT_IO_USERNAME")
    if os.getenv("ADAFRUIT_IO_KEY"):
        config["adafruit_io"]["key"] = os.getenv("ADAFRUIT_IO_KEY")
    
    # Authorized RFID tags (comma separated in ENV or list in json)
    env_rfids = os.getenv("AUTHORIZED_RFID_IDS")
    if env_rfids:
        config["authorized_rfids"] = [int(x.strip()) for x in env_rfids.split(",")]
    elif "authorized_rfids" not in config:
        config["authorized_rfids"] = [] # Default empty
        
    return config

def setup_logging(log_dir="logs"):
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File Handler
    from logging.handlers import RotatingFileHandler
    handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        maxBytes=1024*1024, # 1MB
        backupCount=5
    )
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    
    # Console Handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

# ============================================================================
# SECURITY SYSTEM CONTROLLER
# ============================================================================

class SecuritySystem:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Hardware Initialization
        try:
            self.pir = PirReader(config["pins"]["pir_bcm"], debounce_s=config["logic"]["pir_debounce_seconds"])
            self.dht = DhtReader(config["pins"]["dht_bcm"])
            self.camera = UsbCamera(
                device_index=config["camera"]["device_index"],
                width=config["camera"]["width"],
                height=config["camera"]["height"]
            )
            self.actuators = Actuators(
                led_bcm=config["pins"]["led_bcm"],
                beeper_bcm=config["pins"]["beeper_bcm"],
                servo_bcm=config["pins"]["servo_bcm"]
            )
            self.rfid_reader = RFIDReader()
        except Exception as e:
            logging.critical(f"Hardware init failed: {e}")
            raise e

        # Cloud Clients
        self.aio_client = AdafruitIOClient(
            username=config["adafruit_io"].get("username", ""),
            key=config["adafruit_io"].get("key", ""),
            host=config["adafruit_io"].get("host", "io.adafruit.com")
        )
        
        # State Variables
        self.mode = SystemMode.DISARMED
        self.stealth_mode = False
        self.led_state = LEDState.SLOW_BLINK
        
        self.last_motion_time = 0
        self.pre_alarm_start_time = 0
        self.alarm_start_time = 0
        self.last_photo_time = 0
        
        # Threading
        self.lock = threading.Lock()
        self.running = False
        
        self.event_log = []

    def log_event(self, event_type: str, details: str = ""):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "details": details,
            "mode": self.mode.value
        }
        with self.lock:
            self.event_log.append(entry)
            if len(self.event_log) > 100:
                self.event_log.pop(0)
        
        logging.info(f"EVENT: {event_type} [{details}]")
        
        # Cloud Sync
        if "event_log" in self.config["adafruit_io"]["feeds"]:
            self.aio_client.publish(self.config["adafruit_io"]["feeds"]["event_log"], 1)
        
        # TODO: Send to Neon.com here
        # neon_client.insert_log(entry)

    def arm_system(self, rfid_id=None):
        with self.lock:
            if self.mode == SystemMode.ARMED:
                return False
            
            self.mode = SystemMode.ARMED
            self.log_event("ARM", f"Source: {rfid_id if rfid_id else 'Manual'}")
            
            # 1. Lock Box
            self.actuators.lock_box(self.config["servo_angle"]["locked"])
            
            # 2. Visual Indication (3 Fast Blinks)
            for _ in range(3):
                self.actuators.led_on()
                time.sleep(0.1)
                self.actuators.led_off()
                time.sleep(0.1)
                
            # 3. Set steady state
            if self.stealth_mode:
                self.led_state = LEDState.OFF
            else:
                self.led_state = LEDState.SOLID # Or OFF depending on pref, prompt says OFF if stealth
            
            self.aio_client.publish(self.config["adafruit_io"]["feeds"]["mode"], 1)
            return True

    def disarm_system(self, rfid_id=None):
        with self.lock:
            prev_mode = self.mode
            self.mode = SystemMode.DISARMED
            self.log_event("DISARM", f"Source: {rfid_id if rfid_id else 'Manual'}")
            
            # 1. Stop Alarms
            self.actuators.alarm_active(False)
            
            # 2. Unlock Box
            self.actuators.unlock_box(self.config["servo_angle"]["unlocked"])
            
            # 3. Visual Indication
            self.led_state = LEDState.SLOW_BLINK
            
            # 4. Reset timers
            self.last_motion_time = 0
            
            self.aio_client.publish(self.config["adafruit_io"]["feeds"]["mode"], 0)
            self.aio_client.publish(self.config["adafruit_io"]["feeds"]["alarm"], 0)
            return True

    def handle_motion(self):
        """Called when PIR detects motion"""
        now = time.time()
        self.last_motion_time = now
        
        with self.lock:
            if self.mode == SystemMode.DISARMED:
                return # Ignore motion when disarmed
            
            # Publish motion event
            self.aio_client.publish(self.config["adafruit_io"]["feeds"]["motion"], 1)

            if self.mode == SystemMode.ARMED:
                # Transition to PRE-ALARM
                self.mode = SystemMode.PRE_ALARM
                self.pre_alarm_start_time = now
                self.log_event("MOTION_DETECTED", "Entering Pre-Alarm")
                
                # Immediate Photo
                self._take_photo("Motion Trigger")
                
                # Warning State
                self.led_state = LEDState.SOLID
                # Note: Beep logic handled in main loop

            elif self.mode == SystemMode.PRE_ALARM:
                # Timer handled in loop
                pass

            elif self.mode == SystemMode.ALARM:
                # Already alarming, maybe take more photos?
                if now - self.last_photo_time >= self.config["logic"]["photo_interval_seconds"]:
                    self._take_photo("Alarm Interval")

    def _take_photo(self, reason):
        try:
            fname = self.camera.snapshot()
            self.last_photo_time = time.time()
            self.log_event("PHOTO", f"{reason}: {fname}")
            # TODO: Upload to UploadCare here
        except Exception as e:
            logging.error(f"Photo failed: {e}")

    # ---------------- THREAD LOOPS ----------------

    def loop_main(self):
        """Main logic loop for timers and polling"""
        while self.running:
            with self.lock:
                now = time.time()
                
                # 1. PIR Poll
                if self.pir.read_state() == 1:
                    # Release lock briefly to handle complex logic inside handle_motion
                    pass 
                # Actually, PIR object handles debounce, just check it
                if self.pir.read_state():
                     threading.Thread(target=self.handle_motion).start()

                # 2. Pre-Alarm Logic
                if self.mode == SystemMode.PRE_ALARM:
                    elapsed = now - self.pre_alarm_start_time
                    
                    # Warning Beeps (every 2s)
                    if int(elapsed) % 2 == 0 and (elapsed - int(elapsed) < 0.1):
                         # Quick beep in background
                         threading.Thread(target=self.actuators.beep_once, args=(0.1,)).start()

                    # Timeout Check
                    if elapsed > self.config["logic"]["pre_alarm_delay_seconds"]:
                        self.mode = SystemMode.ALARM
                        self.alarm_start_time = now
                        self.log_event("ALARM_TRIGGERED", "Pre-alarm expired")
                        self.led_state = LEDState.FAST_BLINK
                        self.actuators.alarm_active(True) # Continuous ON
                        self.aio_client.publish(self.config["adafruit_io"]["feeds"]["alarm"], 1)

                # 3. Alarm Logic
                if self.mode == SystemMode.ALARM:
                    # Check timeout (Alarm Duration)
                    if (now - self.alarm_start_time) > self.config["logic"]["alarm_duration_seconds"]:
                        # Reset to Armed
                        self.mode = SystemMode.ARMED
                        self.actuators.alarm_active(False)
                        self.log_event("ALARM_RESET", "Duration expired")
                        self.led_state = LEDState.OFF if self.stealth_mode else LEDState.SOLID
                        self.aio_client.publish(self.config["adafruit_io"]["feeds"]["alarm"], 0)
                    
                    # Check Motion Timeout (If no motion for X seconds, stop)
                    elif (now - self.last_motion_time) > self.config["logic"]["motion_timeout_seconds"]:
                        self.mode = SystemMode.ARMED
                        self.actuators.alarm_active(False)
                        self.log_event("ALARM_RESET", "No motion detected")
                        self.led_state = LEDState.OFF if self.stealth_mode else LEDState.SOLID
                        self.aio_client.publish(self.config["adafruit_io"]["feeds"]["alarm"], 0)

            time.sleep(0.1)

    def loop_led(self):
        """Controls LED blinking patterns"""
        while self.running:
            state = self.led_state
            
            if state == LEDState.OFF:
                self.actuators.led_off()
                time.sleep(0.5)
            elif state == LEDState.SOLID:
                self.actuators.led_on()
                time.sleep(0.5)
            elif state == LEDState.SLOW_BLINK:
                self.actuators.led_on()
                time.sleep(1.0)
                self.actuators.led_off()
                time.sleep(1.0)
            elif state == LEDState.FAST_BLINK:
                self.actuators.led_on()
                time.sleep(0.1)
                self.actuators.led_off()
                time.sleep(0.1)
    
    def loop_rfid(self):
        """Polls RFID reader"""
        while self.running:
            try:
                tag_id = self.rfid_reader.scan()
                if tag_id:
                    logging.info(f"RFID Detected: {tag_id}")
                    # Check authorization
                    authorized_ids = self.config.get("authorized_rfids", [])
                    
                    # If list is empty, allow ALL (Debug mode) or deny ALL?
                    # Let's assume allow if list is empty for testing, OR stricter check
                    is_auth = tag_id in authorized_ids or len(authorized_ids) == 0
                    
                    if is_auth:
                        if self.mode == SystemMode.DISARMED:
                            self.arm_system(rfid_id=tag_id)
                        else:
                            self.disarm_system(rfid_id=tag_id)
                        time.sleep(2) # Prevent double toggle
                    else:
                        self.log_event("AUTH_FAIL", f"Unauthorized ID: {tag_id}")
                        self.actuators.beep_once(0.5) # Long beep for reject
                        time.sleep(1)
                else:
                    time.sleep(0.2)
            except Exception as e:
                logging.error(f"RFID Loop Error: {e}")
                time.sleep(1)

    def loop_sensors(self):
        """Slow loop for Temp/Humidity"""
        while self.running:
            t, h = self.dht.read()
            if t is not None:
                self.aio_client.publish(self.config["adafruit_io"]["feeds"]["temperature"], t)
                self.aio_client.publish(self.config["adafruit_io"]["feeds"]["humidity"], h)
            time.sleep(60)

    def start(self):
        self.running = True
        self.aio_client.connect_non_blocking()
        
        # Start threads
        threading.Thread(target=self.loop_main, daemon=True).start()
        threading.Thread(target=self.loop_led, daemon=True).start()
        threading.Thread(target=self.loop_rfid, daemon=True).start()
        threading.Thread(target=self.loop_sensors, daemon=True).start()
        
        # Ensure servo is in correct state for startup (Disarmed -> Unlocked)
        self.actuators.unlock_box()
        logging.info("System Started")

    def stop(self):
        self.running = False
        self.actuators.shutdown()
        self.aio_client.disconnect()
        GPIO.cleanup()

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__, static_folder="data/images") # Serve images directly if needed
CORS(app)
system = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    if not system: return jsonify({"error": "init"}), 500
    return jsonify({
        "mode": system.mode.value,
        "stealth": system.stealth_mode,
        "temp": system.dht.read() 
    })

@app.route('/api/arm', methods=['POST'])
def api_arm():
    if system.arm_system():
        return jsonify({"success": True, "mode": "armed"})
    return jsonify({"success": False, "msg": "Already armed"})

@app.route('/api/disarm', methods=['POST'])
def api_disarm():
    if system.disarm_system():
        return jsonify({"success": True, "mode": "disarmed"})
    return jsonify({"success": False})

@app.route('/api/stealth', methods=['POST'])
def api_stealth():
    data = request.json
    system.stealth_mode = data.get("enabled", False)
    # Update LED immediately if armed
    if system.mode == SystemMode.ARMED:
        system.led_state = LEDState.OFF if system.stealth_mode else LEDState.SOLID
    return jsonify({"success": True, "stealth": system.stealth_mode})

@app.route('/api/logs')
def api_logs():
    return jsonify({"logs": sorted(system.event_log, key=lambda x: x['timestamp'], reverse=True)})

@app.route('/api/images')
def api_images():
    # List images
    p = Path("data/images")
    files = sorted(p.glob("*.jpg"), key=os.path.getmtime, reverse=True)
    return jsonify({"images": [{"filename": f.name, "timestamp": f.stat().st_mtime} for f in files[:20]]})

@app.route('/api/images/<filename>')
def api_serve_image(filename):
    return send_from_directory('data/images', filename)

@app.route('/api/test/actuator', methods=['POST'])
def api_test():
    data = request.json
    act = data.get("actuator")
    val = data.get("value")
    
    if act == "servo":
        if val == "lock": system.actuators.lock_box()
        else: system.actuators.unlock_box()
    elif act == "buzzer":
        system.actuators.beep_once()
    elif act == "led":
        system.actuators.led_on()
        time.sleep(1)
        system.actuators.led_off()
    elif act == "camera":
        system._take_photo("Manual Test")
        
    return jsonify({"success": True})

if __name__ == '__main__':
    setup_logging()
    cfg = load_config()
    
    system = SecuritySystem(cfg)
    system.start()
    
    try:
        # Disable debug reloader to prevent double-init of hardware
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        system.stop()