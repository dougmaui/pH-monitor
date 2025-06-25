# lib/calibration/calibration_system.py
"""
pH Calibration System Module
Complete calibration interface matching main system architecture
Uses same RTD and pH sensor setup as main monitoring system
"""

import time
import board
import digitalio
import busio
import sys


def run_calibration_mode():
    """Main calibration system entry point"""
    print("🧪 CALIBRATION SYSTEM MODULE ACTIVE")

    # IMMEDIATE: Claim display before console can take it
    try:
        print("   🚀 CLAIMING DISPLAY IMMEDIATELY...")

        # Import displayio first
        import displayio

        # AGGRESSIVE: Disable console display completely
        import supervisor

        supervisor.runtime.autoreload = False

        displayio.release_displays()  # Release any console display
        print("   ✅ Displays released from console")

        # Create SPI bus - SAME setup as main system
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        from fourwire import FourWire

        display_bus = FourWire(spi, command=board.D10, chip_select=board.D9, reset=None)

        # Create display driver - SAME as main system
        import adafruit_ili9341

        display = adafruit_ili9341.ILI9341(display_bus, width=480, height=320)

        print("   ✅ Display claimed and locked - console disabled")

    except Exception as e:
        print(f"   ❌ Display setup failed: {e}")
        # Clean up SPI on failure
        try:
            if "spi" in locals():
                spi.deinit()
        except:
            pass
        return False

    # === SPLASH SCREEN ===
    success = _show_calibration_splash(display)
    if not success:
        return False

    # === OPERATING SCREEN ===
    main_group, labels = _create_operating_screen(display)
    if not main_group:
        return False

    # === SENSOR INITIALIZATION - SAME AS MAIN SYSTEM ===
    sensors = _initialize_sensors(spi)

    # === MAIN CALIBRATION LOOP ===
    return _run_calibration_loop(display, main_group, labels, sensors)


def _show_calibration_splash(display):
    """Show 10-second calibration splash screen"""
    try:
        print("   Creating calibration splash screen...")

        # FIXED: Import displayio at function top
        import displayio
        import terminalio
        from adafruit_display_text import label

        # Create splash display group
        splash = displayio.Group()

        # Purple background for calibration
        color_bitmap = displayio.Bitmap(480, 320, 1)
        color_palette = displayio.Palette(1)
        color_palette[0] = 0x800080  # Purple

        bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette)
        splash.append(bg_sprite)

        # Title text
        title_label = label.Label(
            terminalio.FONT, text="pH CALIBRATION", color=0xFFFFFF, x=100, y=120
        )
        title_label.scale = 3
        splash.append(title_label)

        # Module info
        module_label = label.Label(
            terminalio.FONT, text="MODULE ACTIVE", color=0x00FF00, x=150, y=160
        )
        module_label.scale = 2
        splash.append(module_label)

        # Status
        status_label = label.Label(
            terminalio.FONT,
            text="Initializing sensors...",
            color=0xFFFF00,
            x=140,
            y=220,
        )
        splash.append(status_label)

        # Show splash
        display.root_group = splash
        print("   ✅ Calibration splash displayed")

        # 10-second countdown
        splash_start = time.monotonic()
        splash_duration = 10.0

        while time.monotonic() - splash_start < splash_duration:
            remaining = splash_duration - (time.monotonic() - splash_start)
            status_label.text = f"Loading calibration interface... {remaining:.0f}s"

            # Re-assert display control
            if int(remaining) % 2 == 0:
                display.root_group = splash

            time.sleep(0.1)

        print("   🎨 Splash complete, switching to operating screen...")
        return True

    except Exception as e:
        print(f"   ❌ Splash screen failed: {e}")
        return False


