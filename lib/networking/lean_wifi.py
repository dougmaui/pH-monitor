# lib/networking/lean_wifi.py
"""
Memory-Efficient WiFi Module for ESP32-S3
Optimized for 8MB flash with minimal RAM usage and robust reconnection
"""
import time
import wifi
import socketpool

class WiFiManager:
    """Lean WiFi manager optimized for ESP32-S3 constraints"""
    
    def __init__(self, state_manager, primary_ssid, primary_password, 
                 backup_ssid=None, backup_password=None, pixel=None):
        self.state_manager = state_manager
        self.primary_ssid = primary_ssid
        self.primary_password = primary_password
        self.backup_ssid = backup_ssid
        self.backup_password = backup_password
        self.pixel = pixel
        
        # Minimal state tracking
        self.socket_pool = None
        self.last_rssi_check = 0
        self.consecutive_failures = 0
        self.connection_attempts = 0
        self.successful_connections = 0
        self.is_backup_network = False
        self.last_connection_time = 0
        
        # Lean configuration
        self.rssi_check_interval = 60  # Check signal every minute
        self.connection_timeout = 20   # Reduced timeout
        self.max_retry_attempts = 3    # Fewer retry attempts
        self.retry_delay = 10          # Fixed retry delay
        self.min_acceptable_rssi = -80 # Minimum signal strength
        
        # Register with state manager
        state_manager.register_component("wifi")
    
    def connect(self):
        """Connect to WiFi with minimal memory footprint"""
        self.connection_attempts += 1
        print(f"🌐 WiFi connection attempt #{self.connection_attempts}")
        
        # Try primary network first
        if self._try_network(self.primary_ssid, self.primary_password, False):
            return True
        
        # Try backup if available
        if self.backup_ssid and self._try_network(self.backup_ssid, self.backup_password, True):
            return True
        
        # Both failed
        self._handle_failure()
        return False
    
    def _try_network(self, ssid, password, is_backup):
        """Try connecting to a single network"""
        try:
            print(f"   Connecting to {ssid}...")
            self._set_pixel("connecting")
            
            # Disconnect if connected to wrong network
            if wifi.radio.connected:
                current_ssid = wifi.radio.ap_info.ssid if wifi.radio.ap_info else "unknown"
                if current_ssid != ssid:
                    print(f"   Disconnecting from {current_ssid}")
                    wifi.radio.stop_station()
                    time.sleep(1)
            
            wifi.radio.connect(ssid, password, timeout=self.connection_timeout)
            
            if wifi.radio.connected:
                self.socket_pool = socketpool.SocketPool(wifi.radio)
                self.consecutive_failures = 0
                self.successful_connections += 1
                self.is_backup_network = is_backup
                self.last_connection_time = time.monotonic()
                
                # Get connection info
                ip = wifi.radio.ipv4_address
                rssi = wifi.radio.ap_info.rssi if wifi.radio.ap_info else None
                
                print(f"   ✅ Connected to {ssid}")
                print(f"   IP: {ip}")
                if rssi:
                    print(f"   Signal: {rssi} dBm")
                
                self._set_pixel("connected")
                self.state_manager.update_component_health("wifi", "healthy")
                return True
                
        except Exception as e:
            print(f"   ❌ Connection to {ssid} failed: {e}")
        
        return False
    
    def _handle_failure(self):
        """Handle connection failure"""
        self.consecutive_failures += 1
        self.socket_pool = None
        self._set_pixel("failed")
        
        health = "failed" if self.consecutive_failures > 3 else "degraded"
        error_msg = f"Connection failed #{self.consecutive_failures}"
        self.state_manager.update_component_health("wifi", health, error_msg)
        
        print(f"   ❌ All networks failed (failure #{self.consecutive_failures})")
    
    def check_connection(self):
        """Lightweight connection monitoring"""
        current_time = time.monotonic()
        
        # Check if still connected
        if not wifi.radio.connected:
            print("⚠️  WiFi connection lost - attempting reconnect...")
            self._handle_failure()
            
            # Attempt automatic reconnection
            if self.connect():
                print("✅ WiFi automatically reconnected")
            
            return wifi.radio.connected
        
        # Check RSSI periodically
        if current_time - self.last_rssi_check > self.rssi_check_interval:
            self.last_rssi_check = current_time
            try:
                rssi = wifi.radio.ap_info.rssi if wifi.radio.ap_info else None
                if rssi:
                    if rssi < self.min_acceptable_rssi:
                        self.state_manager.update_component_health(
                            "wifi", "degraded", f"Weak signal: {rssi}dBm"
                        )
                    else:
                        self.state_manager.update_component_health("wifi", "healthy")
            except Exception as e:
                print(f"RSSI check error: {e}")
        
        return True
    
    def _set_pixel(self, status):
        """Minimal pixel status indication"""
        if not self.pixel:
            return
        try:
            colors = {
                "connecting": (25, 25, 0),  # Yellow
                "connected": (0, 25, 0),    # Green
                "failed": (25, 0, 0)        # Red
            }
            self.pixel[0] = colors.get(status, (0, 0, 0))
        except:
            pass
    
    def is_connected(self):
        """Check if WiFi is currently connected"""
        return wifi.radio.connected and self.socket_pool is not None
    
    def get_socket_pool(self):
        """Get socket pool if connected"""
        return self.socket_pool if self.is_connected() else None
    
    def disconnect(self):
        """Clean disconnect from WiFi"""
        try:
            if wifi.radio.connected:
                wifi.radio.stop_station()
            self.socket_pool = None
            print("📴 WiFi disconnected")
        except Exception as e:
            print(f"WiFi disconnect error: {e}")
    
    def reset(self):
        """Reset WiFi radio and attempt reconnection"""
        try:
            print("🔄 Resetting WiFi radio...")
            wifi.radio.enabled = False
            time.sleep(2)
            wifi.radio.enabled = True
            time.sleep(2)
            
            self.consecutive_failures = 0
            return self.connect()
            
        except Exception as e:
            error_msg = f"WiFi reset failed: {e}"
            self.state_manager.update_component_health("wifi", "failed", error_msg)
            print(f"❌ {error_msg}")
            return False
    
    def get_status(self):
        """Get minimal status for debugging"""
        current_time = time.monotonic()
        connection_uptime = (current_time - self.last_connection_time 
                           if self.last_connection_time else 0)
        
        status = {
            "connected": self.is_connected(),
            "ip": str(wifi.radio.ipv4_address) if wifi.radio.connected else None,
            "rssi": wifi.radio.ap_info.rssi if wifi.radio.ap_info else None,
            "failures": self.consecutive_failures,
            "backup": self.is_backup_network,
            "attempts": self.connection_attempts,
            "success_count": self.successful_connections,
            "uptime": connection_uptime
        }
        
        # Calculate success rate
        if self.connection_attempts > 0:
            status["success_rate"] = round(
                (self.successful_connections / self.connection_attempts) * 100, 1
            )
        else:
            status["success_rate"] = 0
        
        return status
    
    def force_reconnect(self):
        """Force a reconnection attempt"""
        print("🔄 Forcing WiFi reconnection...")
        self.disconnect()
        time.sleep(2)
        return self.connect()