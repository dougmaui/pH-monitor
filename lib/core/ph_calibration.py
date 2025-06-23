def calibration_preview(
    ph_label,
    temp_c_label,
    temp_f_label,
    rssi_label,
    time_label,
    button_next,
    button_abort,
    pixel,
):
    import time

    next_was_pressed = False
    abort_was_pressed = False

    calibration_points = [("mid", 7.000), ("low", 4.000), ("high", 10.000)]

    step = 0
    done = False

    print("\n🔍 Calibration Preview Mode")
    print("Press NEXT (D6) to step forward, ABORT (D9) to exit.\n")

    # Wait for release
    while not button_next.value or not button_abort.value:
        if watchdog is not None:
            watchdog.feed()
        time.sleep(0.01)

    led_on = False
    last_flash = time.monotonic()

    while not done:
        buffer_label, pH_value = calibration_points[step]
        ph_label.text = f"pH {pH_value:.3f} ({buffer_label})"
        temp_c_label.text = f"Step {step+1}/3: NEXT"
        temp_f_label.text = "Press NEXT to step or ABORT to exit"
        rssi_label.text = ""
        time_label.text = ""

        while True:
            now = time.monotonic()

            if now - last_flash >= 0.5:
                led_on = not led_on
                pixel[0] = (0, 128, 0) if led_on else (0, 0, 0)
                last_flash = now

            if not button_abort.value and not abort_was_pressed:
                print("❌ Preview aborted.")
                done = True
                break
            elif button_abort.value:
                # Reset the abort press state once released
                abort_was_pressed = False

            # Wait until NEXT is released before allowing calibration
            if not button_next.value and not next_was_pressed:
                next_was_pressed = True
                press_start = now
            elif button_next.value and next_was_pressed:
                next_was_pressed = False
                press_duration = now - press_start
                if press_duration > 0.1:
                    ph_label.text = "Calibrating..."
                    temp_c_label.text = "Waiting..."
                    rssi_label.text = "Hold still..."
                    print(f"⚙️ Calibrating '{label}' at pH {expected_ph:.3f}...")

                    print(f"👉 Sending: Cal,{label},{expected_ph:.2f}")
                    command = f"Cal,{label},{expected_ph:.2f}"
                next_was_pressed = False
                step = (step + 1) % len(calibration_points)
                break

            if watchdog is not None:
                watchdog.feed()
                time.sleep(0.05)

    pixel[0] = (0, 0, 0)
    ph_label.text = "--"
    temp_c_label.text = "Temp C"
    temp_f_label.text = "Temp F"
    rssi_label.text = "RSSI"
    time_label.text = "Time"


