# lib/core/sensor_cycle.py
"""
Sensor Cycle Module
Handles main sensor reading cycle with robust measurements
Extracted from main code.py for better organization
"""


def run_sensor_cycle(
    state_manager,
    time_manager,
    wifi_manager,
    mqtt_manager,
    ph_sensor,
    safe_read_ph,
    pixel,
    display,
    ph_label,
    temp_c_label,
    temp_f_label,
    rssi_label,
    time_label,
    main_loop_iterations,
    safe_read_temperature,
    nominal_temp_c,
    nominal_temp_f,
    measurement_manager,
):
    """Run the main sensor reading and reporting cycle with robust measurements"""

    # Feed watchdog
    state_manager.feed_watchdog()

    # Initialize variables to avoid scoping issues
    temp_source = "unknown"
    ph_source = "unknown"

    # === Enhanced Temperature reading with robust measurements ===
    try:
        if measurement_manager:
            # Use measurement manager for robust temperature reading
            temp_c, temp_source, temp_quality = measurement_manager.read_temperature()
            temp_f = temp_c * 9 / 5 + 32

            # Add quality info to logs
            if temp_source == "robust" and "std_dev" in temp_quality:
                print(
                    f"   📊 Temperature quality: ±{temp_quality['std_dev']:.3f}°C confidence"
                )
        else:
            # Fallback to single reading
            temp_c, temp_source = safe_read_temperature()
            temp_f = temp_c * 9 / 5 + 32
            temp_quality = {"method": "single_fallback"}

        # Set pH temperature compensation
        if ph_sensor:
            ph_sensor.set_temp_compensation(temp_c)

        # Update state based on source and quality
        if temp_source.startswith("robust"):
            state_manager.update_component_health("temperature", "healthy")
        elif temp_source == "fallback":
            state_manager.update_component_health(
                "temperature", "failed", "Using fallback temperature"
            )
        else:
            state_manager.update_component_health("temperature", "healthy")

        state_manager.update_reading("temperature", temp_f)

    except Exception as e:
        print(f"   ❌ Temperature system error: {e}")
        temp_c, temp_f = nominal_temp_c, nominal_temp_f
        temp_source = "error"
        state_manager.update_component_health("temperature", "failed", str(e))

    # === Enhanced pH reading with robust measurements ===
    try:
        if measurement_manager:
            # Use measurement manager for robust pH reading
            ph, ph_source, ph_quality = measurement_manager.read_ph()

            # Add quality info to logs
            if ph_source == "robust" and "std_dev" in ph_quality:
                print(f"   📊 pH quality: ±{ph_quality['std_dev']:.3f} pH confidence")
        else:
            # Fallback to single reading
            ph = safe_read_ph()
            ph_source = "single_fallback"
            ph_quality = {"method": "single_fallback"}

        if ph is not None and isinstance(ph, (int, float)):
            if ph_source.startswith("robust"):
                state_manager.update_component_health("ph", "healthy")
            else:
                state_manager.update_component_health("ph", "healthy")
            state_manager.update_reading("ph", ph)
        else:
            state_manager.update_component_health("ph", "degraded", "No reading")
            ph_source = "timeout"  # FIXED: Set ph_source when no reading
            print(f"   🧪 pH: timeout/error")

    except Exception as e:
        print(f"   ❌ pH system error: {e}")
        ph = None
        ph_source = "error"  # FIXED: This was already correct
        state_manager.update_component_health("ph", "failed", str(e))

    # === Enhanced WiFi monitoring ===
    wifi_status = wifi_manager.get_status()
    rssi = wifi_status.get("rssi")
    if rssi:
        # Add signal quality indicators
        if rssi >= -50:
            signal_quality = "Excellent"
            signal_emoji = "🟢"
        elif rssi >= -60:
            signal_quality = "Good"
            signal_emoji = "🟡"
        elif rssi >= -70:
            signal_quality = "Fair"
            signal_emoji = "🟠"
        else:
            signal_quality = "Poor"
            signal_emoji = "🔴"

        print(f"   📶 WiFi: {rssi} dBm ({signal_quality} {signal_emoji})")

        # Alert on poor signal
        if rssi <= -70:
            alert_msg = f"Poor WiFi signal: {rssi} dBm"
            state_manager.add_alert(alert_msg, "warning")

        # Update WiFi component health based on signal
        if rssi >= -60:
            state_manager.update_component_health("wifi", "healthy")
        elif rssi >= -70:
            state_manager.update_component_health(
                "wifi", "degraded", f"Weak signal: {rssi} dBm"
            )
        else:
            state_manager.update_component_health(
                "wifi", "failed", f"Poor signal: {rssi} dBm"
            )
    else:
        print("   📶 WiFi: No signal data")
        state_manager.update_component_health("wifi", "degraded", "No signal data")

    # Check for WiFi disconnections
    if not wifi_manager.is_connected():
        print("   ❌ WiFi: DISCONNECTED!")
        state_manager.add_alert("WiFi disconnected", "critical")
        state_manager.update_component_health("wifi", "failed", "Disconnected")

    # Import the NeoPixel function
    from lib.core.neopixel_status import update_neopixel_status

    # Simple NeoPixel Status Update
    current_neopixel_status = update_neopixel_status(
        pixel, wifi_manager, mqtt_manager, state_manager
    )

    # Simple status change detection
    global last_neopixel_status
    if "last_neopixel_status" not in globals():
        last_neopixel_status = None

    if last_neopixel_status != current_neopixel_status:
        if current_neopixel_status == "PROBLEM":
            print("   🔴 NeoPixel: RED - System has problems")
        else:
            print("   🟢 NeoPixel: GREEN - System OK")
        last_neopixel_status = current_neopixel_status

    # Display update (TFT uses SPI, not I2C)
    try:
        if display and ph_label:
            from lib.oled_display.oled_display import update_display

            display_time = time_manager.get_local_time_string()
            display_temp_c = (
                str(round(temp_c, 1)) if isinstance(temp_c, float) else "--"
            )
            display_temp_f = (
                str(round(temp_f, 1)) if isinstance(temp_f, float) else "--"
            )
            display_rssi = str(int(rssi)) if rssi else "--"
            display_ph = str(round(ph, 2)) if isinstance(ph, float) else "--"

            # Direct display update (TFT uses SPI, not I2C)
            update_display(
                ph_label,
                temp_c_label,
                temp_f_label,
                rssi_label,
                time_label,
                display_ph,
                display_temp_c,
                display_temp_f,
                display_rssi,
                display_time,
            )

            state_manager.update_component_health("display", "healthy")
            print("   🖥️ Display: updated")
        else:
            print("   🖥️ Display: not available")
    except Exception as e:
        print(f"   ❌ Display error: {e}")
        state_manager.update_component_health("display", "failed", str(e))

    # Enhanced MQTT data transmission with quality metrics
    try:
        from lib.networking.robust_mqtt import MQTTDataFormatter

        # Format sensor readings
        sensor_readings = MQTTDataFormatter.format_sensor_readings(
            temp_c=temp_c, temp_f=temp_f, ph=ph, rssi=rssi
        )

        # FIXED: Add measurement source info (no more "unknown")
        sensor_readings["temp_source"] = temp_source
        sensor_readings["ph_source"] = ph_source

        # ADD ERROR 32 COUNT: Include Error 32 count in regular publishing
        sensor_readings["error-32-count"] = mqtt_manager.error_32_count

        # Add quality metrics if available
        if measurement_manager and temp_source == "robust":
            try:
                temp_std_dev = state_manager.get_reading("temp_std_dev")
                if temp_std_dev:
                    sensor_readings["temp_std_dev"] = round(temp_std_dev, 4)
            except:
                pass

        # FIXED: Simplified pH quality check
        if measurement_manager and ph_source == "robust":
            try:
                ph_std_dev = state_manager.get_reading("ph_std_dev")
                if ph_std_dev:
                    sensor_readings["ph_std_dev"] = round(ph_std_dev, 4)
            except:
                pass

        # Send sensor data
        sent_count = mqtt_manager.send_readings(sensor_readings)

        # Send system status
        system_status = state_manager.get_status()
        mqtt_manager.send_system_status(system_status)

        # Check MQTT queue status
        mqtt_status = mqtt_manager.get_status()
        if mqtt_status["messages_queued"] > 0:
            queue_size = mqtt_status["messages_queued"]
            print(f"   📦 MQTT: {queue_size} messages queued")
            if queue_size > 5:
                state_manager.add_alert(
                    f"MQTT queue backing up: {queue_size} messages", "warning"
                )

        if sent_count > 0:
            print(f"   📡 MQTT: sent {sent_count} readings")
        else:
            print("   📦 MQTT: readings queued")

    except Exception as e:
        print(f"   ❌ MQTT error: {e}")

        # Add WiFi diagnostics to MQTT errors
        wifi_connected = wifi_manager.is_connected()
        current_rssi = wifi_status.get("rssi") if wifi_status else None
        print(
            f"   📊 WiFi diagnostics: Connected={wifi_connected}, RSSI={current_rssi}"
        )

        if not wifi_connected:
            print("   💡 MQTT error likely due to WiFi disconnection")
        elif current_rssi and current_rssi < -70:
            print("   💡 MQTT error likely due to poor WiFi signal")

    # Status summary
    status = state_manager.get_status()
    components_ok = sum(1 for h in status["components"].values() if h == "OK")
    print(f"   📊 System: {status['state']} | Components OK: {components_ok}/7")

    return temp_c, temp_f, ph, rssi, temp_source
