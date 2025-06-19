# lib/sensors/measurement_integration.py
"""
Robust Measurement Integration Module
Provides multi-sample averaging with statistical analysis and noise reduction
Handles automatic fallback from robust -> single -> nominal readings
"""
import time


class MeasurementManager:
    """
    Manages integration between single readings and robust multi-sample measurements
    Provides clean interface for main code with automatic fallback
    """

    def __init__(self, state_manager, safe_read_temperature_func, safe_read_ph_func):
        self.state_manager = state_manager
        self.safe_read_temperature = safe_read_temperature_func
        self.safe_read_ph = safe_read_ph_func

        # Configuration - start with robust measurements enabled
        self.enable_robust = True
        self.temp_sample_count = 5
        self.ph_sample_count = 10
        self.sample_delay = 0.3  # Reduced for faster cycling

        # Robust measurement objects (initialized later)
        self.temp_robust = None
        self.ph_robust = None

        # Statistics
        self.total_temp_readings = 0
        self.total_ph_readings = 0
        self.robust_temp_success = 0
        self.robust_ph_success = 0

        # Register component
        self.state_manager.register_component("measurement_manager")
        print("📊 Measurement manager initialized (robust measurements enabled)")

    def initialize_robust_measurements(self, ph_sensor, i2c_safe):
        """Initialize robust measurement objects"""
        if not self.enable_robust:
            print("📊 Robust measurements disabled by configuration")
            self.state_manager.update_component_health(
                "measurement_manager", "degraded", "Disabled"
            )
            return False

        try:
            # Try to import robust measurement classes
            from lib.sensors.robust_measurement import (
                RobustTemperatureMeasurement,
                RobustpHMeasurement,
            )

            print("📊 Initializing robust measurement system...")

            # Initialize temperature robust measurement
            self.temp_robust = RobustTemperatureMeasurement(
                sensor_function=self.safe_read_temperature,
                sample_delay=self.sample_delay,
            )

            # Initialize pH robust measurement
            self.ph_robust = RobustpHMeasurement(
                ph_sensor=ph_sensor, i2c_safe=i2c_safe, sample_delay=self.sample_delay
            )

            print("✅ Robust measurement system initialized")
            self.state_manager.update_component_health("measurement_manager", "healthy")
            return True

        except ImportError as e:
            print(f"⚠️ Robust measurement system not available: {e}")
            print("   Continuing with single readings only")
            self.enable_robust = False
            self.state_manager.update_component_health(
                "measurement_manager", "degraded", "Module unavailable"
            )
            return False

        except Exception as e:
            print(f"⚠️ Robust measurement initialization failed: {e}")
            print("   Falling back to single readings")
            self.enable_robust = False
            self.temp_robust = None
            self.ph_robust = None
            self.state_manager.update_component_health(
                "measurement_manager", "failed", str(e)
            )
            return False

    def read_temperature(self):
        """
        Read temperature with robust measurement if available, fallback to single reading
        Returns: (temp_c, temp_source, quality_info)
        """
        self.total_temp_readings += 1

        # Try robust measurement first
        if self.enable_robust and self.temp_robust:
            try:
                print(f"   🔬 Robust temperature ({self.temp_sample_count} samples)...")
                temp_result = self.temp_robust.take_measurement(
                    sample_count=self.temp_sample_count
                )

                if temp_result and temp_result.is_stable:
                    self.robust_temp_success += 1
                    temp_c = temp_result.mean
                    temp_source = "robust"
                    quality_info = {
                        "std_dev": temp_result.std_dev,
                        "confidence_interval": temp_result.confidence_interval,
                        "sample_count": temp_result.sample_count,
                        "outliers_removed": temp_result.outliers_removed,
                    }

                    print(
                        f"   🌡️ Temperature (robust): {temp_c:.2f}°C (±{temp_result.std_dev:.3f}°C, {temp_result.sample_count} samples)"
                    )

                    # Update state with quality metrics
                    self.state_manager.update_reading(
                        "temp_std_dev", temp_result.std_dev
                    )
                    self.state_manager.update_reading(
                        "temp_confidence_width",
                        temp_result.confidence_interval[1]
                        - temp_result.confidence_interval[0],
                    )

                    return temp_c, temp_source, quality_info
                else:
                    print(
                        f"   ⚠️ Robust temperature measurement unstable, falling back to single reading"
                    )

            except Exception as e:
                print(f"   ❌ Robust temperature measurement failed: {e}")

        # Fallback to single reading
        try:
            temp_c, temp_source = self.safe_read_temperature()
            quality_info = {"method": "single_reading"}
            print(f"   🌡️ Temperature (single): {temp_c:.1f}°C ({temp_source})")
            return temp_c, f"{temp_source}_single", quality_info

        except Exception as e:
            print(f"   ❌ Temperature reading failed: {e}")
            # Ultimate fallback
            fallback_temp = 39.0  # 103°F in Celsius
            return fallback_temp, "fallback", {"method": "fallback", "error": str(e)}

    def read_ph(self):
        """
        Read pH with robust measurement if available, fallback to single reading
        Returns: (ph_value, ph_source, quality_info)
        """
        self.total_ph_readings += 1

        # Try robust measurement first
        if self.enable_robust and self.ph_robust:
            try:
                print(f"   🔬 Robust pH ({self.ph_sample_count} samples)...")
                ph_result = self.ph_robust.take_measurement(
                    sample_count=self.ph_sample_count
                )

                if ph_result and ph_result.is_stable:
                    self.robust_ph_success += 1
                    ph_value = ph_result.mean
                    ph_source = "robust"
                    quality_info = {
                        "std_dev": ph_result.std_dev,
                        "confidence_interval": ph_result.confidence_interval,
                        "sample_count": ph_result.sample_count,
                        "outliers_removed": ph_result.outliers_removed,
                    }

                    print(
                        f"   🧪 pH (robust): {ph_value:.3f} (±{ph_result.std_dev:.3f}, {ph_result.sample_count} samples)"
                    )

                    # Update state with quality metrics
                    self.state_manager.update_reading("ph_std_dev", ph_result.std_dev)
                    self.state_manager.update_reading(
                        "ph_confidence_width",
                        ph_result.confidence_interval[1]
                        - ph_result.confidence_interval[0],
                    )

                    return ph_value, ph_source, quality_info
                else:
                    print(
                        f"   ⚠️ Robust pH measurement unstable, falling back to single reading"
                    )

            except Exception as e:
                print(f"   ❌ Robust pH measurement failed: {e}")

        # Fallback to single reading
        try:
            ph_value = self.safe_read_ph()
            if isinstance(ph_value, (int, float)):
                quality_info = {"method": "single_reading"}
                print(f"   🧪 pH (single): {ph_value:.2f}")
                return ph_value, "single", quality_info
            else:
                # pH sensor returned error/timeout
                return (
                    None,
                    "error",
                    {"method": "single_reading", "error": "sensor_timeout"},
                )

        except Exception as e:
            print(f"   ❌ pH reading failed: {e}")
            return None, "error", {"method": "single_reading", "error": str(e)}

    def get_statistics(self):
        """Get measurement manager statistics"""
        temp_robust_rate = (
            (self.robust_temp_success / self.total_temp_readings * 100)
            if self.total_temp_readings > 0
            else 0
        )
        ph_robust_rate = (
            (self.robust_ph_success / self.total_ph_readings * 100)
            if self.total_ph_readings > 0
            else 0
        )

        stats = {
            "enabled": self.enable_robust,
            "temp_readings": self.total_temp_readings,
            "ph_readings": self.total_ph_readings,
            "temp_robust_success_rate": round(temp_robust_rate, 1),
            "ph_robust_success_rate": round(ph_robust_rate, 1),
            "temp_sample_count": self.temp_sample_count,
            "ph_sample_count": self.ph_sample_count,
            "sample_delay": self.sample_delay,
        }

        # Add robust measurement statistics if available
        if self.temp_robust:
            try:
                temp_robust_stats = self.temp_robust.get_statistics()
                stats["temp_noise_reduction"] = temp_robust_stats.get(
                    "average_noise_reduction", 0
                )
            except:
                pass

        if self.ph_robust:
            try:
                ph_robust_stats = self.ph_robust.get_statistics()
                stats["ph_noise_reduction"] = ph_robust_stats.get(
                    "average_noise_reduction", 0
                )
            except:
                pass

        return stats

    def configure(self, **kwargs):
        """Configure measurement parameters"""
        if "enable_robust" in kwargs:
            self.enable_robust = kwargs["enable_robust"]
            print(
                f"📊 Robust measurements {'enabled' if self.enable_robust else 'disabled'}"
            )

        if "temp_sample_count" in kwargs:
            self.temp_sample_count = kwargs["temp_sample_count"]
            print(f"📊 Temperature sample count: {self.temp_sample_count}")

        if "ph_sample_count" in kwargs:
            self.ph_sample_count = kwargs["ph_sample_count"]
            print(f"📊 pH sample count: {self.ph_sample_count}")

        if "sample_delay" in kwargs:
            self.sample_delay = kwargs["sample_delay"]
            print(f"📊 Sample delay: {self.sample_delay}s")

    def reset_statistics(self):
        """Reset measurement statistics"""
        self.total_temp_readings = 0
        self.total_ph_readings = 0
        self.robust_temp_success = 0
        self.robust_ph_success = 0
        print("📊 Measurement statistics reset")


