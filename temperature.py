# lib/sensors/temperature.py – Rev 1.4 – Moved to D6 pin for SD card compatibility
# DS18B20 sensor with comprehensive error handling, timeout protection, and auto-recovery

import board
import adafruit_ds18x20
import adafruit_onewire.bus
import time
import microcontroller

# === Internal cache ===
_TEMP_SENSOR = None
_ONEWIRE_BUS = None
_LAST_ERROR = None
_INIT_ATTEMPTS = 0
_LAST_SUCCESSFUL_READ = None
_TOTAL_READS = 0
_SUCCESSFUL_READS = 0
_TIMEOUT_COUNT = 0
_RESET_COUNT = 0
_LAST_RESET_TIME = 0

# === Configuration ===
READ_TIMEOUT = 5.0  # Timeout for temperature readings
INIT_TIMEOUT = 10.0  # Timeout for sensor initialization
SCAN_TIMEOUT = 3.0  # Timeout for OneWire bus scanning
RESET_COOLDOWN = 30.0  # Minimum time between full resets
MAX_CONSECUTIVE_FAILURES = 3  # Force reset after this many failures
FALLBACK_TEMP_C = 39.0  # Fallback temperature (103°F in Celsius)

# === Error tracking ===
_consecutive_failures = 0
_last_failure_time = 0


def _timeout_wrapper(func, timeout_seconds, description="operation"):
    """Execute function with timeout protection"""
    start_time = time.monotonic()

    try:
        print(f"   🕐 Starting {description} (timeout: {timeout_seconds}s)")

        # For operations that don't naturally yield, we need to implement timeout differently
        # This is a simplified timeout - for more complex operations, you might need threading
        result = func()

        elapsed = time.monotonic() - start_time
        print(f"   ✅ {description} completed in {elapsed:.2f}s")
        return result, None

    except Exception as e:
        elapsed = time.monotonic() - start_time

        if elapsed >= timeout_seconds:
            error_msg = f"{description} timed out after {elapsed:.2f}s"
            print(f"   ⏰ {error_msg}")
            return None, error_msg
        else:
            error_msg = f"{description} failed: {e}"
            print(f"   ❌ {error_msg}")
            return None, error_msg


def _safe_bus_scan():
    """Safely scan OneWire bus with timeout protection"""

    def scan_operation():
        return _ONEWIRE_BUS.scan()

    return _timeout_wrapper(scan_operation, SCAN_TIMEOUT, "OneWire bus scan")


def _safe_temperature_read():
    """Safely read temperature with timeout protection"""

    def read_operation():
        return _TEMP_SENSOR.temperature

    return _timeout_wrapper(read_operation, READ_TIMEOUT, "temperature read")


def _init_sensor():
    """Initialize DS18B20 sensor with comprehensive timeout protection"""
    global _TEMP_SENSOR, _ONEWIRE_BUS, _LAST_ERROR, _INIT_ATTEMPTS
    global _RESET_COUNT

    _INIT_ATTEMPTS += 1
    print(f"🌡️  DS18B20 initialization attempt #{_INIT_ATTEMPTS}")

    start_time = time.monotonic()

    try:
        # Step 1: Initialize OneWire bus
        if _ONEWIRE_BUS is None:
            print("   Creating OneWire bus on pin A1 (GPIO2)...")
            _ONEWIRE_BUS = adafruit_onewire.bus.OneWireBus(board.A1)
            print("   ✅ OneWire bus created successfully")

        # Check initialization timeout
        if time.monotonic() - start_time > INIT_TIMEOUT:
            raise TimeoutError("Initialization timeout exceeded")

        # Step 2: Scan for devices with timeout protection
        print("   Scanning for OneWire devices...")
        devices, error = _safe_bus_scan()

        if error:
            _LAST_ERROR = f"Bus scan failed: {error}"
            print(f"   ❌ {_LAST_ERROR}")
            _force_bus_reset()
            return False

        if not devices:
            _LAST_ERROR = "No OneWire devices found on pin A1"
            print(f"   ❌ {_LAST_ERROR}")
            _TEMP_SENSOR = None
            return False

        print(f"   Found {len(devices)} OneWire devices")

        # Print device addresses for debugging
        for i, device in enumerate(devices):
            print(f"   Device {i}: {device} (type: {type(device)})")

        # Check initialization timeout again
        if time.monotonic() - start_time > INIT_TIMEOUT:
            raise TimeoutError("Initialization timeout exceeded")

        # Step 3: Initialize DS18B20 with first device
        print(f"   Initializing DS18B20 with first device...")
        _TEMP_SENSOR = adafruit_ds18x20.DS18X20(_ONEWIRE_BUS, devices[0])
        print("   ✅ DS18B20 sensor initialized successfully")

        # Step 4: Test read with timeout protection
        print("   Testing sensor read...")
        test_temp, error = _safe_temperature_read()

        if error:
            _LAST_ERROR = f"Test read failed: {error}"
            print(f"   ❌ {_LAST_ERROR}")
            _TEMP_SENSOR = None
            return False

        print(f"   ✅ Test read successful: {test_temp}°C")

        elapsed = time.monotonic() - start_time
        print(f"   ✅ Complete initialization in {elapsed:.2f}s")

        _LAST_ERROR = None
        return True

    except TimeoutError as e:
        _LAST_ERROR = f"DS18B20 init timeout: {e}"
        print(f"   ⏰ {_LAST_ERROR}")
        _force_bus_reset()
        return False

    except Exception as e:
        _LAST_ERROR = f"DS18B20 init error: {e}"
        print(f"   ❌ {_LAST_ERROR}")

        # Additional debugging for address issues
        if "OneWireAddress" in str(e):
            print("   🔍 OneWireAddress issue detected - trying recovery...")
            return _attempt_address_recovery()

        _TEMP_SENSOR = None
        return False