def _create_operating_screen(display):
    """Create the main calibration operating screen"""
    try:
        print("   Creating calibration operating screen...")

        import displayio
        import terminalio
        from adafruit_display_text import label

        # Create main display group
        main_group = displayio.Group()

        # Dark blue background
        color_bitmap = displayio.Bitmap(480, 320, 1)
        color_palette = displayio.Palette(1)
        color_palette[0] = 0x001130
        bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette)
        main_group.append(bg_sprite)

        # Title
        title_label = label.Label(
            terminalio.FONT, text="pH CALIBRATION MODULE", color=0x00FF00, x=20, y=30
        )
        title_label.scale = 2
        main_group.append(title_label)

        # Current readings section
        readings_label = label.Label(
            terminalio.FONT, text="CURRENT READINGS:", color=0xFFFF00, x=20, y=80
        )
        main_group.append(readings_label)

        # Sensor readings (will be updated with real data)
        ph_label = label.Label(
            terminalio.FONT, text="pH: Initializing...", color=0xFFFFFF, x=30, y=110
        )
        ph_label.scale = 2
        main_group.append(ph_label)

        temp_label = label.Label(
            terminalio.FONT, text="Temp: Initializing...", color=0xFFFFFF, x=30, y=140
        )
        temp_label.scale = 2
        main_group.append(temp_label)

        cal_status_label = label.Label(
            terminalio.FONT,
            text="Cal Status: Initializing...",
            color=0x00FFFF,
            x=30,
            y=170,
        )
        main_group.append(cal_status_label)

        # Instructions
        instructions = [
            "INSTRUCTIONS:",
            "1. Place probe in pH 7.0 buffer",
            "2. Wait for stable reading",
            "3. Press NEXT when ready (not active yet)",
            "",
            "Power off to exit calibration",
        ]

        for i, instruction in enumerate(instructions):
            color = 0xFFFF00 if i == 0 else 0xFFFFFF if instruction else 0xFF8888
            if "not active" in instruction:
                color = 0x888888
            if "Power off" in instruction:
                color = 0xFF8888

            inst_label = label.Label(
                terminalio.FONT, text=instruction, color=color, x=20, y=210 + (i * 15)
            )
            main_group.append(inst_label)

        # Set operating screen
        display.root_group = main_group
        print("   ✅ Operating screen displayed")

        # Return screen and key labels for updates
        labels = {"ph": ph_label, "temp": temp_label, "cal_status": cal_status_label}

        return main_group, labels

    except Exception as e:
        print(f"   ❌ Operating screen creation failed: {e}")
        return None, None


def _initialize_sensors(spi):
    """Initialize calibration sensors - SAME setup as main system"""
    print("   🔧 Initializing sensors using main system architecture...")

    sensors = {
        "rtd_working": False,
        "rtd_sensor": None,
        "ph_working": False,
        "ph_sensor": None,
    }

    # Setup I2C bus - SAME as main system
    try:
        print("   📡 Setting up I2C bus...")
        i2c = busio.I2C(board.SCL, board.SDA)
        print("   ✅ I2C bus ready")
    except Exception as e:
        print(f"   ❌ I2C setup failed: {e}")
        return sensors

    # RTD Temperature Sensor - SAME setup as main system
    try:
        print("   🌡️ Initializing RTD sensor (same as main system)...")
        from lib.sensors.rtd_sensor import RTDSensor

        # Create RTD sensor with SAME parameters as main system
        rtd_sensor = RTDSensor(spi, cs_pin=board.D12, rtd_wires=3)
        rtd_working = rtd_sensor.initialize()

        if rtd_working:
            # Test reading using the proven read_temperature() method
            temp_c, temp_source = rtd_sensor.read_temperature()
            if temp_c is not None:
                print(f"   ✅ RTD working: {temp_c:.3f}°C from {temp_source}")
                sensors["rtd_working"] = True
                sensors["rtd_sensor"] = rtd_sensor
            else:
                print(f"   ❌ RTD read failed: {temp_source}")
        else:
            print("   ❌ RTD initialization failed")

    except Exception as e:
        print(f"   ❌ RTD initialization error: {e}")
        print("   📝 Using fallback temperature for calibration")

    # pH Sensor - SAME setup as main system
    try:
        print("   🧪 Initializing pH sensor (same as main system)...")
        from lib.sensors.ph_sensor import AtlasScientificPH

        # Create pH sensor with SAME parameters as main system
        ph_sensor = AtlasScientificPH(i2c)

        # FIXED: Use simple initialization like main system
        # Test basic functionality instead of looking for initialize_sensor method
        test_ph = ph_sensor.read_ph()
        device_info = ph_sensor.get_info()

        # If we can read pH and get info, sensor is working
        if test_ph and device_info:
            print(f"   ✅ pH working: {test_ph}")
            print(f"   📊 pH device: {device_info}")
            sensors["ph_working"] = True
            sensors["ph_sensor"] = ph_sensor
        else:
            print("   ❌ pH sensor not responding")

    except Exception as e:
        print(f"   ❌ pH initialization error: {e}")

    rtd_status = "✅" if sensors["rtd_working"] else "❌"
    ph_status = "✅" if sensors["ph_working"] else "❌"
    print(f"   📊 Calibration sensors ready: RTD={rtd_status}, pH={ph_status}")

    return sensors


