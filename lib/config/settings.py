# Try to import standard libraries
try:
    import os
    WIFI_SSID = os.getenv("CIRCUITPY_WIFI_SSID")
    WIFI_PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    if not WIFI_SSID or not WIFI_PASSWORD:
        raise RuntimeError("❌ Wi-Fi credentials missing from settings.toml!")
        
    # Add Adafruit IO credentials inside the try block
    IO_USERNAME = os.getenv("CIRCUITPY_IO_USERNAME")
    IO_KEY = os.getenv("CIRCUITPY_IO_KEY")
    if not IO_USERNAME or not IO_KEY:
        print("⚠️ Warning: Adafruit IO credentials missing from settings.toml")
        # Using None as fallback values if not found
        IO_USERNAME = None
        IO_KEY = None
        
except (ImportError, NameError):
    # Fallback for environments where os is not available
    print("Warning: os module not available, using default values")
    WIFI_SSID = None
    WIFI_PASSWORD = None
    IO_USERNAME = None
    IO_KEY = None
    
# Constants that don't depend on os
TZ_OFFSET = +1  # Standard timezone offset for local time (Mountain Standard Time, MST)
ADT7410_ADDRESS = 0x48  # I2C address of ADT7410 sensor