def _attempt_address_recovery():
    """Attempt to recover from OneWireAddress issues"""
    global _TEMP_SENSOR, _LAST_ERROR

    try:
        print("   🔄 Attempting address recovery...")

        # Try alternative initialization
        devices, error = _safe_bus_scan()
        if error or not devices:
            return False

        print(f"   Retrying with device: {devices[0]}")
        _TEMP_SENSOR = adafruit_ds18x20.DS18X20(_ONEWIRE_BUS, devices[0])

        # Test the recovered sensor
        test_temp, error = _safe_temperature_read()
        if error:
            return False

        print(f"   ✅ Recovery successful: {test_temp}°C")
        _LAST_ERROR = None
        return True

    except Exception as e:
        print(f"   ❌ Recovery failed: {e}")
        return False


def _force_bus_reset():
    """Force a complete OneWire bus reset"""
    global _ONEWIRE_BUS, _TEMP_SENSOR, _RESET_COUNT, _LAST_RESET_TIME

    current_time = time.monotonic()

    # Respect reset cooldown
    if current_time - _LAST_RESET_TIME < RESET_COOLDOWN:
        print(f"   ⏳ Reset cooldown active ({RESET_COOLDOWN}s)")
        return False

    _RESET_COUNT += 1
    _LAST_RESET_TIME = current_time

    print(f"   🔄 Force resetting OneWire bus (reset #{_RESET_COUNT})")

    try:
        # Cleanup existing objects
        _TEMP_SENSOR = None
        if _ONEWIRE_BUS:
            try:
                del _ONEWIRE_BUS
            except:
                pass
        _ONEWIRE_BUS = None

        # Brief delay to let hardware settle
        time.sleep(0.5)

        print("   ✅ Bus reset complete")
        return True

    except Exception as e:
        print(f"   ❌ Bus reset failed: {e}")
        return False


