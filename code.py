# code.py - pH3 version with weighted average temperature (5-minute time constant)
# Simple 5-second RTD cycle: read -> display -> print -> publish (raw + smoothed)
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
from lib.sensors.rtd_sensor import RTDSensor

# Feed watchdog during imports
if watchdog_enabled:
    wdt.feed()

# Import robust modules
from lib.core.lean_state import StateManager
from lib.networking.lean_wifi import WiFiManager
from lib.networking.robust_mqtt import MQTTManager
from lib.time_sync.robust_time import TimeManager

# Feed watchdog after imports
if watchdog_enabled:
    wdt.feed()
print("🐕 Watchdog fed after imports")

# Get RTD feed names from settings
FEED_RTD_TEMP_C = os.getenv("FEED_RTD_TEMP_C", "ph3-temp-c")
FEED_RTD_TEMP_SMOOTH = os.getenv(
    "FEED_RTD_TEMP_SMOOTH", "ph3-temp-smooth"
)  # NEW: For smoothed values
print(f"📡 Using RTD feeds: {FEED_RTD_TEMP_C} (raw), {FEED_RTD_TEMP_SMOOTH} (smoothed)")

# === WEIGHTED AVERAGE CONFIGURATION ===
# Time constant = 5 minutes = 300 seconds
# Sampling interval = 5 seconds
# Smoothing factor α = Δt / (τ + Δt) = 5 / (300 + 5) = 0.0164
SMOOTHING_ALPHA = 5.0 / (300.0 + 5.0)  # α = 0.0164
print(f"🧮 Weighted average config: α = {SMOOTHING_ALPHA:.4f} (5-minute time constant)")

# === PRIME NUMBER ANTI-ALIASING CONFIGURATION ===
# Prime millisecond offsets to prevent power line interference aliasing
# These primes have no common factors with 50Hz (20ms) or 60Hz (16.67ms) periods
PRIME_OFFSETS_MS = [23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83]
BASE_CYCLE_MS = 5000  # 5 seconds base cycle
prime_cycle_index = 0  # Track which prime we're using
print(
    f"⚡ Anti-aliasing config: Base {BASE_CYCLE_MS}ms + prime offsets {PRIME_OFFSETS_MS[:5]}... ms"
)

# === SIMPLE OUTLIER DETECTION CONFIGURATION ===
# Conservative outlier thresholds for hot tub temperature monitoring
OUTLIER_MAX_CHANGE_PER_CYCLE = 0.5  # °C - maximum reasonable change in 5 seconds
OUTLIER_ABSOLUTE_MIN_TEMP = 15.0  # °C - minimum realistic temperature
OUTLIER_ABSOLUTE_MAX_TEMP = 50.0  # °C - maximum realistic temperature
OUTLIER_MAX_CONSECUTIVE = 3  # Max consecutive outliers before alarm
outlier_consecutive_count = 0  # Track consecutive outliers
outlier_total_count = 0  # Track total outliers detected
print(
    f"🛡️ Outlier detection: ±{OUTLIER_MAX_CHANGE_PER_CYCLE}°C/cycle, range {OUTLIER_ABSOLUTE_MIN_TEMP}-{OUTLIER_ABSOLUTE_MAX_TEMP}°C"
)

# === SAFE SHUTDOWN MONITOR SETUP ===
print("🔧 Setting up safe shutdown monitor...")
shutdown_pin = digitalio.DigitalInOut(
    board.D6
)  # Change pin if D6 conflicts with your setup
shutdown_pin.direction = digitalio.Direction.INPUT
shutdown_pin.pull = digitalio.Pull.UP  # Pin normally HIGH, shutdown when LOW
print("   Safe shutdown monitor active - ground D6 to shutdown safely")


def safe_system_shutdown():
    """Enhanced shutdown that properly releases display SPI resources"""
    print("🛑 Safe shutdown initiated...")

    try:
        # First release displays (this should free display SPI)
        import displayio

        displayio.release_displays()
        print("   ✅ Display resources released")

        # Emergency I2C cleanup (your existing function)
        emergency_i2c_cleanup()
        print("   ✅ I2C cleaned up")

        # Clean up main SPI bus
        if "spi" in globals():
            try:
                spi.deinit()
                print("   ✅ Main SPI bus released")
            except:
                pass

        # Clean up board SPI if it exists
        try:
            if hasattr(board, "SPI"):
                board.SPI().deinit()
                print("   ✅ Board SPI released")
        except:
            pass

        # Flash LED to confirm safe state
        led = digitalio.DigitalInOut(board.LED)
        led.direction = digitalio.Direction.OUTPUT
        for _ in range(10):
            led.value = not led.value
            time.sleep(0.2)

        print("🔋 System halted - SAFE TO DISCONNECT USB")
        return True

    except Exception as e:
        print(f"   ⚠️ Shutdown error: {e}")
        return False


