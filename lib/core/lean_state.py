# lib/core/lean_state.py  
"""
Minimal State Manager for ESP32-S3
CircuitPython compatible - no typing imports
"""
import time

class SystemState:
    """Simplified system states"""
    STARTING = 0
    HEALTHY = 1
    DEGRADED = 2
    CRITICAL = 3

class StateManager:
    """Memory-efficient state manager"""
    
    def __init__(self, watchdog=None):
        self.state = SystemState.STARTING
        self.watchdog = watchdog
        
        # Minimal component tracking
        self.components = {}  # name -> health_level (0=healthy, 1=degraded, 2=failed)
        self.alerts = []      # Keep only last 5 alerts
        self.readings = {}    # Latest sensor readings only
        
        # Hot tub safety thresholds
        self.temp_critical = 107.0  # °F
        self.temp_warning = 105.0   # °F
        
    def register_component(self, name):
        """Register a component"""
        self.components[name] = 2  # Start as unknown/failed
    
    def update_component_health(self, name, health, error=None):
        """Update component health with string values"""
        health_map = {"healthy": 0, "degraded": 1, "failed": 2}
        old_health = self.components.get(name, 2)
        self.components[name] = health_map.get(health, 2)
        
        if error and health != "healthy":
            self.add_alert(f"{name}: {error}")
        
        # Update system state if health changed
        if old_health != self.components[name]:
            self._update_system_state()
    
    def update_reading(self, sensor, value, timestamp=None):
        """Store latest sensor reading"""
        if timestamp is None:
            timestamp = time.monotonic()
        self.readings[sensor] = {"value": value, "time": timestamp}
        
        # Temperature safety check
        if sensor == "temperature" and isinstance(value, (int, float)):
            if value >= self.temp_critical:
                self.add_alert(f"CRITICAL: Temp {value}°F!", "critical")
                self.state = SystemState.CRITICAL
            elif value >= self.temp_warning:
                self.add_alert(f"WARNING: Temp {value}°F high")
    
    def _update_system_state(self):
        """Update overall system state"""
        failed = sum(1 for h in self.components.values() if h == 2)
        degraded = sum(1 for h in self.components.values() if h == 1)
        
        if "temperature" in self.components and self.components["temperature"] == 2:
            self.state = SystemState.CRITICAL  # No temperature = safety risk
        elif failed >= 2:
            self.state = SystemState.CRITICAL
        elif failed >= 1 or degraded >= 2:
            self.state = SystemState.DEGRADED
        else:
            self.state = SystemState.HEALTHY
    
    def add_alert(self, message, severity="warning"):
        """Add alert with memory management"""
        alert = {"msg": message, "sev": severity, "time": time.monotonic()}
        self.alerts.append(alert)
        
        # Keep only last 5 alerts to save memory
        if len(self.alerts) > 5:
            self.alerts.pop(0)
        
        print(f"ALERT: {message}")
    
    def get_reading(self, sensor, max_age=60):
        """Get recent sensor reading"""
        reading = self.readings.get(sensor)
        if not reading:
            return None
        
        age = time.monotonic() - reading["time"]
        return reading["value"] if age <= max_age else None
    
    def should_continue(self):
        """Check if system should continue operating"""
        return self.state != SystemState.CRITICAL
    
    def feed_watchdog(self):
        """Feed watchdog if system is healthy enough"""
        if self.watchdog and self.should_continue():
            try:
                self.watchdog.feed()
            except:
                pass
    
    def get_status(self):
        """Get minimal status summary"""
        state_names = ["STARTING", "HEALTHY", "DEGRADED", "CRITICAL"]
        temp_reading = self.get_reading("temperature", 120)
        temp_safe = True
        if temp_reading:
            temp_safe = temp_reading < self.temp_critical
        
        return {
            "state": state_names[self.state],
            "components": {name: ["OK", "WARN", "FAIL"][health] 
                          for name, health in self.components.items()},
            "alerts": len(self.alerts),
            "temp_safe": temp_safe
        }