def run_calibration(
    ph_sensor,
    read_temperature,
    ph_label,
    temp_c_label,
    temp_f_label,
    rssi_label,
    time_label,
    button_next,
    button_abort,
    pixel,
    watchdog=None,
):
    import time

    temp_f_label.text = ""
    rssi_label.text = ""
    time_label.text = ""

    next_was_pressed = False
    abort_was_pressed = False

    calibration_points = [("mid", 7.000), ("low", 4.000), ("high", 10.000)]

    print("\n--- PH CALIBRATION MODE ---")
    print("Use NEXT (D6) to calibrate once stable.")
    print("Press ABORT (D9) to cancel.\n")

    while not button_next.value or not button_abort.value:
        time.sleep(0.01)

    led_on = False
    last_flash = time.monotonic()
    step = 0
    aborted = False

    while step < len(calibration_points):
        ph_label.text = f"Step {step+1} active"
        temp_f_label.text = "Press NEXT to calibrate"
        rssi_label.text = ""
        label, expected_ph = calibration_points[step]
        print(f"\nPlace probe in pH {expected_ph:.3f} buffer ({label})")

        press_start = None
        last_temp_update = 0
        last_ph_update = 0

        while True:
            now = time.monotonic()

            if now - last_flash >= 0.5:
                led_on = not led_on
                pixel[0] = (0, 128, 0) if led_on else (0, 0, 0)
                last_flash = now

            if watchdog is not None:
                watchdog.feed()

            if now - last_temp_update >= 2.0:
                temp_c = read_temperature()
                if temp_c is not None:
                    ph_sensor.set_temp_compensation(temp_c)
                    print(f"🌡️ Temp compensation: {temp_c:.2f} °C")
                last_temp_update = now

            if now - last_ph_update >= 1.0:
                current_ph = ph_sensor.read_ph()
                ph_label.text = f"pH {current_ph:.3f} ({label})"
                temp_c_label.text = f"Step {step+1}/3"
                if ph_label.text != "Calibrating...":
                    temp_f_label.text = ""
                    rssi_label.text = ""
                time_label.text = ""
                last_ph_update = now
                print(f"📖 Live pH: {current_ph:.3f}")

            if not button_abort.value and not abort_was_pressed:
                abort_was_pressed = True
                abort_press_start = now
            elif not button_abort.value and abort_was_pressed:
                if now - abort_press_start > 1.0:
                    print("❌ Calibration aborted.")
                    ph_label.text = "❌ Aborted"
                    aborted = True
                    break
            elif button_abort.value:
                abort_was_pressed = False
                abort_was_pressed = False

            if not button_next.value and not next_was_pressed:
                next_was_pressed = True
                time.sleep(0.1)
            elif button_next.value and next_was_pressed:
                next_was_pressed = False

                ph_label.text = "Calibrating..."
                temp_c_label.text = "Waiting..."
                rssi_label.text = "Hold still..."
                print(f"⚙️ Calibrating '{label}' at pH {expected_ph:.3f}...")

                print(f"👉 Sending: Cal,{label},{expected_ph:.2f}")
                command = f"Cal,{label},{expected_ph:.2f}"
                print(f"👉 Sending: {command}")
                try:
                    # Read current calibration level BEFORE
                    pre_status = ph_sensor.query("Cal,?").strip()
                    pre_level = (
                        int(pre_status.split(",")[1]) if "," in pre_status else 0
                    )

                    ph_sensor.write(command)
                    for _ in range(25):  # 5 seconds in 0.2s steps
                        if watchdog is not None:
                            watchdog.feed()
                        time.sleep(0.2)

                    result = None
                    query_start = time.monotonic()
                    new_level = pre_level  # Default in case no update
                    while time.monotonic() - query_start < 5.0:
                        try:
                            result = ph_sensor.query("Cal,?").strip()
                            # Raw response suppressed (was: Resp: '?Cal,n')
                            new_level = (
                                int(result.split(",")[1])
                                if "," in result
                                else pre_level
                            )
                            if new_level > pre_level:
                                break  # Success: calibration level increased
                        except Exception as e:
                            print("Query error:", e)
                            result = ""
                            break
                        if watchdog is not None:
                            watchdog.feed()
                        time.sleep(0.25)
                    if result is None:
                        result = ""
                except Exception as e:
                    print("⚠️ Calibration write/query error:", e)
                    result = ""
                # Suppress raw ?Cal,n display on OLED
                pass
                print(f"📡 OLED Debug → Resp: '{result.strip()}'")

                # Use actual change in calibration level to determine success
                success = new_level > pre_level or new_level >= step + 1
                if success:
                    ph_label.text = f"✅ {label} calibrated"
                    temp_c_label.text = ""
                    rssi_label.text = "Press NEXT to continue"
                else:
                    ph_label.text = f"⚠️ {label} failed"
                    temp_c_label.text = f"Resp: {result.strip()}"
                    rssi_label.text = "Press NEXT to continue"

                # Wait for user to press NEXT to move on
                rssi_label.text = "✅ Press NEXT to continue"

                # Wait for NEXT button release first
                while not button_next.value:
                    if watchdog is not None:
                        watchdog.feed()
                    if not button_abort.value:
                        print("❌ Aborted after calibration")
                        aborted = True
                        break
                    time.sleep(0.05)

                # Then wait for a new NEXT press
                while button_next.value:
                    if watchdog is not None:
                        watchdog.feed()
                    time.sleep(0.05)

                while not button_next.value:
                    if not button_abort.value:
                        print("❌ Aborted after calibration")
                        aborted = True
                        break
                    time.sleep(0.05)

                if not aborted:
                    step += 1
                    break

            time.sleep(0.05)

        if aborted:
            break

    pixel[0] = (0, 0, 0)

    if not aborted:
        ph_label.text = "🎉 Calibration finished"
        time.sleep(3.0)
        ph_label.text = "🎉 Calibration complete"
        temp_c_label.text = ""

        # Show Cal,? response
        status = ph_sensor.query("Cal,?")
        print(f"📊 Final calibration status: {status.strip()}")
        rssi_label.text = f"Cal: {status.strip()}"
    else:
        ph_label.text = "Calibration canceled"
        temp_c_label.text = ""

    temp_f_label.text = "Temp F"
    rssi_label.text = "RSSI"
    time_label.text = "Time"
