# lib/networking/robust_mqtt.py
"""
Robust MQTT Manager for ESP32-S3
Handles connections, queuing, reconnections, and data publishing
Memory optimized for CircuitPython
ULTRA-MINIMAL: Error 32 detection only, no emergency publishing
"""
import time
import wifi
from lib.networking.adafruit_io_mqtt import connect_to_adafruit_io, send_data_to_feed
import os

# Import feed names from settings.toml
FEED_PH = os.getenv("FEED_PH", "pH2-1")
FEED_TEMPERATURE = os.getenv("FEED_TEMPERATURE", "pH2Temp-2")
FEED_RSSI = os.getenv("FEED_RSSI", "pH2RSSI-1")


class MQTTManager:
    """
    Robust MQTT manager with automatic reconnection and data queuing
    Integrates with state manager and WiFi manager
    """

    def __init__(self, state_manager, wifi_manager, username, key):
        self.state_manager = state_manager
        self.wifi_manager = wifi_manager
        self.username = username
        self.key = key

        # MQTT client state
        self.client = None
        self.last_connection_attempt = 0
        self.connection_attempts = 0
        self.successful_connections = 0
        self.consecutive_failures = 0

        # Data queuing (keep small for memory constraints)
        self.message_queue = []
        self.max_queue_size = 10  # Keep queue small for ESP32-S3
        self.last_send_attempt = 0

        # FIXED: Faster timing settings for better responsiveness
        self.reconnect_interval = 5  # CHANGED: Try reconnect every 5 seconds (was 30)
        self.send_interval = 0.5  # CHANGED: Faster sending (was 1)
        self.connection_timeout = 15  # Connection timeout

        # Statistics
        self.messages_sent = 0
        self.messages_queued = 0
        self.messages_dropped = 0

        # ULTRA-MINIMAL ADDITION: Simple Error 32 counter only
        self.error_32_count = 0

        # Register with state manager
        state_manager.register_component("mqtt")

    def initialize(self):
        """Initialize MQTT connection with immediate attempt"""
        if not self.wifi_manager.is_connected():
            self.state_manager.update_component_health(
                "mqtt", "degraded", "No WiFi connection"
            )
            return False

        # FIXED: Force immediate connection attempt
        print("🔗 Attempting immediate MQTT connection...")
        self.last_connection_attempt = 0  # Reset to allow immediate attempt
        return self._attempt_connection()

    def _attempt_connection(self):
        """Attempt to connect to MQTT broker"""
        current_time = time.monotonic()

        # FIXED: Allow immediate attempt on first connection or after interval
        if (
            self.connection_attempts > 0
            and (current_time - self.last_connection_attempt) < self.reconnect_interval
        ):
            return False

        self.last_connection_attempt = current_time
        self.connection_attempts += 1

        try:
            print(f"🔗 MQTT connection attempt #{self.connection_attempts}")
            socket_pool = self.wifi_manager.get_socket_pool()
            if not socket_pool:
                raise Exception("No socket pool available")

            print(f"  Using socket pool: {socket_pool}")
            print(f"  WiFi radio: {wifi.radio}")
            print(f"  Username: {self.username}")

            # Connect to Adafruit IO
            self.client = connect_to_adafruit_io(
                wifi.radio, socket_pool, self.username, self.key
            )

            if self.client and self.client.is_connected():
                self.successful_connections += 1
                self.consecutive_failures = 0
                print(
                    f"✅ MQTT connected successfully (#{self.successful_connections})"
                )
                self.state_manager.update_component_health("mqtt", "healthy")

                # Process any queued messages immediately
                self._process_queue()
                return True
            else:
                raise Exception("Connection returned None or not connected")

        except Exception as e:
            self.consecutive_failures += 1
            error_msg = f"Connection failed: {e}"
            print(f"❌ MQTT connection failed: {error_msg}")
            print(f"  Error type: {type(e)}")
            print(f"  WiFi connected: {self.wifi_manager.is_connected()}")
            print(
                f"  Socket pool available: {self.wifi_manager.get_socket_pool() is not None}"
            )
            print(f"  Consecutive failures: {self.consecutive_failures}")

            # Determine health status based on failure count
            if self.consecutive_failures > 5:
                health = "failed"
            else:
                health = "degraded"

            self.state_manager.update_component_health("mqtt", health, error_msg)
            self.client = None
            return False

    def is_connected(self):
        """Check if MQTT is connected and healthy"""
        if not self.client:
            return False
        try:
            return self.client.is_connected()
        except:
            return False

    def send_reading(self, feed_name, value):
        """Send a single reading to MQTT feed"""
        message = {"feed": feed_name, "value": value, "timestamp": time.monotonic()}

        if self._send_message(message):
            return True
        else:
            # Queue message if send failed
            self._queue_message(message)
            return False

    def send_readings(self, readings_dict):
        """Send multiple readings at once"""
        current_time = time.monotonic()
        success_count = 0

        for feed_name, value in readings_dict.items():
            if value is not None:  # Only send valid readings
                message = {"feed": feed_name, "value": value, "timestamp": current_time}

                if self._send_message(message):
                    success_count += 1
                else:
                    self._queue_message(message)

        return success_count

    def send_system_status(self, system_status):
        """Send system status information"""
        status_readings = {
            "system-state": system_status.get("state", "UNKNOWN"),
        }
        return self.send_readings(status_readings)

    def _send_message(self, message):
        """Attempt to send a single message with ultra-minimal Error 32 detection"""
        current_time = time.monotonic()

        # Rate limiting (more permissive)
        if (current_time - self.last_send_attempt) < self.send_interval:
            return False

        self.last_send_attempt = current_time

        # Check connection status
        if not self.is_connected():
            return False  # Don't attempt reconnection here, let update() handle it

        try:
            # Send using existing function
            send_data_to_feed(self.client, message["feed"], message["value"])
            self.messages_sent += 1

            # Update health status on successful send
            self.state_manager.update_component_health("mqtt", "healthy")
            return True

        except Exception as e:
            error_str = str(e)

            # ULTRA-MINIMAL: Just detect Error 32 and report to WiFi manager
            if "32" in error_str:
                self.error_32_count += 1
                print(f"🚨 MQTT Error 32 detected (count: {self.error_32_count})")

                # Report to WiFi manager for correlation analysis
                if hasattr(self.wifi_manager, "report_mqtt_error"):
                    self.wifi_manager.report_mqtt_error("error_32")

            print(f"❌ MQTT send error: {e}")
            # Mark client as disconnected on send failure
            self.client = None
            self.state_manager.update_component_health(
                "mqtt", "degraded", f"Send failed: {e}"
            )
            return False

    def _queue_message(self, message):
        """Add message to queue for later sending"""
        # Remove oldest messages if queue is full
        while len(self.message_queue) >= self.max_queue_size:
            dropped = self.message_queue.pop(0)
            self.messages_dropped += 1
            print(f"⚠️ MQTT queue full - dropped {dropped['feed']}")

        self.message_queue.append(message)
        self.messages_queued += 1
        print(
            f"📦 MQTT message queued: {message['feed']} (queue: {len(self.message_queue)})"
        )

    def _process_queue(self):
        """Process queued messages when connection is restored"""
        if not self.message_queue:
            return

        print(f"📤 Processing {len(self.message_queue)} queued MQTT messages...")

        # Process messages in FIFO order
        messages_to_remove = []
        processed_count = 0

        for i, message in enumerate(self.message_queue):
            # Check message age (don't send very old data)
            age = time.monotonic() - message["timestamp"]
            if age > 300:  # 5 minutes old
                messages_to_remove.append(i)
                print(f"⏰ Dropping old message: {message['feed']} (age: {age:.0f}s)")
                continue

            # Try to send the message
            try:
                send_data_to_feed(self.client, message["feed"], message["value"])
                messages_to_remove.append(i)
                processed_count += 1
                self.messages_sent += 1

                # Small delay between sends to avoid overwhelming
                time.sleep(0.1)

            except Exception as e:
                print(f"❌ Queue processing failed at message {i}: {e}")
                # Stop processing on first failure
                break

        # Remove successfully sent messages (in reverse order to maintain indices)
        for i in reversed(messages_to_remove):
            self.message_queue.pop(i)

        if processed_count > 0:
            print(f"✅ Successfully sent {processed_count} queued messages")

        if len(self.message_queue) > 0:
            print(f"📦 {len(self.message_queue)} messages remain in queue")

    def update(self):
        """Update MQTT manager - call this in main loop"""
        current_time = time.monotonic()

        # Attempt connection if not connected and WiFi is available
        if not self.is_connected() and self.wifi_manager.is_connected():
            if (current_time - self.last_connection_attempt) >= self.reconnect_interval:
                print(
                    f"🔄 MQTT auto-reconnect attempt (last attempt {current_time - self.last_connection_attempt:.1f}s ago)"
                )
                self._attempt_connection()

        # Process queue if connected and has messages
        if self.is_connected() and self.message_queue:
            self._process_queue()

    def get_status(self):
        """Get comprehensive MQTT status"""
        queue_age = 0
        if self.message_queue:
            oldest_message = min(self.message_queue, key=lambda m: m["timestamp"])
            queue_age = time.monotonic() - oldest_message["timestamp"]

        success_rate = 0
        if self.connection_attempts > 0:
            success_rate = round(
                (self.successful_connections / self.connection_attempts) * 100, 1
            )

        return {
            "connected": self.is_connected(),
            "connection_attempts": self.connection_attempts,
            "successful_connections": self.successful_connections,
            "consecutive_failures": self.consecutive_failures,
            "success_rate": success_rate,
            "messages_sent": self.messages_sent,
            "messages_queued": len(self.message_queue),
            "messages_dropped": self.messages_dropped,
            "queue_age": queue_age,
            "last_attempt": time.monotonic() - self.last_connection_attempt,
            "next_attempt_in": max(
                0,
                self.reconnect_interval
                - (time.monotonic() - self.last_connection_attempt),
            ),
            "error_32_count": self.error_32_count,  # ULTRA-MINIMAL ADDITION
        }

    def disconnect(self):
        """Clean disconnect from MQTT"""
        try:
            if self.client:
                self.client.disconnect()
                print("📴 MQTT disconnected")
        except Exception as e:
            print(f"MQTT disconnect error: {e}")
        finally:
            self.client = None

    def reset(self):
        """Reset MQTT manager"""
        print("🔄 Resetting MQTT manager...")
        self.disconnect()
        self.consecutive_failures = 0
        self.message_queue.clear()
        self.last_connection_attempt = 0
        print("✅ MQTT manager reset complete")

    def force_reconnect(self):
        """Force an immediate reconnection attempt"""
        print("🔄 Forcing MQTT reconnection...")
        self.disconnect()
        self.last_connection_attempt = 0
        return self._attempt_connection()


# Convenience functions for common operations
class MQTTDataFormatter:
    """Helper class to format sensor data for MQTT transmission"""

    @staticmethod
    def format_sensor_readings(temp_c=None, temp_f=None, ph=None, rssi=None):
        """Format sensor readings for MQTT"""
        readings = {}

        if isinstance(temp_c, (int, float)):
            readings["temp"] = round(temp_c, 2)

        if isinstance(temp_f, (int, float)):
            readings[FEED_TEMPERATURE] = round(temp_f, 2)

        if isinstance(ph, (int, float)):
            readings[FEED_PH] = round(ph, 3)

        if isinstance(rssi, (int, float)):
            readings[FEED_RSSI] = int(rssi)

        return readings

    @staticmethod
    def format_system_status(state_manager):
        """Format system status for MQTT"""
        status = state_manager.get_status()
        return {
            "system-state": status.get("state", "UNKNOWN"),
            "component-count-ok": sum(
                1 for h in status.get("components", {}).values() if h == "OK"
            ),
            "alert-count": status.get("alerts", 0),
        }