def read_temperature():
    """Read temperature with comprehensive error handling and recovery"""
    global _TEMP_SENSOR, _LAST_ERROR, _TOTAL_READS, _SUCCESSFUL_READS
    global _TIMEOUT_COUNT, _consecutive_failures, _LAST_SUCCESSFUL_READ, _last_failure_time

    _TOTAL_READS += 1
    start_time = time.monotonic()

    # Initialize sensor if needed
    if _TEMP_SENSOR is None:
        print("🌡️  Temperature sensor not initialized, attempting init...")
        if not _init_sensor():
            _consecutive_failures += 1
            _last_failure_time = time.monotonic()
            return _handle_read_failure("Initialization failed")

    try:
        print("🌡️  Reading DS18B20 temperature...")

        # Read with timeout protection
        temperature, error = _safe_temperature_read()

        if error:
            _TIMEOUT_COUNT += 1 if "timeout" in error.lower() else 0
            _consecutive_failures += 1
            _last_failure_time = time.monotonic()

            # Reset sensor on timeout or critical errors
            if (
                "timeout" in error.lower()
                or _consecutive_failures >= MAX_CONSECUTIVE_FAILURES
            ):
                print(f"   🔄 Resetting sensor due to: {error}")
                _TEMP_SENSOR = None

                if _consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    _force_bus_reset()

            return _handle_read_failure(error)

        # Success!
        _SUCCESSFUL_READS += 1
        _consecutive_failures = 0
        _LAST_SUCCESSFUL_READ = time.monotonic()
        _LAST_ERROR = None

        elapsed = time.monotonic() - start_time
        print(f"   ✅ Temperature read: {temperature}°C (in {elapsed:.2f}s)")

        return temperature

    except Exception as e:
        _consecutive_failures += 1
        _last_failure_time = time.monotonic()
        error_msg = f"DS18B20 read error: {e}"
        print(f"   ❌ {error_msg}")

        # Reset sensor on any exception
        _TEMP_SENSOR = None

        return _handle_read_failure(error_msg)


def _handle_read_failure(error_msg):
    """Handle temperature read failure with appropriate response"""
    global _LAST_ERROR

    _LAST_ERROR = error_msg

    # Check if we should force a system reset due to persistent failures
    current_time = time.monotonic()
    if (
        _consecutive_failures >= MAX_CONSECUTIVE_FAILURES * 2
        and _LAST_SUCCESSFUL_READ
        and current_time - _LAST_SUCCESSFUL_READ > 300
    ):  # 5 minutes without success

        print(f"   🚨 Persistent temperature failures - system may need attention")
        print(f"   📊 Consecutive failures: {_consecutive_failures}")
        print(
            f"   📊 Time since last success: {current_time - _LAST_SUCCESSFUL_READ:.0f}s"
        )

    return None


def get_temperature_status():
    """Get comprehensive temperature sensor status for debugging"""
    current_time = time.monotonic()
    success_rate = (_SUCCESSFUL_READS / _TOTAL_READS * 100) if _TOTAL_READS > 0 else 0

    time_since_success = (
        (current_time - _LAST_SUCCESSFUL_READ) if _LAST_SUCCESSFUL_READ else None
    )
    time_since_failure = (
        (current_time - _last_failure_time) if _last_failure_time else None
    )
    time_since_reset = (current_time - _LAST_RESET_TIME) if _LAST_RESET_TIME else None

    return {
        "sensor_initialized": _TEMP_SENSOR is not None,
        "bus_initialized": _ONEWIRE_BUS is not None,
        "last_error": _LAST_ERROR,
        "init_attempts": _INIT_ATTEMPTS,
        "pin": "A1 (GPIO2)",
        "total_reads": _TOTAL_READS,
        "successful_reads": _SUCCESSFUL_READS,
        "success_rate": round(success_rate, 1),
        "timeout_count": _TIMEOUT_COUNT,
        "reset_count": _RESET_COUNT,
        "consecutive_failures": _consecutive_failures,
        "time_since_last_success": time_since_success,
        "time_since_last_failure": time_since_failure,
        "time_since_last_reset": time_since_reset,
        "fallback_temp": FALLBACK_TEMP_C,
        "health_status": _get_health_status(),
    }


def _get_health_status():
    """Determine sensor health status"""
    if _TEMP_SENSOR is None:
        return "failed"
    elif _consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        return "critical"
    elif _consecutive_failures > 0:
        return "degraded"
    elif _TIMEOUT_COUNT > 0:
        return "warning"
    else:
        return "healthy"


def reset_temperature_sensor():
    """Force reset of temperature sensor with statistics reset"""
    global _TEMP_SENSOR, _ONEWIRE_BUS, _LAST_ERROR, _INIT_ATTEMPTS
    global _consecutive_failures, _TIMEOUT_COUNT

    print("🔄 Resetting DS18B20 sensor...")
    _TEMP_SENSOR = None
    _ONEWIRE_BUS = None
    _LAST_ERROR = None
    _INIT_ATTEMPTS = 0
    _consecutive_failures = 0
    _TIMEOUT_COUNT = 0
    print("   ✅ Sensor reset complete")


