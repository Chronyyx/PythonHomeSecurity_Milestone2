"""
AnLex Guard Security System - Flask Backend
Complete backend with state management, RFID integration, and API endpoints
"""
import os
import json
import time
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from sensors import PirReader, DhtReader, UsbCamera
from actuators import Actuators
from adafruit_io import AdafruitIOClient
from mfrc522 import SimpleMFRC522
import RPi.GPIO as GPIO

# ============================================================================
# CONFIGURATION
# ============================================================================

class SystemMode(Enum):
    DISARMED = "disarmed"
    ARMED = "armed"
    PRE_ALARM = "pre_alarm"
    ALARM = "alarm"

class LEDState(Enum):
    OFF = "off"
    SLOW_BLINK = "slow_blink"  # Disarmed
    SOLID = "solid"  # Armed
    FAST_BLINK = "fast_blink"  # Alarm

def load_config(path="config/config.json"):
    with open(path, "r") as f:
        return json.load(f)

def setup_logging(log_dir="logs"):
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    from logging.handlers import TimedRotatingFileHandler
    handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        when="midnight",
        backupCount=30,
        utc=True
    )
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

# ============================================================================
# SECURITY SYSTEM STATE MANAGER
# ============================================================================

class SecuritySystem:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pins = config["pins"]
        self.logic = config["logic"]
        
        # Initialize hardware
        self.pir = PirReader(self.pins["pir_bcm"], debounce_s=self.logic.get("pir_debounce_seconds", 1.0))
        self.dht = DhtReader(self.pins["dht_bcm"])
        self.camera = UsbCamera(
            device_index=config["camera"]["device_index"],
            width=config["camera"]["width"],
            height=config["camera"]["height"]
        )
        self.actuators = Actuators(
            led_bcm=self.pins["led_bcm"],
            beeper_bcm=self.pins["beeper_bcm"],
            servo_bcm=self.pins["servo_bcm"]
        )
        
        # RFID setup
        GPIO.setmode(GPIO.BCM)
        self.rfid_reader = SimpleMFRC522()
        self.authorized_rfid_ids = config.get("authorized_rfids", [565967042481])
        
        # Adafruit IO
        aio_cfg = config["adafruit_io"]
        self.aio_client = AdafruitIOClient(
            username=aio_cfg["username"],
            key=aio_cfg["key"],
            host=aio_cfg.get("host", "io.adafruit.com"),
            port=aio_cfg.get("port", 8883),
            use_tls=aio_cfg.get("use_tls", True)
        )
        self.feeds = aio_cfg["feeds"]
        
        # State management
        self.mode = SystemMode.DISARMED
        self.stealth_mode = False
        self.led_state = LEDState.SLOW_BLINK
        
        # Timing
        self.pre_alarm_delay = self.logic.get("pre_alarm_delay_seconds", 30)
        self.alarm_duration = self.logic.get("alarm_duration_seconds", 180)
        self.motion_timeout = self.logic.get("motion_timeout_seconds", 60)
        self.photo_interval = self.logic.get("photo_interval_seconds", 5)
        
        # State tracking
        self.last_motion_time = None
        self.alarm_start_time = None
        self.pre_alarm_start_time = None
        self.last_photo_time = None
        
        # Threading locks
        self.lock = threading.Lock()
        self.running = False
        self.main_thread = None
        self.led_thread = None
        self.rfid_thread = None
        
        # Event log
        self.event_log = []
        self.max_log_entries = 1000
        
        logging.info("SecuritySystem initialized")
    
    def log_event(self, event_type: str, details: str = ""):
        """Log system events"""
        timestamp = datetime.now(timezone.utc).isoformat()
        event = {
            "timestamp": timestamp,
            "type": event_type,
            "details": details,
            "mode": self.mode.value
        }
        
        with self.lock:
            self.event_log.append(event)
            if len(self.event_log) > self.max_log_entries:
                self.event_log.pop(0)
        
        logging.info(f"EVENT: {event_type} - {details}")
        
        # Publish to Adafruit IO
        try:
            if "event_log" in self.feeds:
                self.aio_client.publish_number(self.feeds["event_log"], 1)
        except Exception as e:
            logging.warning(f"Failed to publish event to Adafruit IO: {e}")
    
    def connect_adafruit_io(self):
        """Connect to Adafruit IO"""
        try:
            self.aio_client.connect()
            logging.info("Connected to Adafruit IO")
            self.log_event("SYSTEM", "Connected to Adafruit IO")
        except Exception as e:
            logging.error(f"Failed to connect to Adafruit IO: {e}")
    
    def arm_system(self, rfid_id: Optional[int] = None):
        """Arm the security system"""
        with self.lock:
            if self.mode != SystemMode.DISARMED:
                return {"success": False, "message": "System already armed"}
            
            self.mode = SystemMode.ARMED
            self.log_event("ARM", f"RFID: {rfid_id}" if rfid_id else "Manual")
            
            # Lock the servo
            self.actuators.servo.angle = 0  # Locked position
            time.sleep(0.5)
            self.actuators.servo.detach()
            
            # LED indication
            self.actuators.led.off()
            # 3 fast blinks
            for _ in range(3):
                self.actuators.led.on()
                time.sleep(0.1)
                self.actuators.led.off()
                time.sleep(0.1)
            
            # Set LED state based on stealth mode
            if self.stealth_mode:
                self.led_state = LEDState.OFF
            else:
                self.led_state = LEDState.SOLID
            
            # Publish to Adafruit IO
            try:
                self.aio_client.publish_number(self.feeds["mode"], 1)  # 1 = Armed
            except Exception as e:
                logging.warning(f"Failed to publish mode to Adafruit IO: {e}")
            
            return {"success": True, "message": "System armed", "mode": self.mode.value}
    
    def disarm_system(self, rfid_id: Optional[int] = None):
        """Disarm the security system"""
        with self.lock:
            previous_mode = self.mode
            self.mode = SystemMode.DISARMED
            self.log_event("DISARM", f"RFID: {rfid_id}" if rfid_id else "Manual")
            
            # Turn off alarms immediately
            self.actuators.beeper.off()
            
            # Unlock the servo
            self.actuators.servo.angle = 90  # Unlocked position
            time.sleep(0.5)
            self.actuators.servo.detach()
            
            # Set LED to slow blink
            self.led_state = LEDState.SLOW_BLINK
            
            # Reset timing states
            self.last_motion_time = None
            self.alarm_start_time = None
            self.pre_alarm_start_time = None
            
            # Publish to Adafruit IO
            try:
                self.aio_client.publish_number(self.feeds["mode"], 0)  # 0 = Disarmed
            except Exception as e:
                logging.warning(f"Failed to publish mode to Adafruit IO: {e}")
            
            return {
                "success": True,
                "message": f"System disarmed from {previous_mode.value}",
                "mode": self.mode.value
            }
    
    def handle_motion_detected(self):
        """Handle motion detection when system is armed"""
        with self.lock:
            if self.mode not in [SystemMode.ARMED, SystemMode.PRE_ALARM]:
                return
            
            current_time = time.time()
            self.last_motion_time = current_time
            
            if self.mode == SystemMode.ARMED:
                # Enter PRE_ALARM state
                self.mode = SystemMode.PRE_ALARM
                self.pre_alarm_start_time = current_time
                self.log_event("MOTION_DETECTED", "Pre-alarm started")
                
                # Take first photo immediately
                try:
                    photo_path = self.camera.snapshot()
                    self.log_event("PHOTO_TAKEN", str(photo_path))
                    self.last_photo_time = current_time
                except Exception as e:
                    logging.error(f"Failed to take photo: {e}")
                
                # LED solid red
                self.led_state = LEDState.SOLID
                self.actuators.led.on()
                
                # Publish to Adafruit IO
                try:
                    self.aio_client.publish_number(self.feeds["motion"], 1)
                except Exception as e:
                    logging.warning(f"Failed to publish motion to Adafruit IO: {e}")
    
    def check_pre_alarm_timeout(self):
        """Check if pre-alarm period has expired"""
        with self.lock:
            if self.mode != SystemMode.PRE_ALARM:
                return
            
            current_time = time.time()
            if current_time - self.pre_alarm_start_time >= self.pre_alarm_delay:
                # Escalate to ALARM
                self.mode = SystemMode.ALARM
                self.alarm_start_time = current_time
                self.log_event("ALARM_TRIGGERED", "Pre-alarm timeout expired")
                
                # Activate full alarm
                self.actuators.beeper.on()
                self.led_state = LEDState.FAST_BLINK
                
                # Publish to Adafruit IO
                try:
                    self.aio_client.publish_number(self.feeds["alarm"], 1)
                except Exception as e:
                    logging.warning(f"Failed to publish alarm to Adafruit IO: {e}")
    
    def check_alarm_timeout(self):
        """Check if alarm should continue or reset"""
        with self.lock:
            if self.mode != SystemMode.ALARM:
                return
            
            current_time = time.time()
            
            # If no motion for motion_timeout, stop alarm
            if self.last_motion_time and (current_time - self.last_motion_time) >= self.motion_timeout:
                self.mode = SystemMode.ARMED
                self.actuators.beeper.off()
                self.led_state = LEDState.SOLID if not self.stealth_mode else LEDState.OFF
                self.log_event("ALARM_STOPPED", "No motion detected for timeout period")
                self.alarm_start_time = None
                
                try:
                    self.aio_client.publish_number(self.feeds["alarm"], 0)
                except Exception as e:
                    logging.warning(f"Failed to publish alarm status: {e}")
            
            # Take photos during alarm at intervals
            if self.last_photo_time is None or (current_time - self.last_photo_time) >= self.photo_interval:
                try:
                    photo_path = self.camera.snapshot()
                    self.log_event("PHOTO_TAKEN", str(photo_path))
                    self.last_photo_time = current_time
                except Exception as e:
                    logging.error(f"Failed to take photo: {e}")
    
    def read_temperature(self):
        """Read and publish temperature/humidity"""
        try:
            temp_c, humidity = self.dht.read()
            if temp_c is not None and humidity is not None:
                # Publish to Adafruit IO
                try:
                    self.aio_client.publish_number(self.feeds["temperature"], float(temp_c))
                    self.aio_client.publish_number(self.feeds["humidity"], float(humidity))
                except Exception as e:
                    logging.warning(f"Failed to publish temp/humidity: {e}")
                
                return {"temperature": temp_c, "humidity": humidity}
        except Exception as e:
            logging.error(f"Failed to read DHT sensor: {e}")
        return None
    
    def led_controller(self):
        """LED control thread"""
        while self.running:
            try:
                if self.led_state == LEDState.OFF:
                    self.actuators.led.off()
                    time.sleep(0.5)
                
                elif self.led_state == LEDState.SOLID:
                    self.actuators.led.on()
                    time.sleep(0.5)
                
                elif self.led_state == LEDState.SLOW_BLINK:
                    self.actuators.led.on()
                    time.sleep(1.0)
                    self.actuators.led.off()
                    time.sleep(1.0)
                
                elif self.led_state == LEDState.FAST_BLINK:
                    self.actuators.led.on()
                    time.sleep(0.2)
                    self.actuators.led.off()
                    time.sleep(0.2)
            
            except Exception as e:
                logging.error(f"LED controller error: {e}")
                time.sleep(1)
    
    def rfid_monitor(self):
        """RFID monitoring thread"""
        while self.running:
            try:
                # Non-blocking RFID read with timeout
                id_read, _ = self.rfid_reader.read_no_block()
                
                if id_read:
                    logging.info(f"RFID scanned: {id_read}")
                    
                    if id_read in self.authorized_rfid_ids:
                        if self.mode == SystemMode.DISARMED:
                            self.arm_system(rfid_id=id_read)
                        else:
                            self.disarm_system(rfid_id=id_read)
                    else:
                        self.log_event("RFID_UNAUTHORIZED", f"ID: {id_read}")
                
                time.sleep(0.5)
            
            except Exception as e:
                logging.error(f"RFID monitor error: {e}")
                time.sleep(2)
    
    def main_loop(self):
        """Main system monitoring loop"""
        last_temp_read = 0
        temp_read_interval = 60  # Read temperature every 60 seconds
        
        while self.running:
            try:
                # Read motion sensor
                motion = self.pir.read_state()
                
                if motion == 1:
                    self.handle_motion_detected()
                
                # Check state timeouts
                self.check_pre_alarm_timeout()
                self.check_alarm_timeout()
                
                # Read temperature periodically
                current_time = time.time()
                if current_time - last_temp_read >= temp_read_interval:
                    self.read_temperature()
                    last_temp_read = current_time
                
                time.sleep(0.5)
            
            except Exception as e:
                logging.error(f"Main loop error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the security system"""
        if self.running:
            return {"success": False, "message": "System already running"}
        
        self.running = True
        self.connect_adafruit_io()
        
        # Start threads
        self.main_thread = threading.Thread(target=self.main_loop, daemon=True)
        self.led_thread = threading.Thread(target=self.led_controller, daemon=True)
        self.rfid_thread = threading.Thread(target=self.rfid_monitor, daemon=True)
        
        self.main_thread.start()
        self.led_thread.start()
        self.rfid_thread.start()
        
        self.log_event("SYSTEM", "Security system started")
        logging.info("Security system started")
        
        return {"success": True, "message": "System started"}
    
    def stop(self):
        """Stop the security system"""
        self.running = False
        self.log_event("SYSTEM", "Security system stopped")
        
        # Wait for threads to finish
        if self.main_thread:
            self.main_thread.join(timeout=2)
        if self.led_thread:
            self.led_thread.join(timeout=2)
        if self.rfid_thread:
            self.rfid_thread.join(timeout=2)
        
        # Cleanup
        self.actuators.shutdown()
        self.camera.close()
        self.aio_client.disconnect()
        GPIO.cleanup()
        
        logging.info("Security system stopped")
        return {"success": True, "message": "System stopped"}
    
    def get_status(self):
        """Get current system status"""
        with self.lock:
            return {
                "mode": self.mode.value,
                "stealth_mode": self.stealth_mode,
                "led_state": self.led_state.value,
                "last_motion_time": self.last_motion_time,
                "running": self.running
            }

# ============================================================================
# FLASK APPLICATION
# ============================================================================

app = Flask(__name__)
CORS(app)

# Global system instance
system: Optional[SecuritySystem] = None

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status"""
    if system is None:
        return jsonify({"error": "System not initialized"}), 500
    
    status = system.get_status()
    temp_data = system.read_temperature()
    
    response = {
        "status": status,
        "temperature": temp_data
    }
    
    return jsonify(response)

@app.route('/api/arm', methods=['POST'])
def arm_system():
    """Arm the security system"""
    if system is None:
        return jsonify({"error": "System not initialized"}), 500
    
    result = system.arm_system()
    return jsonify(result)

@app.route('/api/disarm', methods=['POST'])
def disarm_system():
    """Disarm the security system"""
    if system is None:
        return jsonify({"error": "System not initialized"}), 500
    
    result = system.disarm_system()
    return jsonify(result)

@app.route('/api/stealth', methods=['POST'])
def toggle_stealth():
    """Toggle stealth mode"""
    if system is None:
        return jsonify({"error": "System not initialized"}), 500
    
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    with system.lock:
        system.stealth_mode = enabled
        if system.mode == SystemMode.ARMED:
            system.led_state = LEDState.OFF if enabled else LEDState.SOLID
        system.log_event("STEALTH_MODE", f"{'Enabled' if enabled else 'Disabled'}")
    
    return jsonify({"success": True, "stealth_mode": enabled})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get event logs"""
    if system is None:
        return jsonify({"error": "System not initialized"}), 500
    
    limit = request.args.get('limit', default=100, type=int)
    
    with system.lock:
        logs = system.event_log[-limit:]
    
    return jsonify({"logs": logs})

@app.route('/api/images', methods=['GET'])
def list_images():
    """List captured images"""
    images_dir = Path("data/images")
    if not images_dir.exists():
        return jsonify({"images": []})
    
    images = []
    for img_file in sorted(images_dir.glob("*.jpg"), reverse=True):
        images.append({
            "filename": img_file.name,
            "timestamp": img_file.stat().st_mtime,
            "size": img_file.stat().st_size
        })
    
    limit = request.args.get('limit', default=50, type=int)
    return jsonify({"images": images[:limit]})

@app.route('/api/images/<filename>', methods=['GET'])
def get_image(filename):
    """Serve a specific image"""
    images_dir = Path("data/images")
    return send_from_directory(images_dir, filename)

@app.route('/api/actuators/test', methods=['POST'])
def test_actuators():
    """Test individual actuators"""
    if system is None:
        return jsonify({"error": "System not initialized"}), 500
    
    data = request.get_json()
    actuator = data.get('actuator')
    action = data.get('action')
    
    try:
        if actuator == 'led':
            if action == 'on':
                system.actuators.led.on()
            else:
                system.actuators.led.off()
        
        elif actuator == 'beeper':
            if action == 'on':
                system.actuators.beeper.on()
            else:
                system.actuators.beeper.off()
        
        elif actuator == 'servo':
            angle = data.get('angle', 90)
            system.actuators.servo.angle = angle
            time.sleep(0.5)
            system.actuators.servo.detach()
        
        elif actuator == 'camera':
            photo_path = system.camera.snapshot()
            return jsonify({"success": True, "photo": str(photo_path)})
        
        else:
            return jsonify({"error": "Unknown actuator"}), 400
        
        system.log_event("ACTUATOR_TEST", f"{actuator} - {action}")
        return jsonify({"success": True})
    
    except Exception as e:
        logging.error(f"Actuator test failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """Get or update system settings"""
    if system is None:
        return jsonify({"error": "System not initialized"}), 500
    
    if request.method == 'GET':
        return jsonify({
            "pre_alarm_delay": system.pre_alarm_delay,
            "alarm_duration": system.alarm_duration,
            "motion_timeout": system.motion_timeout,
            "photo_interval": system.photo_interval,
            "stealth_mode": system.stealth_mode
        })
    
    else:  # POST
        data = request.get_json()
        
        with system.lock:
            if 'pre_alarm_delay' in data:
                system.pre_alarm_delay = data['pre_alarm_delay']
            if 'alarm_duration' in data:
                system.alarm_duration = data['alarm_duration']
            if 'motion_timeout' in data:
                system.motion_timeout = data['motion_timeout']
            if 'photo_interval' in data:
                system.photo_interval = data['photo_interval']
            if 'stealth_mode' in data:
                system.stealth_mode = data['stealth_mode']
        
        system.log_event("SETTINGS_UPDATED", str(data))
        return jsonify({"success": True, "message": "Settings updated"})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "system_running": system is not None and system.running,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

def initialize_system():
    """Initialize the security system"""
    global system
    
    setup_logging()
    config = load_config()
    
    system = SecuritySystem(config)
    system.start()
    
    logging.info("Flask application initialized")

if __name__ == '__main__':
    initialize_system()
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    finally:
        if system:
            system.stop()