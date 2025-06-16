# i2c_touchscreen_test.py
"""
I2C-only touchscreen test - avoids SPI conflicts
Safe to run with existing pH monitoring system
"""

print("🖱️ I2C Touchscreen Test (No SPI conflicts)")
print("   Testing TSC2007 controller via I2C only")
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
    print("   Test will continue with I2C scan only...")
    adafruit_tsc2007 = None

# Use standard I2C (same as your existing pH sensor - no conflicts)
print("🔌 Setting up I2C for touchscreen...")
i2c = busio.I2C(board.SCL, board.SDA)
print("   Using same I2C bus as pH sensor (no conflicts)")

# I2C device scan
print("\n🔍 I2C device scan:")
while not i2c.try_lock():
    pass
try:
    devices = i2c.scan()
    print(f"   Found devices: {[hex(d) for d in devices]}")
    
    # Check for expected devices
    if 0x63 in devices:
        print("   ✅ pH sensor found at 0x63")
    if 0x48 in devices:
        print("   ✅ TSC2007 (default) found at 0x48")
    if 0x49 in devices:
        print("   ✅ TSC2007 (A0 set) found at 0x49") 
    if 0x4A in devices:
        print("   ✅ TSC2007 (A1 set) found at 0x4A")
    if 0x4B in devices:
        print("   ✅ TSC2007 (A0+A1 set) found at 0x4B")
        
finally:
    i2c.unlock()

# Try to initialize touchscreen if library available
if adafruit_tsc2007:
    print("\n🖱️ Initializing TSC2007 touchscreen controller...")
    touchscreen = None
    tsc_address = None
    
    # Try different addresses
    for addr in [0x48, 0x49, 0x4A, 0x4B]:
        if addr in devices:
            try:
                touchscreen = adafruit_tsc2007.TSC2007(i2c, address=addr)
                print(f"   ✅ TSC2007 initialized at address {hex(addr)}")
                tsc_address = addr
                break
            except Exception as e:
                print(f"   ❌ Failed at {hex(addr)}: {e}")
    
    if touchscreen:
        # Simple touch test
        print(f"\n🖱️ Touch test (10 seconds) - Touch the screen...")
        print("   Raw touch coordinates will be displayed")

        start_time = time.monotonic()
        touch_count = 0
        last_touch_time = 0

        while time.monotonic() - start_time < 10:
            try:
                if touchscreen.touched:
                    current_time = time.monotonic()
                    
                    # Rate limit to avoid spam
                    if current_time - last_touch_time > 0.5:
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
            
            except Exception as e:
                print(f"   ⚠️ Touch read error: {e}")
                break
            
            time.sleep(0.1)

        # Test summary
        print("\n" + "=" * 40)
        print("📊 TOUCHSCREEN TEST RESULTS") 
        print("=" * 40)

        if touch_count > 0:
            print(f"✅ SUCCESS: {touch_count} touches detected")
            print("   Touchscreen is working!")
        else:
            print("⚠️ No touches detected")
            print("   Try touching screen more firmly")
            
    else:
        print("❌ Could not initialize TSC2007")
        print("   Check FeatherWing V2 connections")
else:
    print("\n⚠️ Skipping touchscreen test - library not available")

print(f"\n✅ I2C test complete - no SPI conflicts")
print("   Your pH monitoring system should resume normally")