# lib/calibration/calibration_manager.py
"""
Simple Calibration Manager - Everything in one place
"""
import time


class CalibrationManager:
    def __init__(
        self,
        ph_sensor,
        display,
        next_pin,
        abort_pin,
        safe_read_ph,
        watchdog_enabled=False,
        wdt=None,
    ):
        self.ph_sensor = ph_sensor
        self.display = display
        self.next_pin = next_pin
        self.abort_pin = abort_pin
        self.safe_read_ph = safe_read_ph
        self.watchdog_enabled = watchdog_enabled
        self.wdt = wdt

    def run_calibration(self):
        """Simple calibration - just test buttons for now"""
        print("=== SIMPLE pH CALIBRATION ===")
        print("D11 = Next, D13 = Abort")
        print("Testing for 15 seconds...")

        start_time = time.monotonic()

        while time.monotonic() - start_time < 15:
            # Feed watchdog
            if self.watchdog_enabled and self.wdt:
                self.wdt.feed()

            # Check buttons
            if not self.next_pin.value:
                print("✅ NEXT button pressed!")
                time.sleep(0.5)  # Simple debounce

            if not self.abort_pin.value:
                print("❌ ABORT button pressed - exiting!")
                return False

            time.sleep(0.1)

        print("✅ Button test complete - calibration would run here")
        return True
