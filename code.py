# code.py - Production version with TFT display, early watchdog, I2C safety, temperature fallback, and Robust Measurements
# Rev 3.8 - Cleaned up OneWire dependencies, RTD-only temperature system
import time
import board
import digitalio
import neopixel
import wifi
import socketpool
import microcontroller
import busio
import watchdog
import os

import supervisor

supervisor.runtime.autoreload = False

# Import extracted modules
from lib.core.neopixel_status import (
    update_neopixel_status,
    print_neopixel_legend,
    neopixel_diagnostic_test,
)
from lib.core.system_init import initialize_system_managers
from lib.core.connection_manager import connect_and_initialize_services
from lib.core.sensor_cycle import run_sensor_cycle
from lib.core.status_reporter import run_detailed_status_report

# === CALIBRATION BUTTON DETECTION (CORRECTED) ===
print("🔧 Checking for calibration mode...")
detection_start = time.monotonic()

# Setup button pins for calibration detection - BOTH required
try:
    next_btn = digitalio.DigitalInOut(board.D13)  # NEXT button
    next_btn.direction = digitalio.Direction.INPUT
    next_btn.pull = digitalio.Pull.UP

    abort_btn = digitalio.DigitalInOut(board.D11)  # ABORT button
    abort_btn.direction = digitalio.Direction.INPUT
    abort_btn.pull = digitalio.Pull.UP

    # Check immediately for both buttons pressed (active low)
    both_pressed = not next_btn.value and not abort_btn.value

    if both_pressed:
        detection_time = time.monotonic() - detection_start
        print(f"🎯 CALIBRATION MODE DETECTED! ({detection_time:.1f}s)")

        try:
            print("📡 Importing calibration system...")
            from lib.calibration.calibration_system import run_calibration_mode

            print("🚀 Starting calibration interface...")
            run_calibration_mode()

        except ImportError as e:
            print(f"❌ Calibration module not found: {e}")
            print("   Continuing to normal monitoring mode...")

        except Exception as e:
            print(f"❌ Calibration failed: {e}")
            print("   Continuing to normal monitoring mode...")
    else:
        # Wait full 8 seconds to give user time (only if not detected immediately)
        while time.monotonic() - detection_start < 8.0:
            both_pressed = not next_btn.value and not abort_btn.value
            if both_pressed:
                detection_time = time.monotonic() - detection_start
                print(f"🎯 CALIBRATION MODE DETECTED! ({detection_time:.1f}s)")

                try:
                    print("📡 Importing calibration system...")
                    from lib.calibration.calibration_system import (
                        run_calibration_mode,
                    )

                    print("🚀 Starting calibration interface...")
                    run_calibration_mode()

                except ImportError as e:
                    print(f"❌ Calibration module not found: {e}")
                    print("   Continuing to normal monitoring mode...")

                except Exception as e:
                    print(f"❌ Calibration failed: {e}")
                    print("   Continuing to normal monitoring mode...")
                break
            time.sleep(0.1)  # Check every 100ms

except Exception as e:
    print(f"❌ Button detection setup failed: {e}")
    print("   Continuing to normal monitoring mode...")

# Continue with normal monitoring regardless of calibration outcome
calibration_check_time = time.monotonic() - detection_start
print(f"   📊 Normal monitoring mode (checked for {calibration_check_time:.1f}s)")
print("🟢 NORMAL MODE - Full system initialization")

# === HARDWARE BOOTSTRAP INITIALIZATION ===
from lib.startup.hardware_bootstrap import initialize_hardware_foundation

watchdog_enabled, wdt, i2c, spi, pixel, shutdown_pin = initialize_hardware_foundation()

# [Rest of the code remains the same...]

# Read timezone offset from settings.toml
TZ_OFFSET = int(os.getenv("TZ_OFFSET", 1))  # Default to 1 if not found
print(f"🕐 Using timezone offset: UTC{'+' if TZ_OFFSET >= 0 else ''}{TZ_OFFSET}")

# Feed watchdog during imports
if watchdog_enabled:
    wdt.feed()

