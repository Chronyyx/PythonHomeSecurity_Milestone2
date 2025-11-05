"""
Main loop:
- Publishes ONLY PIR (1/0), DHT11 temp/humidity to Adafruit IO
- Snapshot on motion
- Alarm (LED+Beeper+Relay+Fan) ON while motion, OFF otherwise
"""
import os, json, time, logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from sensors import PirReader, DhtReader, UsbCamera
from actuators import Actuators
from adafruit_io import AdafruitIOClient

def load_config(path="config/config.json"):
    with open(path, "r") as f:
        return json.load(f)

def setup_logging(log_dir="logs"):
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = TimedRotatingFileHandler(filename=os.path.join(log_dir, "app.log"), when="midnight", backupCount=7, utc=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

def main():
    cfg = load_config()
    setup_logging()

    aio_cfg = cfg["adafruit_io"]
    pins = cfg["pins"]
    cam_cfg = cfg["camera"]
    logic = cfg["logic"]

    logging.info("Starting security system")

    pir = PirReader(pins["pir_bcm"], debounce_s=logic["pir_debounce_seconds"])
    dht = DhtReader(pins["dht_bcm"])
    cam = UsbCamera(device_index=cam_cfg["device_index"], width=cam_cfg["width"], height=cam_cfg["height"])
    acts = Actuators(pins["led_bcm"], pins["beeper_bcm"], pins["servo_bcm"])

    client = AdafruitIOClient(
        username=aio_cfg["username"],
        key=aio_cfg["key"],
        host=aio_cfg.get("host", "io.adafruit.com"),
        port=aio_cfg.get("port", 8883),
        use_tls=aio_cfg.get("use_tls", True),
    )
    client.connect()

    feeds = aio_cfg["feeds"]
    read_interval = logic["read_interval_seconds"]
    alarm_secs = logic["motion_alarm_seconds"]

    last_motion_state = None
    try:
        while True:
            motion = pir.read_state()
            if motion != last_motion_state:
                last_motion_state = motion
                client.publish_number(feeds["motion"], int(motion))
                logging.info("Motion state changed => %s", motion)

                if motion == 1:
                    acts.alarm_on()
                    try:
                        cam.snapshot()
                    except Exception as e:
                        logging.exception("Snapshot failed: %s", e)
                    # keep alarm on for the configured burst, then remain on if motion persists
                    time.sleep(alarm_secs)
                else:
                    acts.alarm_off()

            temp_c, hum = dht.read()
            if temp_c is not None and hum is not None:
                client.publish_number(feeds["temperature"], float(temp_c))
                client.publish_number(feeds["humidity"], float(hum))
                logging.info("DHT11 T=%.1fC H=%.1f%%", temp_c, hum)

            time.sleep(read_interval)

    except KeyboardInterrupt:
        logging.info("Exiting on keyboard interrupt")
    except Exception as e:
        logging.exception("Fatal error: %s", e)
    finally:
        acts.shutdown()
        cam.close()
        client.disconnect()

if __name__ == "__main__":
    main()