# === Setup NeoPixel for status ===
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
pixel[0] = (0, 0, 0)

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

# === Initialize system managers (minimal set for pH3) ===
print("🔧 Initializing pH3 system managers...")
if watchdog_enabled:
    wdt.feed()

# Initialize state manager
state_manager = StateManager(watchdog=wdt if watchdog_enabled else None)

# Register minimal components for pH3
state_manager.register_component("wifi")
state_manager.register_component("time")
state_manager.register_component("temperature")
state_manager.register_component("mqtt")
state_manager.register_component("display")

# Initialize RTD sensor
print("🌡️ Initializing RTD sensor...")
try:
    rtd_sensor = RTDSensor(spi, board.D12, rtd_wires=3)
    rtd_initialized = rtd_sensor.initialize()
    if rtd_initialized:
        print("✅ RTD sensor initialized successfully")
        state_manager.update_component_health("temperature", "healthy")
    else:
        print("❌ RTD sensor initialization failed")
        state_manager.update_component_health(
            "temperature", "failed", "RTD init failed"
        )
        rtd_sensor = None
except Exception as e:
    print(f"❌ RTD sensor error: {e}")
    state_manager.update_component_health("temperature", "failed", str(e))
    rtd_sensor = None

# Initialize TFT display with shared SPI
print("🖥️ Initializing TFT display with shared SPI...")
try:
    from lib.oled_display.oled_display import (
        initialize_display,
        create_display_group,
    )

    display = initialize_display(shared_spi=spi)
    display_group, ph_label, temp_c_label, temp_f_label, rssi_label, time_label = (
        create_display_group()
    )
    display.root_group = display_group
    print("✅ TFT display initialized successfully")
    state_manager.update_component_health("display", "healthy")

    # Initialize display with pH3 outlier detection identifiers
    ph_label.text = "pH3 + Outlier Guard"
    temp_c_label.text = "Raw: --°C"
    temp_f_label.text = "Smooth: --°C"  # Show smoothed temp
    rssi_label.text = "Smart filtering"
    time_label.text = "--:--"

except Exception as e:
    print(f"❌ Display initialization failed: {e}")
    state_manager.update_component_health("display", "failed", str(e))
    display = None
    ph_label = temp_c_label = temp_f_label = rssi_label = time_label = None

if watchdog_enabled:
    wdt.feed()

# Initialize robust managers
print("🌐 Initializing robust WiFi manager...")
wifi_manager = WiFiManager(
    state_manager,
    WIFI_SSID,
    WIFI_PASSWORD,
    backup_ssid=None,
    backup_password=None,
    pixel=pixel,
)

print("🕐 Initializing robust time manager...")
time_manager = TimeManager(state_manager, wifi_manager, timezone_offset=TZ_OFFSET)

print("📡 Initializing robust MQTT manager...")
mqtt_manager = MQTTManager(state_manager, wifi_manager, IO_USERNAME, IO_KEY)

if watchdog_enabled:
    wdt.feed()

# === Connect and initialize all services ===
print("🔗 Connecting WiFi and initializing services...")

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

print("\n✅ pH3 RTD system with weighted averaging initialized!")

# Print status reports
print("System state:", state_manager.get_status())
print("WiFi status:", wifi_manager.get_status())
print("Time status:", time_manager.get_status())
print("MQTT status:", mqtt_manager.get_status())
if rtd_sensor:
    print("RTD status:", rtd_sensor.get_status())
print("=" * 60)

# === Force system to operational state ===
print("🔧 Ensuring system is operational...")
if not state_manager.should_continue():
    print("   Forcing system to operational state...")
    state_manager.state = 2  # DEGRADED - allows operation

print(f"   System ready: {state_manager.should_continue()}")
print("=" * 60)

# === pH3 MAIN LOOP - RTD with Weighted Average + Prime Anti-Aliasing ===
loop_start = time.monotonic()
cycle_count = 0
total_read_time = 0
successful_reads = 0