def get_fallback_temperature():
    """Get fallback temperature for system continuity"""
    return FALLBACK_TEMP_C


def test_onewire_pins():
    """Test OneWire on different pins to find the sensor"""
    test_pins = [
        board.A1,
        board.A2,
        board.A3,
        board.D9,
        board.D10,
        board.D6,
        board.D5,
    ]  # Try A1 first, then other good options

    print("🔍 Testing OneWire on different pins...")

    for pin in test_pins:
        try:
            print(f"   Testing pin {pin}...")

            # Create bus with timeout protection
            start_time = time.monotonic()
            bus = adafruit_onewire.bus.OneWireBus(pin)

            if time.monotonic() - start_time > 3.0:
                print(f"   ⏰ Pin {pin} initialization timed out")
                continue

            devices = bus.scan()

            if devices:
                print(f"   ✅ Found {len(devices)} device(s) on pin {pin}")
                for i, device in enumerate(devices):
                    print(f"     Device {i}: {device}")

                # Try to initialize DS18B20 with first device
                try:
                    sensor = adafruit_ds18x20.DS18X20(bus, devices[0])
                    temp = sensor.temperature
                    print(f"   ✅ DS18B20 working on pin {pin}: {temp}°C")
                    return pin, devices[0]
                except Exception as e:
                    print(f"   ❌ Device on pin {pin} is not DS18B20: {e}")
            else:
                print(f"   No devices found on pin {pin}")

        except Exception as e:
            print(f"   ❌ Error testing pin {pin}: {e}")
        finally:
            # Cleanup
            try:
                del bus
            except:
                pass

    print("   ❌ No working DS18B20 found on any pin")
    return None, None


def emergency_temperature_cleanup():
    """Emergency cleanup for temperature sensor"""
    global _TEMP_SENSOR, _ONEWIRE_BUS

    try:
        print("🚨 Emergency temperature sensor cleanup...")
        _TEMP_SENSOR = None
        if _ONEWIRE_BUS:
            del _ONEWIRE_BUS
        _ONEWIRE_BUS = None
        time.sleep(0.5)
        print("   Emergency temperature cleanup complete")
    except:
        pass


# Debugging function for OneWire address issues
def debug_onewire_addresses():
    """Debug OneWire device addresses with timeout protection"""
    print("🔍 OneWire Address Debug:")
    try:
        if _ONEWIRE_BUS is None:
            bus = adafruit_onewire.bus.OneWireBus(board.A1)
        else:
            bus = _ONEWIRE_BUS

        # Scan with timeout
        start_time = time.monotonic()
        devices = bus.scan()
        scan_time = time.monotonic() - start_time

        print(f"   Found {len(devices)} devices (scan took {scan_time:.2f}s):")

        for i, device in enumerate(devices):
            print(f"   Device {i}:")
            print(f"     Address: {device}")
            print(f"     Type: {type(device)}")
            print(f"     Repr: {repr(device)}")

            # Try to get device family (DS18B20 should be family 0x28)
            try:
                if hasattr(device, "family_code"):
                    print(f"     Family: {hex(device.family_code)}")
                elif hasattr(device, "rom"):
                    print(f"     ROM: {device.rom}")
            except:
                pass

    except Exception as e:
        print(f"   ❌ Debug error: {e}")


def print_temperature_statistics():
    """Print comprehensive temperature sensor statistics"""
    status = get_temperature_status()

    print("\n🌡️  Temperature Sensor Statistics:")
    print(f"   Health Status: {status['health_status']}")
    print(f"   Pin: {status['pin']}")  # Will now show D4
    print(f"   Sensor Initialized: {status['sensor_initialized']}")
    print(
        f"   Success Rate: {status['success_rate']}% ({status['successful_reads']}/{status['total_reads']})"
    )
    print(f"   Consecutive Failures: {status['consecutive_failures']}")
    print(f"   Timeout Count: {status['timeout_count']}")
    print(f"   Reset Count: {status['reset_count']}")
    print(f"   Init Attempts: {status['init_attempts']}")

    if status["time_since_last_success"]:
        print(f"   Time Since Last Success: {status['time_since_last_success']:.0f}s")

    if status["last_error"]:
        print(f"   Last Error: {status['last_error']}")

    print()
