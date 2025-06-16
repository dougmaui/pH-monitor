# Adafruit IO integration using MQTT
import time
import adafruit_minimqtt.adafruit_minimqtt as MQTT

def connect_to_adafruit_io(wifi_radio, socketpool_obj, username, key):
    """
    Connect to Adafruit IO using MQTT
    
    Args:
        wifi_radio: wifi.radio object
        socketpool_obj: socketpool object
        username: Adafruit IO username
        key: Adafruit IO key
        
    Returns:
        MQTT client if successful, None otherwise
    """
    try:
        print(f"Connecting to Adafruit IO as user: {username}")
        
        # Create a socket pool
        pool = socketpool_obj
        
        # Set up a MiniMQTT Client directly (not using IO_MQTT wrapper)
        mqtt_client = MQTT.MQTT(
            broker="io.adafruit.com",
            port=1883,
            username=username,
            password=key,
            socket_pool=pool
        )
        
        # Define callback functions
        def connect(mqtt_client, userdata, flags, rc):
            print(f"Connected to Adafruit IO with result code {rc}")
        
        def disconnect(mqtt_client, userdata, rc):
            print(f"Disconnected from Adafruit IO with result code {rc}")
        
        def publish(mqtt_client, userdata, topic, pid):
            print(f"Published to {topic} with PID {pid}")
        
        # Set up callbacks
        mqtt_client.on_connect = connect
        mqtt_client.on_disconnect = disconnect
        mqtt_client.on_publish = publish
        
        # Connect to Adafruit IO MQTT broker
        print("Attempting to connect to Adafruit IO MQTT broker...")
        mqtt_client.connect()
        
        # Store username as attribute for easier topic creation
        mqtt_client._username = username
        
        print("Successfully connected to Adafruit IO MQTT!")
        return mqtt_client
    except Exception as e:
        print(f"Failed to connect to Adafruit IO: {e}")
        return None

def send_data_to_feed(mqtt_client, feed_name, value):
    """
    Send data to an Adafruit IO feed using MQTT
    
    Args:
        mqtt_client: MQTT client object
        feed_name: Name of the feed
        value: Value to send
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Format the value as a string
        if isinstance(value, float):
            value_str = f"{value:.3f}"  # Use 3 decimal places for pH values
        else:
            value_str = str(value)
        
        # Format the topic according to Adafruit IO requirements
        # The format should be: username/feeds/feedname
        username = mqtt_client._username
        topic = f"{username}/feeds/{feed_name}"
        
        print(f"Publishing {value_str} to topic: {topic}")
        
        # Publish the data
        mqtt_client.publish(topic, value_str)
        mqtt_client.loop()  # Process network traffic
        
        return True
    except Exception as e:
        print(f"Error sending data to feed: {e}")
        return False# Adafruit IO integration using MQTT
import time
import socketpool
import adafruit_minimqtt.adafruit_minimqtt as MQTT

def connect_to_adafruit_io(wifi_radio, socketpool_obj, username, key):
    """
    Connect to Adafruit IO using MQTT
    
    Args:
        wifi_radio: wifi.radio object
        socketpool_obj: socketpool object
        username: Adafruit IO username
        key: Adafruit IO key
        
    Returns:
        MQTT client if successful, None otherwise
    """
    try:
        print(f"Connecting to Adafruit IO as user: {username}")
        
        # Create a socket pool
        pool = socketpool_obj
        
        # Set up a MiniMQTT Client directly (not using IO_MQTT wrapper)
        mqtt_client = MQTT.MQTT(
            broker="io.adafruit.com",
            port=1883,
            username=username,
            password=key,
            socket_pool=pool
        )
        
        # Define callback functions
        def connect(mqtt_client, userdata, flags, rc):
            print(f"Connected to Adafruit IO with result code {rc}")
        
        def disconnect(mqtt_client, userdata, rc):
            print(f"Disconnected from Adafruit IO with result code {rc}")
        
        def publish(mqtt_client, userdata, topic, pid):
            print(f"Published to {topic} with PID {pid}")
        
        # Set up callbacks
        mqtt_client.on_connect = connect
        mqtt_client.on_disconnect = disconnect
        mqtt_client.on_publish = publish
        
        # Connect to Adafruit IO MQTT broker
        print("Attempting to connect to Adafruit IO MQTT broker...")
        mqtt_client.connect()
        
        # Store username as attribute for easier topic creation
        mqtt_client._username = username
        
        print("Successfully connected to Adafruit IO MQTT!")
        return mqtt_client
    except Exception as e:
        print(f"Failed to connect to Adafruit IO: {e}")
        return None

def send_data_to_feed(mqtt_client, feed_name, value):
    """
    Send data to an Adafruit IO feed using MQTT
    
    Args:
        mqtt_client: MQTT client object
        feed_name: Name of the feed
        value: Value to send
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Format the value as a string
        value_str = f"{value:.3f}"
        
        # Format the topic according to Adafruit IO requirements
        # The format should be: username/feeds/feedname
        username = mqtt_client._username
        topic = f"{username}/feeds/{feed_name}"
        
        print(f"Publishing {value_str} to topic: {topic}")
        
        # Publish the data
        mqtt_client.publish(topic, value_str)
        mqtt_client.loop()  # Process network traffic
        
        return True
    except Exception as e:
        print(f"Error sending data to feed: {e}")
        return False