# Simple fallback implementation if robust_measurement module not available
class SimpleMeasurement:
    """Simple measurement result for fallback"""

    def __init__(self, value):
        self.mean = value
        self.std_dev = 0.0
        self.confidence_interval = (value, value)
        self.sample_count = 1
        self.outliers_removed = 0
        self.is_stable = True


class FallbackRobustMeasurement:
    """Fallback robust measurement that just does single readings"""

    def __init__(self, sensor_function, sample_delay=0.3):
        self.sensor_function = sensor_function
        self.sample_delay = sample_delay
        self.total_measurements = 0

    def take_measurement(self, sample_count=1):
        """Take a single measurement and wrap it as a 'robust' result"""
        self.total_measurements += 1
        try:
            if hasattr(self.sensor_function, "__call__"):
                # It's a function
                result = self.sensor_function()
                if isinstance(result, tuple):
                    value = result[0]  # Get temperature value from (temp, source) tuple
                else:
                    value = result
            else:
                # It's a sensor object
                value = self.sensor_function.read_ph()

            if isinstance(value, (int, float)):
                return SimpleMeasurement(value)
            else:
                return None
        except Exception as e:
            print(f"   Fallback measurement error: {e}")
            return None

    def get_statistics(self):
        return {
            "total_measurements": self.total_measurements,
            "average_noise_reduction": 0.0,
        }


