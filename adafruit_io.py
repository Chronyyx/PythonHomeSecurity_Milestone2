import ssl, time, json, logging
import paho.mqtt.client as mqtt

class AdafruitIOClient:
    def __init__(self, username, key, host="io.adafruit.com", port=8883, use_tls=True):
        self.username = username
        self.key = key
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.client = mqtt.Client(client_id=f"pi-sec-{int(time.time())}", clean_session=True, protocol=mqtt.MQTTv311)
        self.client.username_pw_set(self.username, self.key)
        if self.use_tls:
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            self.client.tls_insecure_set(False)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._connected = False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Adafruit IO connected")
            self._connected = True
        else:
            logging.error(f"Adafruit IO connection failed, rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        logging.warning(f"Adafruit IO disconnected rc={rc}")
        self._connected = False

    def connect_non_blocking(self):
        try:
            self.client.connect_async(self.host, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logging.error(f"Failed to initiate MQTT connection: {e}")

    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def _topic(self, feed_key):
        return f"{self.username}/feeds/{feed_key}"

    def publish(self, feed_key, value):
        if not self._connected:
            return # Fail silently if offline
        try:
            payload = json.dumps({"value": value})
            self.client.publish(self._topic(feed_key), payload=payload, qos=1)
        except Exception as e:
            logging.error(f"MQTT publish error: {e}")