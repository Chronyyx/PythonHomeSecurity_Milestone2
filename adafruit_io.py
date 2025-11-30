import ssl, time, json, logging
import paho.mqtt.client as mqtt
import requests
from datetime import datetime

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
        except Exception as e:
            logging.error(f"Error while disconnecting from MQTT: {e}")

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

    def get_data(self, feed_key, start_time=None, end_time=None, limit=1000):
        """
        Fetch historical data from Adafruit IO using REST API.
        
        Args:
            feed_key: The feed key to fetch data from
            start_time: ISO format datetime string or datetime object (optional)
            end_time: ISO format datetime string or datetime object (optional)
            limit: Maximum number of data points to return (default 1000, max 1000)
        
        Returns:
            List of data points with 'value' and 'created_at' fields
        """
        try:
            # Build API URL
            url = f"https://io.adafruit.com/api/v2/{self.username}/feeds/{feed_key}/data"
            
            # Build query parameters
            params = {'limit': min(limit, 1000)}  # Adafruit IO max is 1000
            
            if start_time:
                if isinstance(start_time, datetime):
                    start_time = start_time.isoformat()
                params['start_time'] = start_time
                
            if end_time:
                if isinstance(end_time, datetime):
                    end_time = end_time.isoformat()
                params['end_time'] = end_time
            
            # Make request with authentication
            headers = {'X-AIO-Key': self.key}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logging.info(f"Retrieved {len(data)} data points from {feed_key}")
                return data
            else:
                logging.error(f"Adafruit IO API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logging.error(f"Failed to fetch data from Adafruit IO: {e}")
            return []