class FallbackpHMeasurement(FallbackRobustMeasurement):
    """Fallback pH measurement"""

    def __init__(self, ph_sensor, i2c_safe, sample_delay=0.3):
        self.ph_sensor = ph_sensor
        self.i2c_safe = i2c_safe
        self.sample_delay = sample_delay
        self.total_measurements = 0

    def take_measurement(self, sample_count=1):
        """Take a single pH measurement"""
        self.total_measurements += 1
        try:
            ph_value = self.ph_sensor.read_ph()
            if isinstance(ph_value, (int, float)):
                return SimpleMeasurement(ph_value)
            else:
                return None
        except Exception as e:
            print(f"   Fallback pH measurement error: {e}")
            return None


# Auto-fallback creation functions
def create_measurement_manager(
    state_manager, safe_read_temperature_func, safe_read_ph_func
):
    """Create and return a configured measurement manager"""
    manager = MeasurementManager(
        state_manager, safe_read_temperature_func, safe_read_ph_func
    )

    # If robust_measurement module is not available, create fallback robust measurement objects
    if manager.enable_robust and not manager.temp_robust:
        print("📊 Creating fallback robust measurement objects...")
        try:
            manager.temp_robust = FallbackRobustMeasurement(safe_read_temperature_func)
            manager.ph_robust = None  # Will be set in initialize_robust_measurements
            print("✅ Fallback robust measurements ready")
        except Exception as e:
            print(f"⚠️ Fallback creation failed: {e}")
            manager.enable_robust = False

    return manager