# Weighted average variables
smoothed_temp = None  # Will be initialized with first reading
smoothed_initialized = False
previous_raw_temp = None  # For outlier detection


# Prime anti-aliasing function
def get_next_prime_cycle_interval():
    """Get next cycle interval with prime millisecond offset for anti-aliasing"""
    global prime_cycle_index
    prime_offset_ms = PRIME_OFFSETS_MS[prime_cycle_index]
    prime_cycle_index = (prime_cycle_index + 1) % len(PRIME_OFFSETS_MS)
    interval_seconds = (BASE_CYCLE_MS + prime_offset_ms) / 1000.0
    return interval_seconds, prime_offset_ms


# Simple outlier detection function
def is_temperature_outlier(new_temp, previous_temp):
    """
    Simple outlier detection for temperature readings
    Returns: (is_outlier: bool, reason: str)
    """
    global outlier_consecutive_count, outlier_total_count

    # Check absolute bounds
    if new_temp < OUTLIER_ABSOLUTE_MIN_TEMP:
        outlier_total_count += 1
        outlier_consecutive_count += 1
        return True, f"too_low ({new_temp:.1f}°C < {OUTLIER_ABSOLUTE_MIN_TEMP}°C)"

    if new_temp > OUTLIER_ABSOLUTE_MAX_TEMP:
        outlier_total_count += 1
        outlier_consecutive_count += 1
        return True, f"too_high ({new_temp:.1f}°C > {OUTLIER_ABSOLUTE_MAX_TEMP}°C)"

    # Check rate of change (only if we have a previous reading)
    if previous_temp is not None:
        change = abs(new_temp - previous_temp)
        if change > OUTLIER_MAX_CHANGE_PER_CYCLE:
            outlier_total_count += 1
            outlier_consecutive_count += 1
            return True, f"big_jump ({change:.3f}°C > {OUTLIER_MAX_CHANGE_PER_CYCLE}°C)"

    # Not an outlier - reset consecutive count
    outlier_consecutive_count = 0
    return False, "normal"


print(
    "🚀 Starting pH3 main loop - RTD with weighted averaging + prime anti-aliasing + outlier detection..."
)
print(f"   Base cycle: {BASE_CYCLE_MS}ms + prime offsets")
print(f"   Raw RTD feed: {FEED_RTD_TEMP_C}")
print(f"   Smoothed feed: {FEED_RTD_TEMP_SMOOTH}")
print(f"   Smoothing factor α: {SMOOTHING_ALPHA:.4f}")
print(f"   Anti-aliasing: {len(PRIME_OFFSETS_MS)} prime intervals")
print(f"   Outlier detection: Active with conservative thresholds")
print("=" * 60)

