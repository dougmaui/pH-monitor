# lib/sensors/temperature.py – Rev 2.0 – RTD version using MAX31865 amplifier (SPI)
# Compatible with PT100 RTD and Adafruit P3328D

import board
import digitalio
import busio
import adafruit_max31865
import time

# === SPI and RTD Configuration ===
CS_PIN = board.D12  # Set to unused GPIO for MAX31865 CS
RTD_WIRES = 3  # 2, 3, or 4-wire RTD

#spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
#cs = digitalio.DigitalInOut(CS_PIN)
#cs.direction = digitalio.Direction.OUTPUT

# === Runtime State ===
rtd = None
_last_error = None
_last_success = None
_total_reads = 0
_successful_reads = 0
_failures = 0

# === Fallback Configuration ===
FALLBACK_TEMP_C = 39.0  # 103°F


def initialize_sensor():
    global rtd
    try:
        if not spi.try_lock():
            spi.try_lock()
        rtd = adafruit_max31865.MAX31865(spi, cs, wires=RTD_WIRES)
        rtd.clear_faults()
        print("✅ RTD sensor initialized successfully")
        return True
    except Exception as e:
        print(f"❌ RTD initialization failed: {e}")
        return False
    finally:
        spi.unlock()


def read_temperature():
    global _last_error, _last_success, _total_reads, _successful_reads, _failures
    _total_reads += 1
    try:
        temp = rtd.temperature
        _successful_reads += 1
        _last_success = time.monotonic()
        _last_error = None
        return temp
    except Exception as e:
        _failures += 1
        _last_error = str(e)
        print(f"❌ RTD read error: {e}")
        return None


def get_temperature_status():
    return {
        "sensor_initialized": rtd is not None,
        "last_error": _last_error,
        "total_reads": _total_reads,
        "successful_reads": _successful_reads,
        "failures": _failures,
        "time_since_last_success": (
            time.monotonic() - _last_success if _last_success else None
        ),
        "fallback_temp": FALLBACK_TEMP_C,
        "health_status": _get_health_status(),
    }


def _get_health_status():
    if rtd is None:
        return "not_initialized"
    elif _failures > 10:
        return "degraded"
    elif _last_error:
        return "warning"
    else:
        return "healthy"


def get_fallback_temperature():
    return FALLBACK_TEMP_C


def reset_temperature_sensor():
    """Reinitialize sensor and reset statistics"""
    global rtd, _last_error, _total_reads, _successful_reads, _failures
    print("🔄 Resetting RTD sensor state...")
    rtd = None
    _last_error = None
    _total_reads = 0
    _successful_reads = 0
    _failures = 0
    return initialize_sensor()
