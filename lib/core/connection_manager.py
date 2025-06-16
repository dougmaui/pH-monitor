# lib/core/connection_manager.py
"""
Connection and Startup Manager
Handles WiFi connection, time sync, MQTT initialization, and startup tests
Extracted from main code.py for better organization
"""
import wifi
from lib.core.neopixel_status import print_neopixel_legend, neopixel_diagnostic_test


def connect_and_initialize_services(wifi_manager, time_manager, mqtt_manager, 
                                   ph_sensor, safe_read_ph, watchdog_enabled, wdt,
                                   safe_read_temperature, pixel):
    """Connect WiFi, sync time, connect MQTT, and run initial tests"""
    
    # Connect Wi-Fi
    print("Connecting to WiFi with robust manager...")
    if wifi_manager.connect():
        print(f"✅ WiFi connected: {wifi.radio.ipv4_address}")
    else:
        print("⚠️ WiFi connection failed - continuing in degraded mode")

    if watchdog_enabled:
        wdt.feed()

    # Initialize Time Sync
    if time_manager.initialize():
        print("✅ Time manager initialized")
    else:
        print("⚠️ Time manager initialization failed - will retry automatically")

    # Connect MQTT
    if mqtt_manager.initialize():
        print("✅ MQTT manager initialized")
    else:
        print("⚠️ MQTT initialization failed - will retry automatically")

    if watchdog_enabled:
        wdt.feed()

    # Initialize NeoPixel Status Monitoring
    print_neopixel_legend()
    print("🚀 Simple NeoPixel status monitoring active!")

    # Run startup diagnostic test
    print("🎨 Running NeoPixel startup diagnostic...")
    neopixel_diagnostic_test(pixel, watchdog_enabled, wdt)

    print("\n✅ Robust system initialized!")
    try:
        device_info = ph_sensor.get_info()
        print("Device info:", device_info)
    except Exception as e:
        print(f"⚠️ pH sensor info error: {e}")
        device_info = "pH sensor offline"

    # Quick sensor test
    print("🔍 Quick sensor test with I2C safety...")
    try:
        # Test temperature reading with RTD priority
        temp_c, temp_source = safe_read_temperature()
        temp_f = temp_c * 9 / 5 + 32
        print(f"   Temperature: {temp_c:.1f}°C / {temp_f:.1f}°F ({temp_source})")

        # Test pH reading with safety wrapper
        try:
            ph_test = safe_read_ph()
            print(f"   pH: {ph_test}")
        except Exception as e:
            print(f"   pH: sensor error - {e}")

        print(f"   Time: {time_manager.get_local_datetime_string()}")
        print(f"   Uptime: {time_manager.get_uptime_string()}")

    except Exception as e:
        print(f"   Sensor test error: {e}")

    if watchdog_enabled:
        wdt.feed()

    return True