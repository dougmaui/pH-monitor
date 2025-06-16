# Hot Tub Controller (CircuitPython)

This project runs on an Adafruit Feather  and automates monitoring and control of a hot tub using:

- ✅ pH and temperature sensors
- ✅ Peristaltic acid dosing pump
- ✅ Wi-Fi data logging via Adafruit IO
- ✅ OLED display for real-time feedback
- ✅ Pushbutton-based 3-point calibration
- ✅ Uploading to ADAFRUIT


## Project Structure

## Setup

1. Copy the `code.py` and necessary files to your CIRCUITPY drive.
2. Install required libraries into the `lib/` folder (via Adafruit Library Bundle).
3. Connect to the serial REPL to view output or run interactively.

## Goals

- [x] Modular, maintainable code
- [x] Reliable remote monitoring
- [ ] Add over-the-air updates (future)
- [ ] Add fault detection for sensors and dosing

---

I am now at the second stage of this project where I created modular code that did the basic sensing, and wifi attach and acquistion of date and local time. I also connected to ADAFRUIT IO and could see the updating. My next steps are to make this much more robust befor I go to Europe. First I am going to create a timestamp that I include with my updates to AF. This will solve some logging complexities on AF and also provide better resolution for debugging. It will also allow me to see dropouts quickly on the AF dashboard feed. After that I am going to make a much more robust WIFI system with a watchdog, connect test, re-connects and possibly fault logging. The step after that is to provide much of the same robustness to the AF interface. I also just found that The temperature sense, if not initiated correctly won't self correct.

