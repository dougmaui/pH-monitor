# lib/calibration/calibration_manager.py
"""
Display-Oriented pH Calibration Manager
3-point calibration with EZO commands and display feedback
"""
import time


class CalibrationManager:
    def __init__(
        self,
        ph_sensor,
        display,
        ph_label,
        temp_c_label,
        temp_f_label,
        rssi_label,
        time_label,
        next_pin,
        abort_pin,
        safe_read_ph,
        safe_read_temperature,
        pixel,
        watchdog_enabled=False,
        wdt=None,
    ):
        self.ph_sensor = ph_sensor
        self.display = display
        self.ph_label = ph_label
        self.temp_c_label = temp_c_label
        self.temp_f_label = temp_f_label
        self.rssi_label = rssi_label
        self.time_label = time_label
        self.next_pin = next_pin
        self.abort_pin = abort_pin
        self.safe_read_ph = safe_read_ph
        self.safe_read_temperature = safe_read_temperature
        self.pixel = pixel
        self.watchdog_enabled = watchdog_enabled
        self.wdt = wdt

        # Calibration sequence (Atlas Scientific order)
        self.calibration_steps = [
            {
                "name": "mid",
                "ph_target": 7.00,
                "buffer_name": "pH 7.00 Buffer",
                "command": "Cal,mid,7.00",
                "step_num": 1,
            },
            {
                "name": "low",
                "ph_target": 4.00,
                "buffer_name": "pH 4.00 Buffer",
                "command": "Cal,low,4.00",
                "step_num": 2,
            },
            {
                "name": "high",
                "ph_target": 10.00,
                "buffer_name": "pH 10.00 Buffer",
                "command": "Cal,high,10.00",
                "step_num": 3,
            },
        ]

    def run_calibration(self):
        """Run complete 3-point pH calibration using display"""
        try:
            print("🖥️ Starting display-oriented calibration...")
            print(f"   Display available: {self.display is not None}")
            print(
                f"   Labels available: {all([self.ph_label, self.temp_c_label, self.temp_f_label, self.rssi_label, self.time_label])}"
            )

            # Clear display and show welcome
            self._update_display(
                line1="pH CALIBRATION",
                line2="3-Point Calibration",
                line3="Press NEXT to begin",
                line4="Press ABORT to cancel",
                line5="",
            )

            self.pixel[0] = (0, 255, 255)  # Cyan = Calibration mode
            print("🔵 NeoPixel set to CYAN - calibration mode active")

            # Wait for user to start
            print("⏳ Waiting for NEXT button to start calibration...")
            if not self._wait_for_next("Ready to start?"):
                return False
                return False

            # Run each calibration step
            for step in self.calibration_steps:
                if not self._run_calibration_step(step):
                    return False

            # Show completion
            self._show_completion()
            return True

        except Exception as e:
            self._show_error(f"Error: {e}")
            return False

    def _run_calibration_step(self, step):
        """Run a single calibration step"""
        step_num = step["step_num"]
        buffer_name = step["buffer_name"]
        ph_target = step["ph_target"]
        command = step["command"]

        # Show step instructions
        self._update_display(
            line1=f"STEP {step_num}/3",
            line2=f"Place probe in",
            line3=buffer_name,
            line4="Waiting for stable reading...",
            line5="",
        )

        self.pixel[0] = (255, 255, 0)  # Yellow = Working

        # Monitor for stable reading
        stable_readings = 0
        required_stable = 3  # Need 3 consecutive stable readings
        last_temp_update = 0
        last_ph_update = 0

        while True:
            current_time = time.monotonic()

            # Feed watchdog
            if self.watchdog_enabled and self.wdt:
                self.wdt.feed()

            # Check for abort
            if not self.abort_pin.value:
                self._show_cancelled()
                return False

            # Update temperature every 5 seconds
            if current_time - last_temp_update >= 5.0:
                temp_info = self._get_temperature_info()
                last_temp_update = current_time
            else:
                temp_info = self._get_temperature_info()  # Use cached if available

            # Update pH reading every 2 seconds
            if current_time - last_ph_update >= 2.0:
                try:
                    # Get current pH reading
                    current_ph = self.safe_read_ph()

                    if isinstance(current_ph, (int, float)):
                        # Check if reading is close to target
                        if abs(current_ph - ph_target) <= 0.3:
                            stable_readings += 1
                            if stable_readings >= required_stable:
                                # Stable! Ready to calibrate
                                self._update_display(
                                    line1=f"STEP {step_num}/3 - STABLE",
                                    line2=f"pH: {current_ph:.2f}",
                                    line3=f"Target: {ph_target:.2f}",
                                    line4="Press NEXT to calibrate",
                                    line5=temp_info,
                                )
                                self.pixel[0] = (0, 255, 0)  # Green = Ready

                                # Wait for NEXT button
                                if self._wait_for_next("Calibrate now?"):
                                    # Execute calibration
                                    if self._execute_calibration(step, current_ph):
                                        return True  # Success, move to next step
                                    else:
                                        # Calibration failed, retry this step
                                        stable_readings = 0
                                        continue
                                else:
                                    return False  # Aborted
                            else:
                                # Still stabilizing
                                self._update_display(
                                    line1=f"STEP {step_num}/3",
                                    line2=f"pH: {current_ph:.2f}",
                                    line3=f"Stabilizing... {stable_readings}/{required_stable}",
                                    line4="Wait for stable reading",
                                    line5=temp_info,
                                )
                        else:
                            # Not close to target
                            stable_readings = 0
                            self._update_display(
                                line1=f"STEP {step_num}/3",
                                line2=f"pH: {current_ph:.2f}",
                                line3=f"Target: {ph_target:.2f}",
                                line4="Adjust buffer solution",
                                line5=temp_info,
                            )
                    else:
                        # pH reading error
                        stable_readings = 0
                        self._update_display(
                            line1=f"STEP {step_num}/3",
                            line2="pH: ERROR",
                            line3="Check probe connection",
                            line4="",
                            line5=temp_info,
                        )

                    last_ph_update = current_time

                except Exception as e:
                    self._update_display(
                        line1=f"STEP {step_num}/3",
                        line2="pH: ERROR",
                        line3=f"Error: {e}",
                        line4="",
                        line5="",
                    )

            time.sleep(0.2)  # Small delay

    def _execute_calibration(self, step, current_ph):
        """Execute the actual calibration command"""
        command = step["command"]
        step_num = step["step_num"]

        # Show calibrating status
        self._update_display(
            line1=f"STEP {step_num}/3",
            line2="CALIBRATING...",
            line3="Please wait",
            line4="Do not move probe",
            line5="",
        )

        self.pixel[0] = (255, 0, 255)  # Magenta = Calibrating

        try:
            # Send calibration command to EZO
            self.ph_sensor.send_command(command)

            # Wait for processing (EZO needs time)
            for i in range(20):  # 4 seconds total
                if self.watchdog_enabled and self.wdt:
                    self.wdt.feed()
                time.sleep(0.2)

            # Check calibration result
            response = self.ph_sensor.query("Cal,?")

            # Show result
            if "Cal," in response:
                self._update_display(
                    line1=f"STEP {step_num}/3",
                    line2="✅ SUCCESS!",
                    line3=f"Calibrated at pH {current_ph:.2f}",
                    line4="Press NEXT to continue",
                    line5=f"Status: {response.strip()}",
                )
                self.pixel[0] = (0, 255, 0)  # Green = Success

                # Wait for NEXT to continue
                return self._wait_for_next("Continue?")
            else:
                self._update_display(
                    line1=f"STEP {step_num}/3",
                    line2="❌ FAILED",
                    line3="Calibration unsuccessful",
                    line4="Press NEXT to retry",
                    line5=f"Response: {response.strip()}",
                )
                self.pixel[0] = (255, 0, 0)  # Red = Failed

                # Wait for NEXT to retry
                return False  # Will retry this step

        except Exception as e:
            self._update_display(
                line1=f"STEP {step_num}/3",
                line2="❌ ERROR",
                line3=f"Command failed: {e}",
                line4="Press NEXT to retry",
                line5="",
            )
            self.pixel[0] = (255, 0, 0)  # Red = Error
            return False

    def _show_completion(self):
        """Show calibration completion screen"""
        try:
            # Get final calibration status
            cal_status = self.ph_sensor.query("Cal,?")

            self._update_display(
                line1="🎉 COMPLETE!",
                line2="3-Point Calibration",
                line3="Successfully finished",
                line4="System will restart",
                line5=f"Final: {cal_status.strip()}",
            )

            # Flash green
            for _ in range(6):
                self.pixel[0] = (0, 255, 0) if _ % 2 else (0, 0, 0)
                time.sleep(0.5)

        except Exception as e:
            self._update_display(
                line1="🎉 COMPLETE!",
                line2="Calibration finished",
                line3="System will restart",
                line4="",
                line5="",
            )

    def _show_cancelled(self):
        """Show calibration cancelled screen"""
        self._update_display(
            line1="❌ CANCELLED",
            line2="Calibration aborted",
            line3="No changes made",
            line4="System will restart",
            line5="",
        )
        self.pixel[0] = (255, 0, 0)  # Red
        time.sleep(3)

    def _show_error(self, error_msg):
        """Show error screen"""
        self._update_display(
            line1="💥 ERROR",
            line2="Calibration failed",
            line3=error_msg,
            line4="System will restart",
            line5="",
        )
        self.pixel[0] = (255, 0, 0)  # Red
        time.sleep(3)

    def _wait_for_next(self, prompt):
        """Wait for NEXT button press, return False if ABORT pressed"""
        # Wait for button release first
        while not self.next_pin.value or not self.abort_pin.value:
            if self.watchdog_enabled and self.wdt:
                self.wdt.feed()
            time.sleep(0.1)

        # Wait for button press
        while True:
            if self.watchdog_enabled and self.wdt:
                self.wdt.feed()

            if not self.next_pin.value:  # NEXT pressed
                return True
            if not self.abort_pin.value:  # ABORT pressed
                return False

            time.sleep(0.1)

    def _get_temperature_info(self):
        """Get current temperature info for display"""
        try:
            temp_result = self.safe_read_temperature()
            if isinstance(temp_result, tuple):
                temp_c, temp_source = temp_result
            else:
                temp_c = temp_result
                temp_source = "unknown"
            if temp_c:
                temp_f = temp_c * 9 / 5 + 32
                return f"Temp: {temp_c:.1f}°C ({temp_f:.1f}°F)"
            else:
                return "Temp: --"
        except:
            return "Temp: Error"

    def _update_display(self, line1, line2, line3, line4, line5):
        """Update all display labels"""
        try:
            print(f"🖥️ Updating display:")
            print(f"   Line 1: {line1}")
            print(f"   Line 2: {line2}")
            print(f"   Line 3: {line3}")
            print(f"   Line 4: {line4}")
            print(f"   Line 5: {line5}")

            self.ph_label.text = line1
            self.temp_c_label.text = line2
            self.temp_f_label.text = line3
            self.rssi_label.text = line4
            self.time_label.text = line5

            print("✅ Display updated successfully")
        except Exception as e:
            print(f"❌ Display update error: {e}")
            print(
                f"   Labels available: ph={self.ph_label is not None}, temp_c={self.temp_c_label is not None}"
            )
            import traceback

            traceback.print_exception(e)
