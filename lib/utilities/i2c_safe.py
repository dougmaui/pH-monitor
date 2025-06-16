# lib/utils/i2c_safe.py
"""
I2C Safety Wrapper - Prevents system hangs from I2C lockups
Provides timeout protection and bus reset capabilities
"""
import time
import busio
import board
import microcontroller

class I2CSafeWrapper:
    """
    Safe I2C wrapper that prevents hangs and provides recovery
    """
    
    def __init__(self, i2c_bus, state_manager=None):
        self.i2c = i2c_bus
        self.state_manager = state_manager
        
        # Timeout settings
        self.default_timeout = 2.0  # 2 second default timeout
        self.reset_timeout = 5.0    # 5 second timeout for reset operations
        
        # Health tracking
        self.total_operations = 0
        self.failed_operations = 0
        self.timeouts = 0
        self.resets = 0
        self.last_reset_time = 0
        
        # Rate limiting for resets
        self.min_reset_interval = 10  # Don't reset more than once per 10 seconds
    
    def safe_read_sensor(self, read_function, sensor_name="unknown", timeout=None):
        """
        Safely execute a sensor read function with timeout protection
        
        Args:
            read_function: Function to call (e.g., ph_sensor.read_ph)
            sensor_name: Name for logging/debugging
            timeout: Timeout in seconds (uses default if None)
        
        Returns:
            Sensor value or None if timeout/error
        """
        if timeout is None:
            timeout = self.default_timeout
        
        self.total_operations += 1
        start_time = time.monotonic()
        
        try:
            print(f"📡 Reading {sensor_name} (timeout: {timeout}s)")
            
            # Execute with timeout
            result = self._execute_with_timeout(read_function, timeout)
            
            if result is not None:
                elapsed = time.monotonic() - start_time
                print(f"   ✅ {sensor_name} read successful ({elapsed:.2f}s)")
                return result
            else:
                print(f"   ⏰ {sensor_name} read timeout after {timeout}s")
                return self._handle_timeout(sensor_name)
                
        except Exception as e:
            self.failed_operations += 1
            elapsed = time.monotonic() - start_time
            print(f"   ❌ {sensor_name} read error after {elapsed:.2f}s: {e}")
            
            # If it's an I2C related error, consider reset
            if "I2C" in str(e) or "SCL" in str(e) or "SDA" in str(e):
                return self._handle_i2c_error(sensor_name, e)
            
            return None
    
    def _execute_with_timeout(self, function, timeout):
        """Execute function with timeout protection"""
        start_time = time.monotonic()
        
        # For CircuitPython, we can't use threading, so we'll try multiple quick attempts
        max_attempts = max(1, int(timeout * 10))  # 10 attempts per second
        
        for attempt in range(max_attempts):
            try:
                # Quick attempt
                result = function()
                return result
            except Exception as e:
                # If it's a quick failure, retry
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return None  # Timeout reached
                
                # Brief delay before retry
                time.sleep(0.1)
        
        return None  # All attempts failed within timeout
    
    def _handle_timeout(self, sensor_name):
        """Handle sensor timeout"""
        self.timeouts += 1
        
        if self.state_manager:
            self.state_manager.add_alert(f"{sensor_name} timeout - I2C may be hung", "warning")
        
        # Consider I2C reset if we have multiple recent timeouts
        if self.timeouts % 3 == 0:  # Every 3rd timeout
            print(f"   🔄 Multiple timeouts detected - attempting I2C reset")
            self._attempt_i2c_reset()
        
        return None
    
    def _handle_i2c_error(self, sensor_name, error):
        """Handle I2C specific errors"""
        print(f"   🔧 I2C error detected for {sensor_name}: {error}")
        
        if self.state_manager:
            self.state_manager.add_alert(f"I2C error on {sensor_name}: {error}", "warning")
        
        # Attempt I2C reset for I2C errors
        self._attempt_i2c_reset()
        return None
    
    def _attempt_i2c_reset(self):
        """Attempt to reset I2C bus"""
        current_time = time.monotonic()
        
        # Rate limit resets
        if current_time - self.last_reset_time < self.min_reset_interval:
            print(f"   ⏳ I2C reset rate limited (last reset {current_time - self.last_reset_time:.1f}s ago)")
            return False
        
        self.last_reset_time = current_time
        self.resets += 1
        
        try:
            print(f"   🔄 Attempting I2C bus reset #{self.resets}...")
            
            # Method 1: Try to unlock and recreate
            try:
                if self.i2c.try_lock():
                    self.i2c.unlock()
                    print("     ✅ I2C unlocked")
                    time.sleep(0.5)
                    return True
            except Exception as e:
                print(f"     ❌ I2C unlock failed: {e}")
            
            # Method 2: Try to deinitialize and recreate (more aggressive)
            try:
                print("     🔧 Attempting I2C recreation...")
                
                # This is more aggressive - recreate the I2C bus
                # Note: This might not work in all cases due to CircuitPython limitations
                self.i2c.deinit()
                time.sleep(1)
                
                # Recreate I2C bus
                new_i2c = busio.I2C(board.SCL, board.SDA)
                self.i2c = new_i2c
                
                print("     ✅ I2C bus recreated")
                
                if self.state_manager:
                    self.state_manager.add_alert(f"I2C bus reset successful", "info")
                
                return True
                
            except Exception as e:
                print(f"     ❌ I2C recreation failed: {e}")
                
                if self.state_manager:
                    self.state_manager.add_alert(f"I2C reset failed: {e}", "critical")
                
                return False
                
        except Exception as e:
            print(f"   ❌ I2C reset failed: {e}")
            return False
    
    def safe_i2c_scan(self, timeout=None):
        """Safely scan I2C bus with timeout protection"""
        if timeout is None:
            timeout = self.default_timeout
        
        try:
            print(f"🔍 Scanning I2C bus (timeout: {timeout}s)")
            
            def scan_function():
                while not self.i2c.try_lock():
                    time.sleep(0.01)
                try:
                    return self.i2c.scan()
                finally:
                    self.i2c.unlock()
            
            devices = self._execute_with_timeout(scan_function, timeout)
            
            if devices is not None:
                print(f"   ✅ Found I2C devices: {[hex(d) for d in devices]}")
                return devices
            else:
                print(f"   ⏰ I2C scan timeout after {timeout}s")
                self._handle_timeout("I2C_scan")
                return []
                
        except Exception as e:
            print(f"   ❌ I2C scan error: {e}")
            self._handle_i2c_error("I2C_scan", e)
            return []
    
    def check_i2c_health(self):
        """Quick I2C health check"""
        try:
            # Quick scan to see if I2C is responsive
            devices = self.safe_i2c_scan(timeout=1.0)  # Quick 1 second timeout
            return len(devices) > 0  # Healthy if we found any devices
        except:
            return False
    
    def get_stats(self):
        """Get I2C operation statistics"""
        success_rate = 0
        if self.total_operations > 0:
            success_rate = round(((self.total_operations - self.failed_operations) / self.total_operations) * 100, 1)
        
        return {
            "total_operations": self.total_operations,
            "failed_operations": self.failed_operations,
            "timeouts": self.timeouts,
            "resets": self.resets,
            "success_rate": success_rate,
            "last_reset_age": time.monotonic() - self.last_reset_time if self.last_reset_time else None
        }
    
    def reset_stats(self):
        """Reset statistics counters"""
        self.total_operations = 0
        self.failed_operations = 0
        self.timeouts = 0
        # Don't reset self.resets or last_reset_time - keep those for safety


# Convenience functions for sensor operations
def create_safe_sensor_reader(i2c_wrapper, sensor, read_method_name="read"):
    """
    Create a safe sensor reading function
    
    Args:
        i2c_wrapper: I2CSafeWrapper instance
        sensor: Sensor object
        read_method_name: Name of the read method (e.g., "read", "read_ph", "temperature")
    
    Returns:
        Function that safely reads the sensor
    """
    def safe_read():
        read_function = getattr(sensor, read_method_name)
        sensor_name = f"{sensor.__class__.__name__}.{read_method_name}"
        return i2c_wrapper.safe_read_sensor(read_function, sensor_name)
    
    return safe_read

# Global I2C safety instance (to be initialized in main code)
_global_i2c_safe = None

def get_global_i2c_safe():
    """Get the global I2C safety wrapper"""
    return _global_i2c_safe

def set_global_i2c_safe(i2c_safe_wrapper):
    """Set the global I2C safety wrapper"""
    global _global_i2c_safe
    _global_i2c_safe = i2c_safe_wrapper