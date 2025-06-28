# lib/startup/hardware_bootstrap.py
"""
Hardware Bootstrap Module
Centralized hardware initialization for ESP32-S3 with robust error handling
Extracted from main code.py for better organization and reusability
"""
import time
import board
import digitalio
import neopixel
import busio
import microcontroller
import watchdog


def initialize_hardware_foundation():
    """
    Initialize all hardware foundation components

    Returns:
        tuple: (watchdog_enabled, wdt, i2c, spi, pixel, shutdown_pin)
    """
    print("🚀 Initializing hardware foundation...")

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
        wdt = None

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
                print(
                    f"   ❌ SPI initialization failed after {attempt + 1} attempts: {e}"
                )
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

    print("✅ Hardware foundation initialization complete")

    return watchdog_enabled, wdt, i2c, spi, pixel, shutdown_pin
