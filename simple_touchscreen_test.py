# simple_touchscreen_test.py
"""
Simple touchscreen test that preserves ALL existing functionality
Only adds I2C touchscreen support - leaves SPI display code unchanged

This is the minimal test to confirm touchscreen works before integration
"""

print("🖱️ Simple Touchscreen Test")
print("   PRESERVES: All existing SPI display code")
print("   ADDS: I2C touchscreen support only")
print("   Safe to run alongside existing pH monitoring")
print()

import time
import board
import busio

# Check if required library is available
try:
    import adafruit_tsc2007
    print("✅ adafruit_tsc2007 library found")
except ImportError:
    print("❌ Missing adafruit_tsc2007 library")
    print("   Install with: circup install adafruit_tsc2007")
    print("   Or copy from Adafruit library bundle")
    exit(1)

# Use standard I2C (same as your existing pH sensor)
print("🔌 Setting up I2C for touchscreen...")
i2c = busio.I2C(board.SCL, board.SDA)
print("   Using same I2C bus as pH sensor (no conflicts)")

# Initialize touchscreen on I2C
print("🖱️ Initializing TSC2007 touchscreen controller...")
try:
    # Try default address 0x48 first
    touchscreen = adafruit_tsc2007.TSC2007(i2c, address=0x48)
    print("   ✅ TSC2007 initialized at address 0x48")
    tsc_address = 0x48
except Exception as e:
    print(f"   ❌ Failed at 0x48: {e}")
    
    # Try alternate addresses if default fails
    for addr in [0x49, 0x4A, 0x4B]:
        try:
            touchscreen = adafruit_tsc2007.TSC2007(i2c, address=addr)
            print(f"   ✅ TSC2007 initialized at address {hex(addr)}")
            tsc_address = addr
            break
        except Exception as e:
            print(f"   ❌ Failed at {hex(addr)}: {e}")
    else:
        print("❌ Could not initialize TSC2007 at any address")
        print("   Check FeatherWing V2 connections and jumpers")
        exit(1)

# Quick I2C scan for verification
print("\n🔍 I2C device scan:")
while not i2c.try_lock():
    pass
try:
    devices = i2c.scan()
    print(f"   Found devices: {[hex(d) for d in devices]}")
    if tsc_address in devices:
        print(f"   ✅ TSC2007 confirmed at {hex(tsc_address)}")
    else:
        print(f"   ⚠️ TSC2007 not visible in scan (but may still work)")
finally:
    i2c.unlock()

# Simple touch test
print(f"\n🖱️ Touch test (15 seconds) - Touch the screen...")
print("   Raw touch coordinates will be displayed")

start_time = time.monotonic()
touch_count = 0
last_touch_time = 0

while time.monotonic() - start_time < 15:
    try:
        if touchscreen.touched:
            current_time = time.monotonic()
            
            # Rate limit to avoid spam
            if current_time - last_touch_time > 0.3:
                touch_data = touchscreen.touch
                
                if touch_data and touch_data.get("pressure", 0) > 100:
                    touch_count += 1
                    last_touch_time = current_time
                    
                    x = touch_data["x"]
                    y = touch_data["y"] 
                    pressure = touch_data["pressure"]
                    
                    print(f"   Touch #{touch_count}: X={x}, Y={y}, Pressure={pressure}")
                    
                    # Basic coordinate feedback
                    if x < 1000:
                        x_pos = "LEFT"
                    elif x > 3000:
                        x_pos = "RIGHT"
                    else:
                        x_pos = "CENTER"
                        
                    if y < 1000:
                        y_pos = "BOTTOM"
                    elif y > 3000:
                        y_pos = "TOP" 
                    else:
                        y_pos = "MIDDLE"
                    
                    print(f"   Position: {x_pos}-{y_pos}")
                    print()
    
    except Exception as e:
        print(f"   ⚠️ Touch read error: {e}")
        break
    
    time.sleep(0.05)  # 20Hz polling

# Test summary
print("=" * 50)
print("📊 TOUCHSCREEN TEST RESULTS")
print("=" * 50)

if touch_count > 0:
    print(f"✅ SUCCESS: {touch_count} touches detected")
    print("   Touchscreen is working and ready for integration")
    print()
    print("📝 Next steps:")
    print("   1. Integrate touchscreen into main pH monitoring loop")
    print("   2. Add coordinate mapping for screen positions")
    print("   3. Create pH calibration UI")
    print()
    print("🔧 Integration notes:")
    print("   - Touchscreen uses I2C (no SPI conflicts)")
    print("   - Your existing display code unchanged")
    print("   - Can poll touchscreen in main sensor loop")
else:
    print("⚠️ No touches detected")
    print()
    print("🔧 Troubleshooting:")
    print("   1. Verify 3.5\" FeatherWing V2 with TSC2007")
    print("   2. Check I2C address jumpers on back of board")
    print("   3. Ensure firm touch pressure")
    print("   4. Verify STEMMA QT connection if using external I2C")

print(f"\n✅ Test complete - your existing code remains unchanged")
print("   SPI display, pH monitoring, and all other functions preserved")