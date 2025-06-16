# lib/utilities/i2c_reset.py
"""
I2C Reset Functions - Extracted from main code for better organization
Simple module with no dependencies to avoid circular imports
"""
import time
import busio
import board
import microcontroller


def safe_i2c_reset_with_timeout(timeout_seconds=10, watchdog=None):
    """
    Attempt I2C reset with timeout protection and watchdog feeding
    Moved from main code for better organization
    """
    start_time = time.monotonic()
    print(f"🔄 Starting I2C reset with {timeout_seconds}s timeout...")
    try:
        # Feed watchdog before starting
        if watchdog:
            watchdog.feed()

        # Check timeout before each operation
        if time.monotonic() - start_time > timeout_seconds:
            raise Exception("I2C reset timeout - forcing restart")

        if hasattr(board, "I2C"):
            try:
                board.I2C().deinit()
                print("   Board I2C deinitialized")
                if watchdog:
                    watchdog.feed()
            except Exception as e:
                print(f"   Board I2C deinit error: {e}")

        # Check timeout again
        if time.monotonic() - start_time > timeout_seconds:
            raise Exception("I2C reset timeout - forcing restart")

        # Create and immediately deinit temp I2C
        temp_i2c = busio.I2C(board.SCL, board.SDA)
        temp_i2c.deinit()
        print("   Temp I2C created and deinitialized")
        if watchdog:
            watchdog.feed()

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
    """
    Emergency I2C cleanup on errors
    Moved from main code for better organization
    """
    try:
        print("🚨 Emergency I2C cleanup...")
        if hasattr(board, "I2C"):
            board.I2C().deinit()
            time.sleep(0.5)
        print("   Emergency cleanup complete")
    except:
        pass  # If this fails, we're already in trouble