from lib.config.settings import WIFI_SSID, WIFI_PASSWORD, IO_USERNAME, IO_KEY
from lib.sensors.ph_sensor import AtlasScientificPH
from lib.sensors.rtd_sensor import RTDSensor

# Feed watchdog during imports
if watchdog_enabled:
    wdt.feed()

# Import robust modules
from lib.core.lean_state import StateManager
from lib.networking.lean_wifi import WiFiManager
from lib.networking.robust_mqtt import MQTTManager, MQTTDataFormatter
from lib.time_sync.robust_time import TimeManager

# Import I2C safety wrapper
from lib.utilities.i2c_safe import I2CSafeWrapper, create_safe_sensor_reader

# Import measurement integration module
from lib.sensors.measurement_integration import create_measurement_manager

# Feed watchdog after imports
if watchdog_enabled:
    wdt.feed()
print("🐕 Watchdog fed after imports")

# === Temperature fallback configuration ===
NOMINAL_HOT_TUB_TEMP_F = (
    104.0  # UPDATED: Clean fallback temperature for pH compensation
)
NOMINAL_HOT_TUB_TEMP_C = (
    (NOMINAL_HOT_TUB_TEMP_F - 32.0) * 5.0 / 9.0
)  # Convert to Celsius


def safe_read_temperature():
    """Safely read temperature with RTD, fallback to nominal (CLEANED: No OneWire)"""
    # Try RTD first if it exists and is working
    if rtd_sensor:
        try:
            rtd_reading = rtd_sensor.read_temperature()
            # Handle different return formats from RTD sensor
            if isinstance(rtd_reading, dict) and rtd_reading.get("success"):
                return rtd_reading["temp_c"], "rtd"
            elif isinstance(rtd_reading, tuple) and len(rtd_reading) >= 2:
                temp_c, success = rtd_reading[0], rtd_reading[1]
                if success:
                    return temp_c, "rtd"
            elif isinstance(rtd_reading, (int, float)) and -50 < rtd_reading < 150:
                return rtd_reading, "rtd"
        except Exception as e:
            print(f"   ⚠️ RTD read error: {e}")

    # Clean fallback to nominal temperature (REMOVED: OneWire complexity)
    return NOMINAL_HOT_TUB_TEMP_C, "nominal"


# === Initialize all system components ===
managers = initialize_system_managers(
    watchdog_enabled,
    wdt,
    i2c,
    spi,
    pixel,
    WIFI_SSID,
    WIFI_PASSWORD,
    IO_USERNAME,
    IO_KEY,
    TZ_OFFSET,
    safe_read_temperature,
)

# Unpack managers for easier access
state_manager = managers["state_manager"]
i2c_safe = managers["i2c_safe"]
ph_sensor = managers["ph_sensor"]
rtd_sensor = managers["rtd_sensor"]
display = managers["display"]
ph_label = managers["ph_label"]
temp_c_label = managers["temp_c_label"]
temp_f_label = managers["temp_f_label"]
rssi_label = managers["rssi_label"]
time_label = managers["time_label"]
safe_read_ph = managers["safe_read_ph"]
wifi_manager = managers["wifi_manager"]
time_manager = managers["time_manager"]
mqtt_manager = managers["mqtt_manager"]
measurement_manager = managers["measurement_manager"]

# === Connect and initialize all services ===
connect_and_initialize_services(
    wifi_manager,
    time_manager,
    mqtt_manager,
    ph_sensor,
    safe_read_ph,
    watchdog_enabled,
    wdt,
    safe_read_temperature,
    pixel,
)

# Print status reports
print("System state:", state_manager.get_status())
print("WiFi status:", wifi_manager.get_status())
print("Time status:", time_manager.get_status())
print("MQTT status:", mqtt_manager.get_status())
print("I2C stats:", i2c_safe.get_stats())
print("Measurement manager stats:", measurement_manager.get_statistics())
print("=" * 60)

# === Force system to operational state ===
print("🔧 Ensuring system is operational...")
if not state_manager.should_continue():
    print("   Forcing system to operational state...")
    state_manager.state = 2  # DEGRADED - allows operation

