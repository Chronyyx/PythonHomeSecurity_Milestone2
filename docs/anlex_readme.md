# AnLex Guard - Home Security System

A comprehensive Raspberry Pi-based home security system with motion detection, RFID authentication, temperature monitoring, and photo capture capabilities.

## 📋 Table of Contents
- [Hardware Requirements](#hardware-requirements)
- [Pin Wiring Guide](#pin-wiring-guide)
- [Software Installation](#software-installation)
- [Configuration](#configuration)
- [Running the System](#running-the-system)
- [Using the Dashboard](#using-the-dashboard)
- [Troubleshooting](#troubleshooting)

---

## 🔧 Hardware Requirements

### Required Components
- **Raspberry Pi 4/5** (recommended) or Pi 3B+
- **PIR Motion Sensor** (HC-SR501 or similar)
- **DHT11 Temperature/Humidity Sensor**
- **MFRC522 RFID Reader** + RFID Key/Card
- **SG90 Servo Motor** (for latch mechanism)
- **LED** (any color, 5mm recommended)
- **Active Buzzer** (5V)
- **USB Webcam** (any UVC-compatible camera)
- **Breadboard and Jumper Wires**
- **Resistors**: 220Ω (for LED), 1kΩ (for buzzer, optional)

### Optional
- External 5V power supply for servo (recommended for stability)
- Capacitor 100µF for servo power smoothing

---

## 📌 Pin Wiring Guide

### GPIO Pin Assignments

| Component | GPIO Pin | Physical Pin | Wire Color (Suggested) |
|-----------|----------|--------------|------------------------|
| **DHT11 Sensor** |
| DHT11 Data | GPIO 4 | Pin 7 | Yellow |
| DHT11 VCC | 3.3V | Pin 1 | Red |
| DHT11 GND | Ground | Pin 6 | Black |
| **PIR Motion Sensor** |
| PIR Data | GPIO 17 | Pin 11 | Orange |
| PIR VCC | 5V | Pin 2 | Red |
| PIR GND | Ground | Pin 14 | Black |
| **LED Indicator** |
| LED Anode (+) | GPIO 27 | Pin 13 | Green |
| LED Cathode (-) | Ground | Pin 9 | Black (via 220Ω resistor) |
| **Buzzer** |
| Buzzer (+) | GPIO 13 | Pin 33 | Blue |
| Buzzer (-) | Ground | Pin 34 | Black |
| **Servo Motor** |
| Servo Signal | GPIO 18 | Pin 12 | White/Orange |
| Servo VCC | 5V | Pin 4 | Red (external power recommended) |
| Servo GND | Ground | Pin 6 | Brown/Black |
| **RFID Reader (SPI)** |
| SDA (SS) | GPIO 8 | Pin 24 | Purple |
| SCK | GPIO 11 | Pin 23 | Blue |
| MOSI | GPIO 10 | Pin 19 | Green |
| MISO | GPIO 9 | Pin 21 | Yellow |
| RST | GPIO 25 | Pin 22 | White |
| VCC | 3.3V | Pin 17 | Red |
| GND | Ground | Pin 20 | Black |
| **USB Camera** |
| Connect to any USB port on Raspberry Pi |

### Wiring Diagram (Text-based)

```
Raspberry Pi GPIO Layout (Pins 1-40)
=====================================

    3.3V [ 1] [ 2] 5V      ← DHT11 VCC (Pin 1), PIR VCC / Servo VCC (Pin 2/4)
   GPIO2 [ 3] [ 4] 5V
   GPIO3 [ 5] [ 6] GND     ← DHT11 GND, Servo GND
   GPIO4 [ 7] [ 8] GPIO14  ← DHT11 Data (Pin 7)
     GND [ 9] [10] GPIO15  ← LED GND (via resistor)
  GPIO17 [11] [12] GPIO18  ← PIR Data (Pin 11), Servo Signal (Pin 12)
  GPIO27 [13] [14] GND     ← LED Signal (Pin 13), PIR GND
  GPIO22 [15] [16] GPIO23
    3.3V [17] [18] GPIO24  ← RFID VCC
  GPIO10 [19] [20] GND     ← RFID MOSI, RFID GND
   GPIO9 [21] [22] GPIO25  ← RFID MISO, RFID RST
  GPIO11 [23] [24] GPIO8   ← RFID SCK, RFID SDA
     GND [25] [26] GPIO7
   GPIO0 [27] [28] GPIO1
   GPIO5 [29] [30] GND
   GPIO6 [31] [32] GPIO12
  GPIO13 [33] [34] GND     ← Buzzer (+) Pin 33, Buzzer (-) Pin 34
  GPIO19 [35] [36] GPIO16
  GPIO26 [37] [38] GPIO20
     GND [39] [40] GPIO21
```

### Important Wiring Notes

⚠️ **Critical Points:**
- **DHT11**: Use 3.3V (not 5V) to avoid damaging the Pi
- **Servo**: Consider external 5V power supply if experiencing brownouts
- **LED**: Always use a 220Ω resistor to limit current
- **RFID**: Enable SPI in `raspi-config` before use
- **All grounds must be connected together** (common ground)

---

## 💾 Software Installation

### 1. Prepare Raspberry Pi

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-dev python3-venv
sudo apt install -y libatlas-base-dev libopenjp2-7 libtiff5
sudo apt install -y libgpiod2 python3-libgpiod

# Enable SPI for RFID
sudo raspi-config
# Navigate to: Interface Options → SPI → Enable
```

### 2. Install Python Dependencies

```bash
# Create project directory
mkdir ~/anlex-guard
cd ~/anlex-guard

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip3 install flask flask-cors
pip3 install opencv-python
pip3 install gpiozero pigpio
pip3 install adafruit-circuitpython-dht
pip3 install paho-mqtt
pip3 install mfrc522
pip3 install RPi.GPIO
pip3 install spidev
```

### 3. Download Project Files

Place these files in `~/anlex-guard/`:
- `app.py` - Flask backend
- `sensors.py` - Sensor interfaces
- `actuators.py` - Actuator controls
- `adafruit_io.py` - Adafruit IO integration
- `rfid_reader.py` - RFID reader wrapper
- `config/config.json` - Configuration file
- `static/index.html` - Web dashboard

---

## ⚙️ Configuration

### 1. Edit `config/config.json`

```json
{
  "pins": {
    "led_bcm": 27,          // GPIO 27 (Pin 13)
    "beeper_bcm": 13,       // GPIO 13 (Pin 33)
    "servo_bcm": 18,        // GPIO 18 (Pin 12)
    "dht_bcm": "D4",        // GPIO 4 (Pin 7)
    "pir_bcm": 17           // GPIO 17 (Pin 11)
  },
  "camera": {
    "device_index": 0,      // Usually 0 for first USB camera
    "width": 1280,          // Camera resolution
    "height": 720
  },
  "logic": {
    "pre_alarm_delay_seconds": 30,    // Warning time before alarm
    "alarm_duration_seconds": 180,     // Max alarm duration
    "motion_timeout_seconds": 60,      // Time after motion stops
    "photo_interval_seconds": 5,       // Photo capture interval
    "pir_debounce_seconds": 1.0        // Motion sensor debounce
  },
  "adafruit_io": {
    "username": "YOUR_AIO_USERNAME",   // Replace with your username
    "key": "YOUR_AIO_KEY",             // Replace with your key
    "feeds": {
      "motion": "sensor.motion",
      "temperature": "sensor.temperature",
      "humidity": "sensor.humidity",
      "mode": "mode",
      "alarm": "alarm",
      "event_log": "events"
    }
  },
  "authorized_rfids": [565967042481]  // Add your RFID card IDs here
}
```

### 2. Get Your RFID Card ID

```bash
# Run this to scan your RFID card and get its ID
cd ~/anlex-guard
python3 << EOF
from mfrc522 import SimpleMFRC522
reader = SimpleMFRC522()
print("Hold your RFID card near the reader...")
id, text = reader.read()
print(f"Your RFID ID is: {id}")
EOF
```

Add this ID to the `authorized_rfids` array in `config.json`.

### 3. Setup Adafruit IO (Optional)

1. Create account at https://io.adafruit.com
2. Get your username and AIO Key from Settings
3. Create feeds with names matching your config
4. Update `config.json` with your credentials

---

## 🚀 Running the System

### Manual Start

```bash
cd ~/anlex-guard

# Activate virtual environment (if using)
source venv/bin/activate

# Run the application (requires sudo for GPIO access)
sudo python3 app.py
```

The system will start on `http://raspberry-pi-ip:5000`

### Auto-Start on Boot (Systemd Service)

1. Create service file:
```bash
sudo nano /etc/systemd/system/anlex-guard.service
```

2. Add this content:
```ini
[Unit]
Description=AnLex Guard Security System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/anlex-guard
ExecStart=/usr/bin/python3 /home/pi/anlex-guard/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and start:
```bash
sudo systemctl enable anlex-guard
sudo systemctl start anlex-guard

# Check status
sudo systemctl status anlex-guard

# View logs
sudo journalctl -u anlex-guard -f
```

### Control Commands

```bash
# Start service
sudo systemctl start anlex-guard

# Stop service
sudo systemctl stop anlex-guard

# Restart service
sudo systemctl restart anlex-guard

# View logs
sudo journalctl -u anlex-guard -n 50

# Disable auto-start
sudo systemctl disable anlex-guard
```

---

## 🖥️ Using the Dashboard

### Access the Dashboard

1. Find your Raspberry Pi's IP address:
```bash
hostname -I
```

2. Open browser and navigate to:
```
http://RASPBERRY_PI_IP:5000
```

### Dashboard Features

#### System Status Card
- View current mode (Disarmed/Armed/Pre-Alarm/Alarm)
- Toggle stealth mode (LED off when armed)
- See pre-alarm delay setting
- Track last activity

#### Camera Card
- View latest captured photo
- Manually capture photos
- Refresh camera view
- Open photo gallery

#### Sensors Card
- Real-time motion sensor status
- Current temperature and humidity
- RFID reader status
- Box lock status

#### Manual Controls Card
- Test LED (3 seconds)
- Test Buzzer (3 seconds)
- Test Servo unlock (3 seconds)
- Test camera capture

#### Event Log Card
- View all system events
- Refresh log
- Clear log history

#### Settings Card
- Pre-alarm delay (10-120 seconds)
- Alarm duration (30-600 seconds)
- Motion timeout (10-300 seconds)
- Photo interval (3-30 seconds)

### System Operation

#### Arming the System
1. Click "Arm System" button, OR
2. Scan authorized RFID card

**What happens:**
- Servo locks the box
- LED gives 3 fast blinks
- LED goes solid (or off if stealth mode enabled)
- System begins monitoring for motion

#### When Motion is Detected
1. **Pre-Alarm Phase (30 seconds default):**
   - LED turns solid
   - Buzzer beeps softly every 2 seconds
   - Camera takes first photo
   - You can disarm to prevent full alarm

2. **Full Alarm (if not disarmed):**
   - Buzzer activates continuously
   - LED flashes rapidly
   - Photos taken every 5 seconds
   - Alarm continues for 1 minute after motion stops

#### Disarming the System
1. Click "Disarm" button, OR
2. Scan authorized RFID card

**What happens:**
- Buzzer stops immediately
- Servo unlocks the box
- LED starts slow blinking
- Photos saved for review

---

## 🔍 Troubleshooting

### Dashboard Won't Load

```bash
# Check if service is running
sudo systemctl status anlex-guard

# Check Flask is listening
sudo netstat -tulpn | grep 5000

# Check logs
sudo journalctl -u anlex-guard -n 100

# Test API directly
curl http://localhost:5000/api/health
```

### Motion Sensor Not Working

```bash
# Test PIR sensor
python3 << EOF
from gpiozero import MotionSensor
pir = MotionSensor(17)
pir.wait_for_motion()
print("Motion detected!")
EOF
```

- Check PIR sensitivity adjustment potentiometer
- Ensure 5V power supply is adequate
- Wait 30 seconds after power-on for PIR to stabilize

### DHT11 Sensor Errors

```bash
# Test DHT11
python3 << EOF
import adafruit_dht
import board
dht = adafruit_dht.DHT11(board.D4)
print(f"Temp: {dht.temperature}C, Humidity: {dht.humidity}%")
dht.exit()
EOF
```

**Common issues:**
- DHT11 can be unreliable - system retries automatically
- Use 3.3V, not 5V
- Keep wires short (< 20cm if possible)
- Add 10kΩ pull-up resistor between data and VCC if needed

### RFID Not Reading

```bash
# Enable SPI
sudo raspi-config
# Interface Options → SPI → Enable

# Test RFID
python3 << EOF
from mfrc522 import SimpleMFRC522
reader = SimpleMFRC522()
print("Scan card...")
id, text = reader.read()
print(f"ID: {id}")
EOF
```

- Check SPI is enabled
- Verify all 7 wires are connected correctly
- Card must be within 2-3cm of reader
- Some cards may not be compatible (use 13.56MHz MIFARE)

### Camera Not Working

```bash
# List USB devices
lsusb

# Test camera
ls /dev/video*

# Capture test image
fswebcam test.jpg

# Check OpenCV
python3 -c "import cv2; print(cv2.__version__)"
```

- Try different USB ports
- Check camera works with `cheese` or `fswebcam`
- Change `device_index` in config.json (try 0, 1, 2)

### Servo Jittering

- Use external 5V power supply (not from Pi)
- Add 100µF capacitor across servo power lines
- Ensure common ground between Pi and external supply
- Code calls `servo.detach()` after movement to stop PWM

### GPIO Permission Issues

```bash
# Add user to gpio group
sudo usermod -a -G gpio pi

# Or run with sudo
sudo python3 app.py
```

### Cannot Connect to Adafruit IO

- Check internet connection
- Verify username and key in config.json
- Check feed names match exactly
- Test at https://io.adafruit.com

---

## 📊 System Specifications

### Performance
- Motion detection: < 1 second response time
- Camera capture: ~2 seconds per photo
- Temperature reading: Every 60 seconds
- Dashboard refresh: Every 3 seconds

### Capacity
- Event log: 1000 entries (automatic rollover)
- Photo storage: Limited by SD card space (~100 photos per GB)
- Concurrent users: 5-10 dashboard connections

### Power Consumption
- Idle (disarmed): ~5W
- Armed (monitoring): ~6W
- Alarm active: ~8W

---

## 📝 Quick Reference

### GPIO Pin Summary
- GPIO 4 (Pin 7): DHT11 Data
- GPIO 17 (Pin 11): PIR Motion Sensor
- GPIO 27 (Pin 13): LED
- GPIO 13 (Pin 33): Buzzer
- GPIO 18 (Pin 12): Servo
- GPIO 8,9,10,11,25 (Pins 19-24): RFID (SPI)

### API Endpoints
- `GET /api/status` - System status
- `POST /api/arm` - Arm system
- `POST /api/disarm` - Disarm system
- `POST /api/stealth` - Toggle stealth
- `GET /api/logs` - Event logs
- `GET /api/images` - Photo list
- `POST /api/actuators/test` - Test components
- `GET/POST /api/settings` - System settings

### Default Timings
- Pre-alarm: 30 seconds
- Alarm duration: 180 seconds
- Motion timeout: 60 seconds
- Photo interval: 5 seconds

---

## 🆘 Support

**Logs location:** `/home/pi/anlex-guard/logs/app.log`

**Photos location:** `/home/pi/anlex-guard/data/images/`

**Check system health:**
```bash
curl http://localhost:5000/api/health
```

**Common commands:**
```bash
# Restart system
sudo systemctl restart anlex-guard

# View live logs
sudo journalctl -u anlex-guard -f

# Stop system temporarily
sudo systemctl stop anlex-guard
```

---

## 📜 License

AnLex Guard - Educational IoT Security System Project

Built for learning purposes with Raspberry Pi, Flask, and modern web technologies.

---

**Made with ❤️ for the AnLex Guard IoT Project**