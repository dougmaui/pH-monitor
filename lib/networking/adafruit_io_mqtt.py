import time
import adafruit_minimqtt.adafruit_minimqtt as MQTT


def connect_to_adafruit_io(wifi_radio, socketpool_obj, username, key):
    try:
        print(f"Connecting to Adafruit IO as user: {username}")
        mqtt_client = MQTT.MQTT(
            broker="io.adafruit.com",
            port=1883,
            username=username,
            password=key,
            socket_pool=socketpool_obj,
        )

        def connect(mqtt_client, userdata, flags, rc):
            print(f"Connected to Adafruit IO with result code {rc}")

        def disconnect(mqtt_client, userdata, rc):
            print(f"Disconnected from Adafruit IO with result code {rc}")

        def publish(mqtt_client, userdata, topic, pid):
            print(f"Published to {topic} with PID {pid}")

        mqtt_client.on_connect = connect
        mqtt_client.on_disconnect = disconnect
        mqtt_client.on_publish = publish

        mqtt_client.connect()
        mqtt_client._username = username
        print("Successfully connected to Adafruit IO MQTT!")
        return mqtt_client
    except Exception as e:
        print(f"Failed to connect to Adafruit IO: {e}")
        return None


def send_data_to_feed(mqtt_client, feed_name, value):
    try:
        value_str = str(value)
        username = mqtt_client._username
        topic = f"{username}/feeds/{feed_name}"
        print(f"Publishing {value_str} to topic: {topic}")
        mqtt_client.publish(topic, value_str)
        mqtt_client.loop()
        return True
    except Exception as e:
        print(f"Error sending data to feed: {e}")
        return False
