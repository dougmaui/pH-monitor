# lib/core/calibration_button_manager.py
"""
Calibration Button Manager Module
Handles calibration button detection and mode triggering
Stage 1: Button setup and detection testing only
"""
import time
import board
import digitalio


class CalibrationButtonManager:
    """
    Manages calibration button detection and mode triggering
    Non-blocking integration with main loop
    """

    def __init__(self, state_manager=None):
        self.state_manager = state_manager

        # Button setup
        self.next_button = None
        self.abort_button = None

        # State tracking
        self.buttons_initialized = False
        self.calibration_mode_active = False
        self.last_button_check = 0
        self.button_check_interval = 0.1  # Check buttons every 100ms

        # Button press tracking (for debouncing)
        self.next_pressed = False
        self.abort_pressed = False
        self.both_pressed = False
        self.last_next_state = True  # True = not pressed (pull-up)
        self.last_abort_state = True
        self.press_start_time = 0
        self.min_press_duration = 0.2  # Minimum press duration for detection

        # Statistics
        self.next_press_count = 0
        self.abort_press_count = 0
        self.calibration_trigger_count = 0

    def initialize_buttons(self):
        """Initialize calibration button hardware"""
        try:
            print("🔘 Initializing calibration buttons...")

            # Setup NEXT button (D11)
            self.next_button = digitalio.DigitalInOut(board.D11)
            self.next_button.direction = digitalio.Direction.INPUT
            self.next_button.pull = digitalio.Pull.UP  # Normally HIGH, press = LOW

            # Setup ABORT button (D13)
            self.abort_button = digitalio.DigitalInOut(board.D13)
            self.abort_button.direction = digitalio.Direction.INPUT
            self.abort_button.pull = digitalio.Pull.UP  # Normally HIGH, press = LOW

            # Initialize state tracking
            self.last_next_state = self.next_button.value
            self.last_abort_state = self.abort_button.value

            self.buttons_initialized = True
            print("   ✅ Calibration buttons initialized:")
            print("      D11 = NEXT button")
            print("      D13 = ABORT button")
            print("      Both pressed together = Enter calibration mode")

            if self.state_manager:
                self.state_manager.register_component("calibration_buttons")
                self.state_manager.update_component_health(
                    "calibration_buttons", "healthy"
                )

            return True

        except Exception as e:
            print(f"   ❌ Calibration button initialization failed: {e}")
            self.buttons_initialized = False

            if self.state_manager:
                self.state_manager.update_component_health(
                    "calibration_buttons", "failed", str(e)
                )

            return False

    def check_buttons(self):
        """
        Check button states (non-blocking)
        Call this from main loop every cycle
        """
        current_time = time.monotonic()

        # Rate limit button checking
        if current_time - self.last_button_check < self.button_check_interval:
            return False

        self.last_button_check = current_time

        if not self.buttons_initialized:
            return False

        try:
            # Read current button states
            next_current = self.next_button.value
            abort_current = self.abort_button.value

            # Detect button press changes (with debouncing)
            next_pressed_now = not next_current  # Invert because pull-up
            abort_pressed_now = not abort_current

            # NEXT button press detection
            if next_pressed_now and not self.next_pressed:
                # Button just pressed
                self.next_pressed = True
                self.press_start_time = current_time
                print("🔘 NEXT button pressed")

            elif not next_pressed_now and self.next_pressed:
                # Button just released
                press_duration = current_time - self.press_start_time
                if press_duration >= self.min_press_duration:
                    self.next_press_count += 1
                    print(
                        f"   ✅ NEXT button released (duration: {press_duration:.2f}s)"
                    )
                else:
                    print(
                        f"   ⚠️ NEXT button too short (duration: {press_duration:.2f}s)"
                    )
                self.next_pressed = False

            # ABORT button press detection
            if abort_pressed_now and not self.abort_pressed:
                # Button just pressed
                self.abort_pressed = True
                self.press_start_time = current_time
                print("🔘 ABORT button pressed")

            elif not abort_pressed_now and self.abort_pressed:
                # Button just released
                press_duration = current_time - self.press_start_time
                if press_duration >= self.min_press_duration:
                    self.abort_press_count += 1
                    print(
                        f"   ✅ ABORT button released (duration: {press_duration:.2f}s)"
                    )
                else:
                    print(
                        f"   ⚠️ ABORT button too short (duration: {press_duration:.2f}s)"
                    )
                self.abort_pressed = False

            # Both buttons pressed together detection
            both_pressed_now = next_pressed_now and abort_pressed_now

            if both_pressed_now and not self.both_pressed:
                # Both buttons just pressed together
                self.both_pressed = True
                self.press_start_time = current_time
                print("🔘🔘 BOTH buttons pressed together!")

            elif not both_pressed_now and self.both_pressed:
                # At least one button released
                press_duration = current_time - self.press_start_time
                if press_duration >= self.min_press_duration:
                    self.calibration_trigger_count += 1
                    print(
                        f"   🎯 CALIBRATION MODE TRIGGER! (duration: {press_duration:.2f}s)"
                    )
                    print(f"   📊 This would start calibration mode now...")

                    # This is where we'll trigger actual calibration later
                    return "calibration_trigger"
                else:
                    print(
                        f"   ⚠️ Both buttons too short (duration: {press_duration:.2f}s)"
                    )
                self.both_pressed = False

            # Update health status
            if self.state_manager:
                self.state_manager.update_component_health(
                    "calibration_buttons", "healthy"
                )

            return False  # No calibration trigger

        except Exception as e:
            print(f"   ❌ Button check error: {e}")
            if self.state_manager:
                self.state_manager.update_component_health(
                    "calibration_buttons", "degraded", str(e)
                )
            return False

    def get_button_states(self):
        """Get current button states for debugging"""
        if not self.buttons_initialized:
            return None

        try:
            return {
                "next_raw": self.next_button.value,
                "abort_raw": self.abort_button.value,
                "next_pressed": not self.next_button.value,  # Invert for pull-up
                "abort_pressed": not self.abort_button.value,
                "both_pressed": (not self.next_button.value)
                and (not self.abort_button.value),
            }
        except:
            return None

    def get_statistics(self):
        """Get button press statistics"""
        return {
            "initialized": self.buttons_initialized,
            "next_press_count": self.next_press_count,
            "abort_press_count": self.abort_press_count,
            "calibration_triggers": self.calibration_trigger_count,
            "calibration_mode_active": self.calibration_mode_active,
            "last_check_age": (
                time.monotonic() - self.last_button_check
                if self.last_button_check
                else None
            ),
        }

    def reset_statistics(self):
        """Reset button press statistics"""
        self.next_press_count = 0
        self.abort_press_count = 0
        self.calibration_trigger_count = 0
        print("🔘 Button statistics reset")

    def cleanup(self):
        """Clean up button resources"""
        try:
            if self.next_button:
                self.next_button.deinit()
            if self.abort_button:
                self.abort_button.deinit()
            print("🔘 Calibration buttons cleaned up")
        except Exception as e:
            print(f"   ⚠️ Button cleanup error: {e}")


# Convenience function for easy integration
def create_calibration_button_manager(state_manager=None):
    """Create and initialize calibration button manager"""
    manager = CalibrationButtonManager(state_manager)
    manager.initialize_buttons()
    return manager
