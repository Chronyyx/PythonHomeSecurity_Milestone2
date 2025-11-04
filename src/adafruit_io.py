"""
MIT License
Adafruit IO MQTT helper (TLS, QoS 1)
"""
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
        logging.info("Adafruit IO connected rc=%s", rc)
        self._connected = True

    def _on_disconnect(self, client, userdata, rc):
        logging.warning("Adafruit IO disconnected rc=%s", rc)
        self._connected = False

    def connect(self, timeout=10):
        self.client.connect(self.host, self.port, keepalive=60)
        self.client.loop_start()
        import time
        t0 = time.time()
        while not self._connected and (time.time() - t0) < timeout:
            time.sleep(0.1)
        if not self._connected:
            raise TimeoutError("MQTT connect timeout")

    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def _topic(self, feed_key):
        return f"{self.username}/feeds/{feed_key}"

    def publish_number(self, feed_key, value, retain=False, qos=1):
        payload = json.dumps({"value": value})
        info = self.client.publish(self._topic(feed_key), payload=payload, qos=qos, retain=retain)
        return info.wait_for_publish(timeout=5)
