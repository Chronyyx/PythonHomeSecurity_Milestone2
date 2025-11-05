# Raspberry Pi Security System (PIR + DHT11 + USB Camera) — Adafruit IO

This repo publishes **only** the required feeds to Adafruit IO:
- `motion` → 0 or 1 (PIR)
- `temperature` → °C
- `humidity` → %

## Layout

```
security-system-adafruitio-v2/
├─ src/
│  ├─ main.py
│  ├─ sensors.py
│  ├─ actuators.py
│  └─ adafruit_io.py
├─ config/
│  └─ config.json
├─ docs/
│  └─ wiring.md
├─ data/
│  └─ images/
├─ logs/
├─ systemd/
│  └─ security_system.service
├─ requirements.txt
├─ .gitignore
└─ README.md
```

## Quick start

```bash
sudo apt update
sudo apt install -y python3-venv python3-opencv fswebcam libgpiod2
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# set Adafruit IO creds in config/config.json
python src/main.py
```


Install once on Raspberry Pi OS:
```bash
sudo apt update
sudo apt install -y libgpiod2
python3 -m pip install adafruit-circuitpython-dht
```

Pins are mapped by BCM number (e.g., 4, 17, 22, 27) in `src/sensors.py`. If you use a different BCM pin, add it to the mapping.

feeds:

- [Humidity](https://io.adafruit.com/chronyx/feeds/humidity)
- [Temperature](https://io.adafruit.com/chronyx/feeds/temperature)
- [Motion](https://io.adafruit.com/chronyx/feeds/motion)

[Youtube Demo](https://youtu.be/8iTue2UWGeI)
