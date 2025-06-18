# code.py - Production version with TFT display, early watchdog, I2C safety, temperature fallback, and Robust Measurements
# Rev 3.7 - Full robust measurement system integration
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

# === EARLY WATCHDOG SETUP (FIRST THING!) ===
print("🐕 Setting up early watchdog protection...")
try:
    wdt = microcontroller.watchdog
    wdt.timeout = 60  # EXPANDED: 1 minute for startup (was 30s)
    wdt.mode = watchdog.WatchDogMode.RESET
    wdt.feed()
    watchdog_enabled = True
    print("✅ Early watchdog active - 60 second timeout")
except Exception as e:
    print(f"❌ Early watchdog setup failed: {e}")
    watchdog_enabled = False

# Feed watchdog before potentially hanging operations
if watchdog_enabled:
    wdt.feed()
print("🐕 Watchdog fed before I2C operations")


# === I2C RESET FUNCTIONS ===
def safe_i2c_reset_with_timeout(timeout_seconds=20):  # EXPANDED: was 10s
    """Attempt I2C reset with timeout protection and watchdog feeding"""
    start_time = time.monotonic()
    print(f"🔄 Starting I2C reset with {timeout_seconds}s timeout...")
    try:
        # Feed watchdog before starting
        if watchdog_enabled:
            wdt.feed()

        # Check timeout before each operation
        if time.monotonic() - start_time > timeout_seconds:
            raise Exception("I2C reset timeout - forcing restart")

        if hasattr(board, "I2C"):
            try:
                board.I2C().deinit()
                print("   Board I2C deinitialized")
                if watchdog_enabled:
                    wdt.feed()
            except Exception as e:
                print(f"   Board I2C deinit error: {e}")

        # Check timeout again
        if time.monotonic() - start_time > timeout_seconds:
            raise Exception("I2C reset timeout - forcing restart")

        # Create and immediately deinit temp I2C
        temp_i2c = busio.I2C(board.SCL, board.SDA)
        temp_i2c.deinit()
        print("   Temp I2C created and deinitialized")
        if watchdog_enabled:
            wdt.feed()

        elapsed = time.monotonic() - start_time
        print(f"✅ I2C reset complete in {elapsed:.2f}s")
        return True

    except Exception as e:
        elapsed = time.monotonic() - start_time
        print(f"❌ I2C reset failed after {elapsed:.2f}s: {e}")
        if "timeout" in str(e).lower():
            print("🔄 Forcing microcontroller reset due to I2C timeout...")
            time.sleep(1)
            microcontroller.reset()
        return False


def emergency_i2c_cleanup():
    """Emergency I2C cleanup on errors"""
    try:
        print("🚨 Emergency I2C cleanup...")
        if hasattr(board, "I2C"):
            board.I2C().deinit()
            time.sleep(0.5)
        print("   Emergency cleanup complete")
    except:
        pass  # If this fails, we're already in trouble


# Execute protected I2C reset with expanded timeout
safe_i2c_reset_with_timeout(20)  # EXPANDED: was 10s
time.sleep(0.5)

# Feed watchdog after I2C operations
if watchdog_enabled:
    wdt.feed()
print("🐕 Watchdog fed after I2C reset")

# Read timezone offset from settings.toml
TZ_OFFSET = int(os.getenv("TZ_OFFSET", 1))  # Default to 1 if not found
print(f"🕐 Using timezone offset: UTC{'+' if TZ_OFFSET >= 0 else ''}{TZ_OFFSET}")

# Feed watchdog during imports
if watchdog_enabled:
    wdt.feed()

from lib.config.settings import WIFI_SSID, WIFI_PASSWORD, IO_USERNAME, IO_KEY
from lib.sensors import temperature
from lib.sensors.ph_sensor import AtlasScientificPH
from lib.sensors.rtd_sensor import RTDSensor

# Import TFT display functions
from lib.oled_display.oled_display import (
    initialize_display,
    create_display_group,
    update_display,
)

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

# === Setup NeoPixel for status ===
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
pixel[0] = (0, 0, 0)


def check_temperature_health_and_reset():
    """Check temperature sensor health and reset system if persistently failed"""
    temp_status = temperature.get_temperature_status()
    if (
        temp_status["consecutive_failures"] >= 50
        and temp_status["time_since_last_success"] is not None
        and temp_status["time_since_last_success"] > 1800
    ):
        print("🚨 TEMPERATURE RESET TRIGGERED:")
        print(f"   Consecutive failures: {temp_status['consecutive_failures']}")
        print(
            f"   Time since last success: {temp_status['time_since_last_success']:.0f}s"
        )
        print("🔄 Resetting microcontroller in 5 seconds...")
        time.sleep(5)
        import microcontroller

        microcontroller.reset()


# === Setup I2C and SPI buses ===
print("🔌 Setting up I2C bus...")
if watchdog_enabled:
    wdt.feed()

i2c = busio.I2C(board.SCL, board.SDA)
while not i2c.try_lock():
    pass
i2c.unlock()
print("✅ I2C bus ready")

print("🔌 Setting up shared SPI bus...")
# ADDED: Clean up any existing SPI bus for auto-reload compatibility
try:
    if hasattr(board, "SPI"):
        board.SPI().deinit()
        print("   Cleaned up existing SPI bus")
        time.sleep(0.5)  # Brief delay to let hardware settle
except Exception as e:
    print(f"   SPI cleanup note: {e}")

# Try to create SPI bus with retry logic
for attempt in range(3):
    try:
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        print("✅ Shared SPI bus ready")
        break
    except ValueError as e:
        if "in use" in str(e) and attempt < 2:
            print(f"   SPI attempt {attempt + 1} failed, retrying in 1s...")
            time.sleep(1)
            if watchdog_enabled:
                wdt.feed()
        else:
            print(f"   ❌ SPI initialization failed after {attempt + 1} attempts: {e}")
            print("   🔄 Forcing reset to clear SPI state...")
            time.sleep(2)
            microcontroller.reset()

# Feed watchdog after SPI setup
if watchdog_enabled:
    wdt.feed()

# === Adjust watchdog timeout for normal operation ===
if watchdog_enabled:
    try:
        wdt.timeout = 60  # EXPANDED: 1 minute for normal operation (was 20s)
        wdt.feed()
        print("🐕 Watchdog timeout adjusted to 60 seconds for normal operation")
    except Exception as e:
        print(f"⚠️ Watchdog timeout adjustment failed: {e}")

# === Temperature fallback configuration ===
NOMINAL_HOT_TUB_TEMP_F = 103.0  # Fallback temperature for pH compensation
NOMINAL_HOT_TUB_TEMP_C = (
    (NOMINAL_HOT_TUB_TEMP_F - 32.0) * 5.0 / 9.0
)  # Convert to Celsius


def safe_read_temperature():
    """Safely read temperature with RTD priority, then fallback"""
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

    # Try OneWire temperature as backup
    try:
        temp_c = temperature.read_temperature()
        check_temperature_health_and_reset()
        if isinstance(temp_c, (int, float)) and temp_c != 85.0:
            return temp_c, "onewire"
        else:
            return NOMINAL_HOT_TUB_TEMP_C, "nominal"
    except Exception as e:
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

        time.sleep(0.01)

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