try:
    while state_manager.should_continue():
        cycle_start = time.monotonic()
        cycle_count += 1

        # === Get next prime-based cycle interval ===
        cycle_interval, prime_offset = get_next_prime_cycle_interval()

        # === Update all managers ===
        wifi_manager.check_connection()
        time_manager.update()
        mqtt_manager.update()
        state_manager.feed_watchdog()

        # === RTD Reading with Weighted Averaging ===
        try:
            if rtd_sensor:
                read_start = time.monotonic()
                temp_c, rtd_source = rtd_sensor.read_temperature()
                read_duration = time.monotonic() - read_start

                if isinstance(temp_c, (int, float)) and rtd_source == "rtd":
                    successful_reads += 1
                    total_read_time += read_duration

                    # === OUTLIER DETECTION ===
                    is_outlier, outlier_reason = is_temperature_outlier(
                        temp_c, previous_raw_temp
                    )

                    if is_outlier:
                        print(
                            f"   🚨 OUTLIER DETECTED: {temp_c:.3f}°C - {outlier_reason}"
                        )
                        print(
                            f"   📊 Outlier stats: {outlier_consecutive_count} consecutive, {outlier_total_count} total"
                        )

                        # Alert if too many consecutive outliers
                        if outlier_consecutive_count >= OUTLIER_MAX_CONSECUTIVE:
                            state_manager.add_alert(
                                f"Temperature outlier: {outlier_consecutive_count} consecutive bad readings",
                                "warning",
                            )

                        # Skip this reading for weighted average calculation
                        # (still publish raw value for analysis, but don't smooth it)
                        temp_for_smoothing = None
                        outlier_status = "OUTLIER"
                    else:
                        # Normal reading - use for smoothing
                        temp_for_smoothing = temp_c
                        outlier_status = "OK"

                    # === WEIGHTED AVERAGE CALCULATION (only for non-outliers) ===
                    if temp_for_smoothing is not None:
                        if not smoothed_initialized:
                            # Initialize with first valid reading
                            smoothed_temp = temp_for_smoothing
                            smoothed_initialized = True
                            print(
                                f"   🧮 Weighted average initialized: {smoothed_temp:.3f}°C"
                            )
                        else:
                            # Apply weighted average: new = α × reading + (1-α) × old
                            smoothed_temp = (
                                SMOOTHING_ALPHA * temp_for_smoothing
                                + (1 - SMOOTHING_ALPHA) * smoothed_temp
                            )

                    # Update previous temperature for next outlier check
                    if not is_outlier:  # Only update with good readings
                        previous_raw_temp = temp_c

                    # 1. Print to serial monitor (raw, smoothed, prime info, outlier status)
                    current_time_str = time_manager.get_local_time_string()
                    print(
                        f"🌡️ Cycle #{cycle_count} at {current_time_str} (interval: {cycle_interval:.3f}s):"
                    )
                    print(
                        f"   Raw: {temp_c:.3f}°C ({read_duration*1000:.1f}ms) [{outlier_status}]"
                    )
                    if smoothed_initialized:
                        print(f"   Smoothed: {smoothed_temp:.3f}°C")
                        print(f"   Diff: {abs(temp_c - smoothed_temp):.3f}°C")
                    print(f"   Prime offset: +{prime_offset}ms (anti-aliasing)")

                    # 2. Display on current display page
                    if temp_c_label and temp_f_label:
                        temp_c_label.text = f"Raw: {temp_c:.1f}°C"
                        temp_f_label.text = f"Smooth: {smoothed_temp:.1f}°C"
                    if time_label:
                        time_label.text = current_time_str

                    # 3. Publish both raw and smoothed to separate feeds
                    rtd_data = {
                        FEED_RTD_TEMP_C: round(
                            temp_c, 3
                        ),  # Always publish raw (even outliers)
                        "timestamp": time_manager.get_timestamp_for_data(),
                    }

                    # Only publish smoothed if we have a valid smoothed value
                    if smoothed_initialized:
                        rtd_data[FEED_RTD_TEMP_SMOOTH] = round(smoothed_temp, 3)

                    mqtt_sent = mqtt_manager.send_readings(rtd_data)
                    if mqtt_sent:
                        if smoothed_initialized:
                            print(
                                f"   📡 Published raw: {temp_c:.3f}°C, smoothed: {smoothed_temp:.3f}°C"
                            )
                        else:
                            print(
                                f"   📡 Published raw: {temp_c:.3f}°C (smoothed not ready)"
                            )
                    else:
                        print(f"   📦 Queued for publishing")

                    # Update component health based on outlier status
                    if outlier_consecutive_count >= OUTLIER_MAX_CONSECUTIVE:
                        state_manager.update_component_health(
                            "temperature",
                            "degraded",
                            f"{outlier_consecutive_count} consecutive outliers",
                        )
                    else:
                        state_manager.update_component_health("temperature", "healthy")

                    state_manager.update_reading("temperature", temp_c)
                    if smoothed_initialized:
                        state_manager.update_reading(
                            "temperature_smooth", smoothed_temp
                        )

                else:
                    print(
                        f"   ❌ Cycle #{cycle_count}: RTD error - temp={temp_c}, source={rtd_source}"
                    )
                    state_manager.update_component_health(
                        "temperature", "degraded", "Read error"
                    )
                    if temp_c_label:
                        temp_c_label.text = "Raw: ERROR"
                    if temp_f_label:
                        temp_f_label.text = "Smooth: ERROR"
            else:
                print(f"   ❌ Cycle #{cycle_count}: RTD sensor not available")
                state_manager.update_component_health(
                    "temperature", "failed", "Sensor unavailable"
                )
                if temp_c_label:
                    temp_c_label.text = "Raw: NO SENSOR"
                if temp_f_label:
                    temp_f_label.text = "Smooth: NO SENSOR"

        except Exception as e:
            print(f"   💥 Cycle #{cycle_count}: RTD exception: {e}")
            state_manager.update_component_health("temperature", "failed", str(e))
            if temp_c_label:
                temp_c_label.text = "Raw: EXCEPTION"
            if temp_f_label:
                temp_f_label.text = "Smooth: EXCEPTION"

        # === Performance statistics every 10 cycles ===
        if cycle_count % 10 == 0:
            avg_read_time = (
                total_read_time / successful_reads if successful_reads > 0 else 0
            )
            success_rate = (
                (successful_reads / cycle_count * 100) if cycle_count > 0 else 0
            )
            uptime = cycle_start - loop_start

            # Calculate average cycle interval for prime anti-aliasing stats
            avg_cycle_interval = (
                BASE_CYCLE_MS + sum(PRIME_OFFSETS_MS) / len(PRIME_OFFSETS_MS)
            ) / 1000.0

            print(f"\n📊 pH3 Outlier Detection Report (Cycle #{cycle_count}):")
            print(
                f"   Success rate: {success_rate:.1f}% ({successful_reads}/{cycle_count})"
            )
            print(f"   Avg read time: {avg_read_time*1000:.1f}ms")
            print(f"   System uptime: {uptime:.1f}s")
            print(
                f"   Avg cycle interval: {avg_cycle_interval:.3f}s (prime anti-aliasing)"
            )
            print(
                f"   Outliers detected: {outlier_total_count} total, {outlier_consecutive_count} consecutive"
            )
            if smoothed_initialized:
                print(f"   Smoothing active: α = {SMOOTHING_ALPHA:.4f}")
                print(f"   Current smoothed: {smoothed_temp:.3f}°C")
                print(
                    f"   Prime offset range: {min(PRIME_OFFSETS_MS)}-{max(PRIME_OFFSETS_MS)}ms"
                )

            # MQTT status
            mqtt_status = mqtt_manager.get_status()
            if mqtt_status["messages_queued"] > 0:
                print(f"   MQTT queue: {mqtt_status['messages_queued']} messages")

            # System status
            system_status = state_manager.get_status()
            components_ok = sum(
                1 for h in system_status["components"].values() if h == "OK"
            )
            print(
                f"   System: {system_status['state']} | Components OK: {components_ok}/{len(system_status['components'])}"
            )
            print("-" * 50)

        # === NeoPixel status update ===
        current_neopixel_status = update_neopixel_status(
            pixel, wifi_manager, mqtt_manager, state_manager
        )

        # === Sleep until next cycle (prime interval) ===
        cycle_duration = time.monotonic() - cycle_start
        sleep_time = cycle_interval - cycle_duration

        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            print(f"   ⚠️ Cycle overrun: {cycle_duration:.3f}s > {cycle_interval:.3f}s")

        # Fast shutdown check during sleep
        for _ in range(int(max(0, sleep_time) * 10)):
            if not shutdown_pin.value:  # Pin pulled LOW = shutdown requested
                if safe_system_shutdown():
                    import sys

                    sys.exit()
            time.sleep(0.01)

