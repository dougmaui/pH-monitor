# lib/time_sync/robust_time.py
"""
Robust Time Manager for ESP32-S3
Handles NTP sync, timezone management, automatic scheduling, and time validation
Memory optimized for CircuitPython
"""
import time
import rtc
import adafruit_ntp

class TimeManager:
    """
    Robust time manager with automatic NTP synchronization and validation
    Integrates with state manager and WiFi manager
    """
    
    def __init__(self, state_manager, wifi_manager, timezone_offset=1):
        self.state_manager = state_manager
        self.wifi_manager = wifi_manager
        self.timezone_offset = timezone_offset  # Hours from UTC (France = +1)
        
        # NTP configuration - using multiple servers for reliability
        self.ntp_servers = [
            "pool.ntp.org",
            "time.nist.gov", 
            "fr.pool.ntp.org",  # France-specific
            "time.google.com"
        ]
        self.current_server_index = 0
        
        # Time synchronization state
        self.last_sync_time = None
        self.last_sync_success = False
        self.sync_attempts = 0
        self.successful_syncs = 0
        self.consecutive_failures = 0
        
        # Timing configuration
        self.sync_interval = 3600      # Normal sync every hour
        self.failed_sync_retry = 300   # Retry every 5 minutes after failure
        self.startup_sync_timeout = 20 # Longer timeout on startup
        self.normal_sync_timeout = 10  # Normal timeout
        self.max_drift_seconds = 86400 # 24 hours max without sync
        
        # Boot time tracking
        self.boot_time = time.monotonic()
        self.system_start_time = None
        
        # Register with state manager
        state_manager.register_component("time")
    
    def initialize(self):
        """Initialize time manager and attempt first sync"""
        print("🕐 Initializing robust time manager...")
        
        if not self.wifi_manager.is_connected():
            print("   ⚠️  No WiFi - time sync will be attempted when available")
            self.state_manager.update_component_health(
                "time", "degraded", "No WiFi connection"
            )
            return False
        
        # Attempt initial synchronization with longer timeout
        print("   Attempting initial time synchronization...")
        success, error = self._sync_time_now(timeout=self.startup_sync_timeout)
        
        if success:
            print(f"   ✅ Initial time sync successful: {self.get_local_time_string()}")
            self.state_manager.update_component_health("time", "healthy")
            return True
        else:
            print(f"   ⚠️  Initial time sync failed: {error}")
            self.state_manager.update_component_health("time", "degraded", error)
            return False
    
    def _sync_time_now(self, timeout=None):
        """
        Immediately attempt time synchronization with current server
        Returns (success: bool, error_message: str)
        """
        if timeout is None:
            timeout = self.normal_sync_timeout
        
        self.sync_attempts += 1
        
        if not self.wifi_manager.is_connected():
            return False, "No WiFi connection"
        
        socket_pool = self.wifi_manager.get_socket_pool()
        if not socket_pool:
            return False, "No socket pool available"
        
        # Try current NTP server
        server = self.ntp_servers[self.current_server_index]
        
        try:
            print(f"   🌐 Syncing with {server} (timeout: {timeout}s)...")
            
            # Create NTP client
            ntp_client = adafruit_ntp.NTP(
                socket_pool, 
                server=server, 
                tz_offset=self.timezone_offset
            )
            
            # Attempt sync with timeout
            sync_start = time.monotonic()
            current_time = None
            
            while time.monotonic() - sync_start < timeout:
                try:
                    current_time = ntp_client.datetime
                    if current_time:
                        break
                except Exception as e:
                    print(f"     NTP attempt failed: {e}")
                    time.sleep(0.5)
            
            if not current_time:
                raise Exception(f"Timeout after {timeout}s")
            
            # Validate the received time
            if not self._validate_ntp_time(current_time):
                raise Exception("Invalid time received from NTP server")
            
            # Set the system RTC
            rtc.RTC().datetime = current_time
            
            # Record successful sync
            self.last_sync_time = time.monotonic()
            self.last_sync_success = True
            self.successful_syncs += 1
            self.consecutive_failures = 0
            self.system_start_time = current_time
            
            # Format time for logging
            time_str = self._format_datetime(current_time)
            print(f"   ✅ Time synchronized: {time_str}")
            
            return True, None
            
        except Exception as e:
            error_msg = f"Sync with {server} failed: {e}"
            print(f"   ❌ {error_msg}")
            
            # Try next server on next attempt
            self._rotate_ntp_server()
            
            self.last_sync_success = False
            self.consecutive_failures += 1
            
            return False, error_msg
    
    def _validate_ntp_time(self, ntp_time):
        """Validate that NTP time is reasonable"""
        try:
            # Convert to timestamp for validation
            ntp_timestamp = time.mktime(ntp_time)
            
            # Check if time is reasonable (after 2020, before 2050)
            if ntp_timestamp < 1577836800:  # Jan 1, 2020
                print(f"     ❌ Time too far in past: {ntp_timestamp}")
                return False
            
            if ntp_timestamp > 2524608000:  # Jan 1, 2050
                print(f"     ❌ Time too far in future: {ntp_timestamp}")
                return False
            
            # Check for reasonable drift if we have a previous sync
            if self.last_sync_time:
                expected_now = time.time()
                drift = abs(ntp_timestamp - expected_now)
                if drift > 3600:  # More than 1 hour drift
                    print(f"     ⚠️  Large time drift detected: {drift}s")
                    # Don't reject, but log warning
            
            return True
            
        except Exception as e:
            print(f"     ❌ Time validation error: {e}")
            return False
    
    def _rotate_ntp_server(self):
        """Rotate to next NTP server for better reliability"""
        self.current_server_index = (self.current_server_index + 1) % len(self.ntp_servers)
        next_server = self.ntp_servers[self.current_server_index]
        print(f"     🔄 Rotating to next NTP server: {next_server}")
    
    def should_sync_time(self):
        """Determine if time synchronization is needed"""
        if not self.last_sync_time:
            return True  # Never synced
        
        current_time = time.monotonic()
        time_since_sync = current_time - self.last_sync_time
        
        if not self.last_sync_success:
            # Last sync failed - retry sooner
            return time_since_sync >= self.failed_sync_retry
        else:
            # Normal sync interval
            return time_since_sync >= self.sync_interval
    
    def update(self):
        """Update time manager - call this in main loop"""
        # Only attempt sync if WiFi is available and it's time to sync
        if (self.wifi_manager.is_connected() and 
            self.should_sync_time()):
            
            print("🕐 Scheduled time synchronization...")
            success, error = self._sync_time_now()
            
            if success:
                self.state_manager.update_component_health("time", "healthy")
            else:
                health = "failed" if self.consecutive_failures > 3 else "degraded"
                self.state_manager.update_component_health("time", health, error)
    
    def get_local_time_string(self):
        """Get formatted local time string (HH:MM:SS)"""
        try:
            current_time = time.localtime()
            return f"{current_time.tm_hour:02d}:{current_time.tm_min:02d}:{current_time.tm_sec:02d}"
        except Exception:
            return "00:00:00"
    
    def get_local_datetime_string(self):
        """Get formatted local date and time string (YYYY-MM-DD HH:MM:SS)"""
        try:
            current_time = time.localtime()
            return f"{current_time.tm_year:04d}-{current_time.tm_mon:02d}-{current_time.tm_mday:02d} {current_time.tm_hour:02d}:{current_time.tm_min:02d}:{current_time.tm_sec:02d}"
        except Exception:
            return "1970-01-01 00:00:00"
    
    def get_local_date_string(self):
        """Get formatted local date string (YYYY-MM-DD)"""
        try:
            current_time = time.localtime()
            return f"{current_time.tm_year:04d}-{current_time.tm_mon:02d}-{current_time.tm_mday:02d}"
        except Exception:
            return "1970-01-01"
    
    def get_timestamp_for_data(self):
        """Get timestamp suitable for data logging"""
        if self.is_time_valid():
            return self.get_local_datetime_string()
        else:
            # Fallback to uptime if time is invalid
            uptime = time.monotonic() - self.boot_time
            return f"uptime_{uptime:.0f}s"
    
    def get_uptime_string(self):
        """Get system uptime as formatted string (HH:MM:SS)"""
        try:
            uptime_seconds = time.monotonic() - self.boot_time
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception:
            return "00:00:00"
    
    def is_time_valid(self):
        """Check if current system time is considered valid"""
        if not self.last_sync_time:
            return False
        
        # Time is valid if we've synced recently enough
        time_since_sync = time.monotonic() - self.last_sync_time
        return time_since_sync < self.max_drift_seconds
    
    def _format_datetime(self, dt):
        """Format datetime object to string"""
        try:
            return f"{dt.tm_year:04d}-{dt.tm_mon:02d}-{dt.tm_mday:02d} {dt.tm_hour:02d}:{dt.tm_min:02d}:{dt.tm_sec:02d}"
        except Exception:
            return "Invalid time"
    
    def get_timezone_info(self):
        """Get timezone information"""
        return {
            "offset_hours": self.timezone_offset,
            "timezone_name": f"UTC{'+' if self.timezone_offset >= 0 else ''}{self.timezone_offset}",
            "is_dst": time.localtime().tm_isdst if self.is_time_valid() else False
        }
    
    def force_sync(self):
        """Force an immediate time synchronization"""
        print("🔄 Forcing immediate time synchronization...")
        if not self.wifi_manager.is_connected():
            return False, "No WiFi connection"
        
        self.last_sync_time = 0  # Reset to force sync
        return self._sync_time_now(timeout=self.startup_sync_timeout)
    
    def get_status(self):
        """Get comprehensive time manager status"""
        current_time = time.monotonic()
        time_since_sync = (current_time - self.last_sync_time 
                          if self.last_sync_time else None)
        
        # Calculate next sync time
        if self.last_sync_time:
            if self.last_sync_success:
                next_sync_in = self.sync_interval - (current_time - self.last_sync_time)
            else:
                next_sync_in = self.failed_sync_retry - (current_time - self.last_sync_time)
            next_sync_in = max(0, next_sync_in)
        else:
            next_sync_in = 0
        
        success_rate = 0
        if self.sync_attempts > 0:
            success_rate = round((self.successful_syncs / self.sync_attempts) * 100, 1)
        
        return {
            "time_valid": self.is_time_valid(),
            "last_sync_success": self.last_sync_success,
            "time_since_sync": time_since_sync,
            "next_sync_in": next_sync_in,
            "sync_attempts": self.sync_attempts,
            "successful_syncs": self.successful_syncs,
            "consecutive_failures": self.consecutive_failures,
            "success_rate": success_rate,
            "current_time": self.get_local_datetime_string(),
            "current_server": self.ntp_servers[self.current_server_index],
            "uptime": self.get_uptime_string(),
            "timezone": self.get_timezone_info(),
            "should_sync_now": self.should_sync_time()
        }
    
    def reset(self):
        """Reset time manager state"""
        print("🔄 Resetting time manager...")
        self.last_sync_time = None
        self.last_sync_success = False
        self.consecutive_failures = 0
        self.current_server_index = 0
        print("✅ Time manager reset complete")


# Utility functions for backwards compatibility
def get_local_time_string_compat():
    """Backwards compatible time string function"""
    try:
        current_time = time.localtime()
        return f"{current_time.tm_hour:02d}:{current_time.tm_min:02d}:{current_time.tm_sec:02d}"
    except Exception:
        return "00:00:00"

def sync_time_compat(socket_pool, tz_offset=1):
    """Backwards compatible sync function"""
    try:
        ntp_client = adafruit_ntp.NTP(socket_pool, tz_offset=tz_offset)
        
        # Simple timeout implementation
        start_time = time.monotonic()
        while time.monotonic() - start_time < 10:
            try:
                current_time = ntp_client.datetime
                if current_time:
                    rtc.RTC().datetime = current_time
                    return True, None
            except:
                time.sleep(0.5)
        
        return False, "Timeout"
        
    except Exception as e:
        return False, str(e)