# lib/sensors/measurement_integration.py
"""
Testing Stub for Measurement Integration
Implements minimal interface to test code.py integration without breaking existing functionality
"""


class MeasurementManagerStub:
    """Stub measurement manager that passes through to existing functions"""

    def __init__(self, state_manager, safe_read_temperature_func, safe_read_ph_func):
        self.state_manager = state_manager
        self.safe_read_temperature = safe_read_temperature_func
        self.safe_read_ph = safe_read_ph_func
        self.enabled = False  # Start disabled for testing
        print("📊 Measurement manager stub initialized (robust measurements disabled)")

    def initialize_robust_measurements(self, ph_sensor, i2c_safe):
        """Stub initialization - always returns False for now"""
        print("📊 Robust measurements disabled - using single readings only")
        return False

    def read_temperature(self):
        """Pass through to existing temperature function"""
        try:
            temp_c, temp_source = self.safe_read_temperature()
            quality_info = {"method": "single_reading_passthrough"}
            return temp_c, temp_source, quality_info
        except Exception as e:
            print(f"   ❌ Temperature stub error: {e}")
            return 39.0, "fallback", {"method": "fallback", "error": str(e)}

    def read_ph(self):
        """Pass through to existing pH function"""
        try:
            ph_value = self.safe_read_ph()
            if isinstance(ph_value, (int, float)):
                quality_info = {"method": "single_reading_passthrough"}
                return ph_value, "single", quality_info
            else:
                return (
                    None,
                    "error",
                    {"method": "single_reading", "error": "sensor_timeout"},
                )
        except Exception as e:
            print(f"   ❌ pH stub error: {e}")
            return None, "error", {"method": "single_reading", "error": str(e)}

    def get_statistics(self):
        """Return stub statistics"""
        return {
            "enabled": self.enabled,
            "temp_readings": 0,
            "ph_readings": 0,
            "temp_robust_success_rate": 0.0,
            "ph_robust_success_rate": 0.0,
            "status": "stub_mode",
        }


def create_measurement_manager(
    state_manager, safe_read_temperature_func, safe_read_ph_func
):
    """Create stub measurement manager"""
    return MeasurementManagerStub(
        state_manager, safe_read_temperature_func, safe_read_ph_func
    )
