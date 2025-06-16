# lib/core/status_reporter.py
"""
System Status Reporting Module
Handles detailed system status reports and monitoring
Extracted from main code.py for better organization
"""
import time


def run_detailed_status_report(main_loop_iterations, state_manager, wifi_manager, 
                              time_manager, mqtt_manager, i2c_safe, rtd_sensor, 
                              watchdog_enabled, wdt, last_neopixel_status):
    """Run the detailed system status report (every minute)"""
    print(f"\n🔍 DETAILED SYSTEM REPORT (Cycle #{main_loop_iterations}):")

    # System status
    status = state_manager.get_status()
    print(f"   System State: {status['state']}")
    print(f"   Component Health: {status['components']}")

    # Enhanced WiFi status
    wifi_status = wifi_manager.get_status()
    print(f"   WiFi Status:")
    print(f"     Connected: {wifi_status['connected']}")
    print(f"     Success Rate: {wifi_status['success_rate']}%")
    print(f"     Current RSSI: {wifi_status.get('rssi', 'Unknown')} dBm")

    if "rssi" in wifi_status and wifi_status["rssi"]:
        rssi_val = wifi_status["rssi"]
        if rssi_val >= -50:
            rssi_status = "Excellent"
        elif rssi_val >= -60:
            rssi_status = "Good"
        elif rssi_val >= -70:
            rssi_status = "Fair"
        else:
            rssi_status = "Poor - May cause disconnections"
        print(f"     Signal Quality: {rssi_status}")

    # Time status
    time_status = time_manager.get_status()
    print(f"   Time: Valid={time_status['time_valid']}, Current={time_status['current_time']}")

    # MQTT status
    mqtt_status = mqtt_manager.get_status()
    print(f"   MQTT: Connected={mqtt_status['connected']}, Sent={mqtt_status['messages_sent']}, Queued={mqtt_status['messages_queued']}")

    # I2C safety status
    i2c_stats = i2c_safe.get_stats()
    print(f"   I2C Safety: {i2c_stats['success_rate']}% success rate")
    print(f"   I2C Operations: {i2c_stats['total_operations']} total, {i2c_stats['timeouts']} timeouts, {i2c_stats['resets']} resets")

    # NeoPixel status
    print(f"   NeoPixel Status: {last_neopixel_status}")

    # RTD status
    if rtd_sensor:
        try:
            rtd_status = rtd_sensor.get_status()
            print(f"   RTD Status: {rtd_status}")
        except Exception as e:
            print(f"   RTD Status: Error getting status - {e}")
    else:
        print(f"   RTD Status: Not initialized")

    # Watchdog status
    if watchdog_enabled:
        print(f"   Watchdog: Active, timeout={wdt.timeout}s")
    else:
        print(f"   Watchdog: Disabled")

    # Recent readings
    if state_manager.readings:
        print("   Recent Readings:")
        for sensor, reading in state_manager.readings.items():
            age = time.monotonic() - reading["time"]
            print(f"     {sensor}: {reading['value']} (age: {age:.0f}s)")

    print("=" * 60)