except KeyboardInterrupt:
    print("\n🛑 pH3 stopped by user")

except Exception as e:
    print(f"\n💥 pH3 fatal error: {e}")
    import traceback

    traceback.print_exception(e)

    # Emergency cleanup
    emergency_i2c_cleanup()
    state_manager.add_alert(f"FATAL: {e}", "critical")

    # Try to send error via MQTT
    try:
        error_data = {
            "system-error": str(e),
            "error-timestamp": time_manager.get_timestamp_for_data(),
            "ph3-weighted-mode": True,
        }
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

    print("✅ pH3 outlier detection system shutdown complete")
    print(f"📊 Total cycles: {cycle_count}")
    print(f"🌡️ Successful RTD reads: {successful_reads}")
    if successful_reads > 0:
        avg_read_time = total_read_time / successful_reads
        print(f"⚡ Average read time: {avg_read_time*1000:.1f}ms")
    if smoothed_initialized:
        print(f"🧮 Final smoothed temperature: {smoothed_temp:.3f}°C")
        print(f"📈 Smoothing factor used: α = {SMOOTHING_ALPHA:.4f}")
        print(f"⚡ Prime anti-aliasing: {len(PRIME_OFFSETS_MS)} intervals used")
        print(f"🛡️ Outliers detected: {outlier_total_count} total")
    if watchdog_enabled:
        print(f"🐕 Watchdog was active throughout execution")