def _run_calibration_loop(display, main_group, labels, sensors):
    """Main calibration loop with sensor readings and calibration sequence"""
    print("   🔒 Starting calibration loop...")
    print("   💡 INSTRUCTIONS:")
    print("      NEXT (D13): Advance through calibration steps")
    print("      ABORT (D11): Clear calibration and exit")

    # Calibration state
    calibration_step = 0
    calibration_steps = [
        {
            "name": "pH 7.0",
            "command": "Cal,mid,7.00",
            "instruction": "Place probe in pH 7.0 buffer",
        },
        {
            "name": "pH 4.0",
            "command": "Cal,low,4.00",
            "instruction": "Place probe in pH 4.0 buffer",
        },
        {
            "name": "pH 10.0",
            "command": "Cal,high,10.00",
            "instruction": "Place probe in pH 10.0 buffer",
        },
        {"name": "Complete", "command": None, "instruction": "Calibration finished"},
    ]

    # Button setup
    next_button = digitalio.DigitalInOut(board.D13)
    next_button.direction = digitalio.Direction.INPUT
    next_button.pull = digitalio.Pull.UP

    abort_button = digitalio.DigitalInOut(board.D11)
    abort_button.direction = digitalio.Direction.INPUT
    abort_button.pull = digitalio.Pull.UP

    # Button state tracking
    last_next_press = 0
    last_abort_press = 0
    button_debounce = 0.5  # 500ms debounce

    try:
        loop_count = 0
        last_sensor_update = 0
        last_instruction_update = 0

        # Show initial instruction
        _update_calibration_instruction(labels, calibration_steps[calibration_step])

        while True:  # Calibration mode
            loop_count += 1
            current_time = time.monotonic()

            # Re-assert display control every 10 loops
            if loop_count % 10 == 0:
                display.root_group = main_group

            # Check NEXT button (D13)
            if (
                not next_button.value
                and (current_time - last_next_press) > button_debounce
            ):
                last_next_press = current_time

                if calibration_step < len(calibration_steps) - 1:
                    # Perform calibration step
                    result = _perform_calibration_step(
                        sensors, calibration_steps[calibration_step], labels
                    )
                    if result:
                        calibration_step += 1
                        _update_calibration_instruction(
                            labels, calibration_steps[calibration_step]
                        )
                        if calibration_step >= len(calibration_steps) - 1:
                            # Calibration complete
                            return _finish_calibration(sensors, labels)
                else:
                    # Final step - exit
                    return _finish_calibration(sensors, labels)

            # Check ABORT button (D11)
            if (
                not abort_button.value
                and (current_time - last_abort_press) > button_debounce
            ):
                last_abort_press = current_time
                return _abort_calibration(sensors, labels)

            # Update instruction display every 5 seconds
            if current_time - last_instruction_update >= 5.0:
                last_instruction_update = current_time
                _update_calibration_instruction(
                    labels, calibration_steps[calibration_step]
                )

            # Update sensor readings every 2 seconds
            if current_time - last_sensor_update >= 2.0:
                last_sensor_update = current_time

                # Temperature reading - SAME method as main system
                if sensors["rtd_working"] and sensors["rtd_sensor"]:
                    try:
                        temp_c, temp_source = sensors["rtd_sensor"].read_temperature()
                        if temp_c is not None:
                            labels["temp"].text = (
                                f"Temp: {temp_c:.3f} °C ({temp_source})"
                            )

                            # Send temperature compensation to pH sensor
                            if sensors["ph_working"] and sensors["ph_sensor"]:
                                sensors["ph_sensor"].set_temp_compensation(temp_c)
                        else:
                            labels["temp"].text = f"Temp: ERROR ({temp_source})"
                    except Exception as e:
                        print(f"   ⚠️ RTD read error: {e}")
                        labels["temp"].text = "Temp: RTD ERROR"
                else:
                    labels["temp"].text = "Temp: 39.000 °C (fallback)"

                # pH reading - SAME method as main system
                if sensors["ph_working"] and sensors["ph_sensor"]:
                    try:
                        ph_value = sensors["ph_sensor"].read_ph()
                        if isinstance(ph_value, (int, float)):
                            labels["ph"].text = f"pH: {ph_value:.3f}"
                        else:
                            labels["ph"].text = f"pH: {ph_value}"

                        # Calibration status - SAME method as main system
                        cal_status = sensors["ph_sensor"].query("Cal,?")
                        labels["cal_status"].text = f"Cal Status: {cal_status.strip()}"

                    except Exception as e:
                        print(f"   ⚠️ pH read error: {e}")
                        labels["ph"].text = "pH: SENSOR ERROR"
                        labels["cal_status"].text = "Cal Status: ERROR"
                else:
                    labels["ph"].text = "pH: 7.000 (fallback)"
                    labels["cal_status"].text = "Cal Status: NO SENSOR"

                # Status logging every 20 seconds
                if loop_count % 100 == 0:
                    rtd_ok = "✅" if sensors["rtd_working"] else "❌"
                    ph_ok = "✅" if sensors["ph_working"] else "❌"
                    print(
                        f"   📊 Calibration Loop {loop_count}: RTD={rtd_ok}, pH={ph_ok}"
                    )

            time.sleep(0.1)  # 100ms loop

    except KeyboardInterrupt:
        print("   🛑 Calibration interrupted")
        return _cleanup_and_exit()
    except Exception as e:
        print(f"   ❌ Calibration loop error: {e}")
        return _cleanup_and_exit()


