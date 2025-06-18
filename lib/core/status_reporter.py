# lib/core/status_reporter.py
"""
Status Reporter Module
Handles detailed system status reporting with measurement statistics
Extracted from main code.py for better organization
"""
import time


def run_detailed_status_report(
    main_loop_iterations,
    state_manager,
    wifi_manager,
    time_manager,
    mqtt_manager,
    i2c_safe,
    rtd_sensor,
    watchdog_enabled,
    wdt,
    last_neopixel_status,
    measurement_manager,
):
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
    print(
        f"   Time: Valid={time_status['time_valid']}, Current={time_status['current_time']}"
    )

    # MQTT status
    mqtt_status = mqtt_manager.get_status()
    print(
        f"   MQTT: Connected={mqtt_status['connected']}, Sent={mqtt_status['messages_sent']}, Queued={mqtt_status['messages_queued']}"
    )

    # I2C safety status
    i2c_stats = i2c_safe.get_stats()
    print(f"   I2C Safety: {i2c_stats['success_rate']}% success rate")
    print(
        f"   I2C Operations: {i2c_stats['total_operations']} total, {i2c_stats['timeouts']} timeouts, {i2c_stats['resets']} resets"
    )

    # Measurement manager status
    if measurement_manager:
        try:
            measurement_stats = measurement_manager.get_statistics()
            print(f"   Measurement Manager:")
            print(
                f"     Robust measurements: {'Enabled' if measurement_stats['enabled'] else 'Disabled'}"
            )
            print(
                f"     Temperature readings: {measurement_stats['temp_readings']} total"
            )
            print(
                f"     Temperature robust success: {measurement_stats['temp_robust_success_rate']}%"
            )
            print(f"     pH readings: {measurement_stats['ph_readings']} total")
            print(
                f"     pH robust success: {measurement_stats['ph_robust_success_rate']}%"
            )
            print(
                f"     Sample config: T={measurement_stats['temp_sample_count']}, pH={measurement_stats['ph_sample_count']}, delay={measurement_stats['sample_delay']}s"
            )

            # Show noise reduction if available
            if "temp_noise_reduction" in measurement_stats:
                print(
                    f"     Temperature noise reduction: {measurement_stats['temp_noise_reduction']:.4f}°C avg"
                )
            if "ph_noise_reduction" in measurement_stats:
                print(
                    f"     pH noise reduction: {measurement_stats['ph_noise_reduction']:.4f} pH avg"
                )

        except Exception as e:
            print(f"   Measurement Manager: Error getting stats - {e}")
    else:
        print(f"   Measurement Manager: Not initialized")

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

    # Recent readings with quality metrics
    if state_manager.readings:
        print("   Recent Readings:")
        for sensor, reading in state_manager.readings.items():
            age = time.monotonic() - reading["time"]
            value = reading["value"]

            # Add quality indicators for measurements
            if sensor == "temperature" and measurement_manager:
                try:
                    temp_std_dev = state_manager.get_reading("temp_std_dev")
                    if temp_std_dev:
                        print(
                            f"     {sensor}: {value} (±{temp_std_dev:.3f}°C, age: {age:.0f}s)"
                        )
                    else:
                        print(f"     {sensor}: {value} (age: {age:.0f}s)")
                except:
                    print(f"     {sensor}: {value} (age: {age:.0f}s)")
            elif sensor == "ph" and measurement_manager:
                try:
                    ph_std_dev = state_manager.get_reading("ph_std_dev")
                    if ph_std_dev:
                        print(
                            f"     {sensor}: {value} (±{ph_std_dev:.3f} pH, age: {age:.0f}s)"
                        )
                    else:
                        print(f"     {sensor}: {value} (age: {age:.0f}s)")
                except:
                    print(f"     {sensor}: {value} (age: {age:.0f}s)")
            else:
                print(f"     {sensor}: {value} (age: {age:.0f}s)")

    print("=" * 60)
