# lib/core/neopixel_status.py
"""
NeoPixel Status Management Module
Handles NeoPixel status indication and diagnostic functions
Extracted from main code.py for better organization
"""
import time


def update_neopixel_status(pixel, wifi_manager, mqtt_manager, state_manager):
    """Simple NeoPixel status: Green = OK, Red = Problem"""
    try:
        # Get current status
        wifi_connected = wifi_manager.is_connected()
        mqtt_connected = mqtt_manager.is_connected()
        system_status = state_manager.get_status()
        
        # Red if any critical issues
        if (not wifi_connected or 
            not mqtt_connected or 
            system_status.get("state") in ["CRITICAL", "FAILED"]):
            pixel[0] = (255, 0, 0)  # Red
            return "PROBLEM"
        else:
            pixel[0] = (0, 255, 0)  # Green
            return "OK"
            
    except Exception as e:
        pixel[0] = (255, 0, 0)  # Red for any errors
        return "ERROR"


def print_neopixel_legend():
    """Print the simple NeoPixel status legend"""
    print("\n💡 Simple NeoPixel Status Legend:")
    print("   🟢 GREEN: All systems OK")
    print("   🔴 RED: System has problems")
    print()


def neopixel_diagnostic_test(pixel, watchdog_enabled, wdt):
    """Test NeoPixel colors"""
    print("🔍 Simple NeoPixel diagnostic test...")
    colors = [
        ((255, 0, 0), "RED - Problem"),
        ((0, 255, 0), "GREEN - OK"),
    ]

    for color, description in colors:
        print(f"   Testing: {description}")
        pixel[0] = color
        time.sleep(1)
        # Feed watchdog during diagnostic
        if watchdog_enabled:
            wdt.feed()

    pixel[0] = (0, 0, 0)  # Turn off
    print("   Diagnostic complete!")