def _update_calibration_instruction(labels, step_info):
    """Update the instruction display for current calibration step"""
    step_name = step_info["name"]
    instruction = step_info["instruction"]

    # Update instruction labels
    labels["temp"].text = f"STEP: {step_name}"
    if "Complete" in step_name:
        labels["ph"].text = "🎉 Press NEXT to finish"
    else:
        labels["ph"].text = f"📍 {instruction}"


def _perform_calibration_step(sensors, step_info, labels):
    """Perform a calibration step with the pH sensor"""
    if not sensors["ph_working"] or not sensors["ph_sensor"]:
        labels["cal_status"].text = "❌ pH sensor not available"
        return False

    step_name = step_info["name"]
    command = step_info["command"]

    print(f"🧪 Performing calibration step: {step_name}")
    labels["cal_status"].text = f"⏳ Calibrating {step_name}..."

    try:
        # Send calibration command to EZO
        sensors["ph_sensor"].send_command(command)
        time.sleep(1.6)  # EZO processing time

        # Query calibration status
        cal_status = sensors["ph_sensor"].query("Cal,?")
        labels["cal_status"].text = f"✅ {step_name}: {cal_status.strip()}"

        print(f"   ✅ {step_name} complete: {cal_status.strip()}")
        return True

    except Exception as e:
        print(f"   ❌ Calibration step failed: {e}")
        labels["cal_status"].text = f"❌ {step_name} failed"
        return False


def _finish_calibration(sensors, labels):
    """Complete calibration and prepare for exit"""
    print("🎉 CALIBRATION SEQUENCE COMPLETE!")

    # Get final calibration status
    if sensors["ph_working"] and sensors["ph_sensor"]:
        try:
            final_status = sensors["ph_sensor"].query("Cal,?")
            print(f"   📊 Final calibration status: {final_status.strip()}")
            labels["cal_status"].text = f"🎉 DONE: {final_status.strip()}"
        except Exception as e:
            print(f"   ⚠️ Could not read final status: {e}")
            labels["cal_status"].text = "🎉 Calibration complete"

    # Show completion message
    labels["ph"].text = "🎉 Calibration finished!"
    labels["temp"].text = "System will restart..."

    # Give user time to read message
    print("   💡 Displaying completion message for 5 seconds...")
    time.sleep(5)

    print("🔄 Exiting calibration - system will restart in normal mode")
    print("   (This is normal - SPI resource management requires restart)")

    return True


def _abort_calibration(sensors, labels):
    """Abort calibration and clear EZO data"""
    print("🗑️ CALIBRATION ABORTED!")

    # Clear EZO calibration data
    if sensors["ph_working"] and sensors["ph_sensor"]:
        try:
            print("   🧹 Clearing EZO calibration data...")
            sensors["ph_sensor"].send_command("Cal,clear")
            time.sleep(1.6)  # EZO processing time

            # Verify clearing
            cal_status = sensors["ph_sensor"].query("Cal,?")
            print(f"   ✅ EZO cleared: {cal_status.strip()}")
            labels["cal_status"].text = f"🗑️ CLEARED: {cal_status.strip()}"
        except Exception as e:
            print(f"   ⚠️ Could not clear EZO: {e}")
            labels["cal_status"].text = "⚠️ Clear command failed"

    # Show abort message
    labels["ph"].text = "🗑️ Calibration aborted"
    labels["temp"].text = "System will restart..."

    # Give user time to read message
    print("   💡 Displaying abort message for 3 seconds...")
    time.sleep(3)

    print("🔄 Exiting calibration - system will restart in normal mode")
    return True


def _cleanup_and_exit():
    """Clean up resources before exit"""
    try:
        import displayio

        displayio.release_displays()
        print("   🔧 Released display resources")
    except:
        pass
    return True