print(f"   System ready: {state_manager.should_continue()}")
print("=" * 60)

# === Main loop variables ===
loop_start = time.monotonic()
sensor_interval = 2.0
last_status_report = time.monotonic()
status_report_interval = 60
last_i2c_health_check = time.monotonic()
i2c_health_check_interval = 30  # Check I2C health every 30 seconds
main_loop_iterations = 0
last_neopixel_status = None  # Track NeoPixel status changes

print("🚀 Starting main monitoring loop with robust measurements...")

try:

    while state_manager.should_continue():

        main_loop_iterations += 1
        now = time.monotonic()

        if main_loop_iterations == 1:
            print("✅ MAIN LOOP STARTED SUCCESSFULLY!")

        # === Update all managers ===
        wifi_manager.check_connection()
        time_manager.update()
        mqtt_manager.update()

        # === I2C health monitoring ===
        if now - last_i2c_health_check >= i2c_health_check_interval:
            last_i2c_health_check = now
            if i2c_safe.check_i2c_health():
                state_manager.update_component_health("i2c", "healthy")
            else:
                state_manager.update_component_health(
                    "i2c", "degraded", "Health check failed"
                )

        # === Sensor readings (every 2 seconds) ===
        if now - loop_start >= sensor_interval:
            loop_start = now

            # Run the extracted sensor cycle function with measurement manager
            temp_c, temp_f, ph, rssi, temp_source = run_sensor_cycle(
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
                NOMINAL_HOT_TUB_TEMP_C,
                NOMINAL_HOT_TUB_TEMP_F,
                measurement_manager,
            )

            # Show I2C stats
            i2c_stats = i2c_safe.get_stats()
            if i2c_stats["total_operations"] > 0:
                print(
                    f"   🛡️ I2C: {i2c_stats['success_rate']}% success, {i2c_stats['timeouts']} timeouts, {i2c_stats['resets']} resets"
                )

            print("-" * 50)

        # === Detailed status report (every minute) ===
        if now - last_status_report >= status_report_interval:
            last_status_report = now

            # Run the extracted detailed status report function with measurement manager
            run_detailed_status_report(
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
            )

        # Fast shutdown check during sleep (checks every 10ms)
        for _ in range(10):  # 10 checks * 10ms = 100ms total
            if not shutdown_pin.value:  # Pin pulled LOW = shutdown requested
                if safe_system_shutdown():
                    import sys

                    sys.exit()  # Clean exit
            time.sleep(0.01)  # 10ms per check

except KeyboardInterrupt:
    print("\n🛑 Stopped by user")

except Exception as e:
    print(f"\n💥 Fatal error: {e}")
    import traceback

    traceback.print_exception(e)

    # Emergency cleanup
    emergency_i2c_cleanup()
    state_manager.add_alert(f"FATAL: {e}", "critical")

    # Try to send error via MQTT with I2C stats
    try:
        i2c_stats = i2c_safe.get_stats()
        error_data = {
            "system-error": str(e),
            "error-timestamp": time_manager.get_timestamp_for_data(),
            "i2c-success-rate": i2c_stats["success_rate"],
            "i2c-resets": i2c_stats["resets"],
        }
        if measurement_manager:
            measurement_stats = measurement_manager.get_statistics()
            error_data["measurement-robust-enabled"] = measurement_stats["enabled"]
        mqtt_manager.send_readings(error_data)
    except:
        pass

    pixel[0] = (128, 0, 0)
    time.sleep(5)
    microcontroller.reset()

finally:
    # Clean shutdown
    try:
        emergency_i2c_cleanup()
        mqtt_manager.disconnect()
        wifi_manager.disconnect()
    except:
        pass

    print("✅ System shutdown complete")
    print(f"📊 Total monitoring cycles: {main_loop_iterations}")
    print(f"🛡️ Final I2C stats: {i2c_safe.get_stats()}")
    if measurement_manager:
        print(f"📊 Final measurement stats: {measurement_manager.get_statistics()}")
    if watchdog_enabled:
        print(f"🐕 Watchdog was active throughout execution")
