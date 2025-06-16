# lib/oled_display/oled_display.py
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_ili9341
from fourwire import FourWire
import board

# Try to import nice Raleway fonts from font bundle
try:
    from font_raleway_regular_24 import FONT as raleway_24
    from font_raleway_regular_18 import FONT as raleway_18
    large_font = raleway_24
    medium_font = raleway_18
    font_available = True
    print("✅ Using Raleway fonts")
except ImportError:
    # Fall back to terminal font if no custom fonts
    large_font = terminalio.FONT
    medium_font = terminalio.FONT
    font_available = False
    print("⚠️ Using terminal font - install fonts with: circup install font_raleway_regular_18 font_raleway_regular_14")

def initialize_display(shared_spi=None):
    """Initialize display with optional shared SPI bus"""
    displayio.release_displays()
    
    # Use shared SPI if provided, otherwise create new one
    if shared_spi:
        print("   Using shared SPI bus for display")
        spi = shared_spi
    else:
        print("   Creating new SPI bus for display")
        # Use built-in Feather SPI
        spi = board.SPI()
    
    # Display bus setup - using D9 for CS, D10 for DC
    display_bus = FourWire(
        spi, 
        command=board.D10,    # DC pin
        chip_select=board.D9, # CS pin
        reset=None            # No reset needed
    )
    
    # Initialize ILI9341 display (480x320 resolution)
    display = adafruit_ili9341.ILI9341(display_bus, width=480, height=320)
    
    return display

def create_display_group():
    group = displayio.Group()
    
    # Add dark blue background so we can see the display is working
    color_bitmap = displayio.Bitmap(480, 320, 1)
    color_palette = displayio.Palette(1)
    color_palette[0] = 0x000080  # Dark blue background
    
    bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette)
    group.append(bg_sprite)
    
    # Use better fonts if available, otherwise smaller scale with terminal font
    if font_available:
        # With custom fonts - no scaling needed
        ph_label = label.Label(large_font, text="pH: --", color=0xFFFFFF, x=20, y=40)
        temp_c_label = label.Label(medium_font, text="Temp: --°C", color=0xFFFFFF, x=20, y=80)
        temp_f_label = label.Label(medium_font, text="Temp: --°F", color=0xFFFFFF, x=20, y=110)
        rssi_label = label.Label(medium_font, text="WiFi: -- dBm", color=0xFFFFFF, x=20, y=140)
        time_label = label.Label(medium_font, text="--:--", color=0xFFFFFF, x=20, y=170)
    else:
        # With terminal font - use smaller scale for less pixelation
        ph_label = label.Label(terminalio.FONT, text="pH: --", color=0xFFFFFF, x=20, y=40)
        ph_label.scale = 2  # Smaller scale = less pixelated
        
        temp_c_label = label.Label(terminalio.FONT, text="Temp: --°C", color=0xFFFFFF, x=20, y=80)
        temp_c_label.scale = 2
        
        temp_f_label = label.Label(terminalio.FONT, text="Temp: --°F", color=0xFFFFFF, x=20, y=110)
        temp_f_label.scale = 2
        
        rssi_label = label.Label(terminalio.FONT, text="WiFi: -- dBm", color=0xFFFFFF, x=20, y=140)
        rssi_label.scale = 2
        
        time_label = label.Label(terminalio.FONT, text="--:--", color=0xFFFFFF, x=20, y=170)
        time_label.scale = 2
    
    group.append(ph_label)
    group.append(temp_c_label)
    group.append(temp_f_label)
    group.append(rssi_label)
    group.append(time_label)
    
    return group, ph_label, temp_c_label, temp_f_label, rssi_label, time_label

def update_display(
    ph_label,
    temp_c_label,
    temp_f_label,
    rssi_label,
    time_label,
    ph,
    temp_c,
    temp_f,
    rssi,
    time_str,
):
    ph_label.text = f"pH: {ph}" if ph else "pH: --"
    temp_c_label.text = f"Temp: {temp_c}°C" if temp_c else "Temp: --°C"
    temp_f_label.text = f"Temp: {temp_f}°F" if temp_f else "Temp: --°F"
    rssi_label.text = f"WiFi: {rssi} dBm" if rssi else "WiFi: -- dBm"
    time_label.text = time_str