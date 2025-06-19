# lib/sensors/rtd_sensor.py
# RTD sensor management with MAX31865 amplifier
# Extracted from main code for better organization

import board
import digitalio
import time


class RTDSensor:
    """Manages RTD temperature sensor with MAX31865 amplifier"""

    def __init__(self, spi_bus, cs_pin=board.D12, rtd_wires=3, watchdog=None):
        self.spi = spi_bus
        self.cs_pin = cs_pin
        self.rtd_wires = rtd_wires
        self.watchdog = watchdog

        # RTD state
        self.rtd_sensor = None
        self.rtd_working = False
        self.cs_rtd = None

        # Statistics
        self.initialization_attempts = 0
        self.read_attempts = 0
        self.successful_reads = 0
        self.last_fault_register = None

    def initialize(self):
        """Initialize RTD sensor with comprehensive testing"""
        self.initialization_attempts += 1
        print(
            f"🧪 Testing RTD sensor (MAX31865) - Attempt #{self.initialization_attempts}..."
        )

        try:
            import adafruit_max31865

            # Initialize CS pin for RTD
            self.cs_rtd = digitalio.DigitalInOut(self.cs_pin)
            self.cs_rtd.direction = digitalio.Direction.OUTPUT

            # Initialize MAX31865 with shared SPI
            self.rtd_sensor = adafruit_max31865.MAX31865(
                self.spi, self.cs_rtd, wires=self.rtd_wires
            )
            self.rtd_sensor.clear_faults()
            print("   ✅ RTD sensor initialized successfully")

            # Test reading
            test_temp_c = self.rtd_sensor.temperature
            test_temp_f = test_temp_c * 9 / 5 + 32
            test_resistance = self.rtd_sensor.resistance
            test_fault = self.rtd_sensor.fault

            print(f"   🌡️ RTD Reading: {test_temp_c:.2f}°C / {test_temp_f:.1f}°F")
            print(f"   🔧 RTD Resistance: {test_resistance:.1f} ohms")

            # Handle fault register properly (could be tuple or int)
            fault_val = self._parse_fault_register(test_fault)
            self.last_fault_register = fault_val

            print(f"   📊 RTD Fault Register: 0x{fault_val:02x}")
            if fault_val == 0:
                print("   ✅ RTD sensor working correctly - no faults")
                self.rtd_working = True
            else:
                print(f"   ⚠️ RTD has faults: 0x{fault_val:02x}")
                self.rtd_working = False

        except Exception as e:
            print(f"   ❌ RTD initialization failed: {e}")
            self.rtd_working = False
            self.rtd_sensor = None

        print("   📝 RTD initialization complete\n")
        return self.rtd_working

    def _parse_fault_register(self, fault_data):
        """Parse fault register (handles tuple or int)"""
        try:
            if isinstance(fault_data, tuple):
                return fault_data[0] if fault_data else 0
            else:
                return fault_data if fault_data is not None else 0
        except Exception as fault_error:
            print(f"   ⚠️ Fault register read error: {fault_error}")
            print("   Assuming no faults - sensor appears to be working")
            return 0

    def read_temperature(self):
        """Read temperature from RTD sensor"""
        self.read_attempts += 1

        if not self.rtd_working or not self.rtd_sensor:
            return None, "not_initialized"

        try:
            # Feed watchdog during read if available
            if self.watchdog:
                self.watchdog.feed()

            temp_c = self.rtd_sensor.temperature

            # Validate reading
            if isinstance(temp_c, (int, float)) and -50 < temp_c < 150:
                self.successful_reads += 1
                return temp_c, "rtd"
            else:
                print(f"   ⚠️ RTD reading out of range: {temp_c}")
                return None, "out_of_range"

        except Exception as e:
            print(f"   ⚠️ RTD read error: {e}")
            return None, "read_error"

    def get_status(self):
        """Get comprehensive RTD status"""
        current_temp = None
        current_fault = None

        if self.rtd_working and self.rtd_sensor:
            try:
                current_temp = self.rtd_sensor.temperature
                current_fault = self._parse_fault_register(self.rtd_sensor.fault)
            except:
                pass

        success_rate = 0
        if self.read_attempts > 0:
            success_rate = round((self.successful_reads / self.read_attempts) * 100, 1)

        return {
            "initialized": self.rtd_working,
            "sensor_present": self.rtd_sensor is not None,
            "current_temp_c": current_temp,
            "current_temp_f": current_temp * 9 / 5 + 32 if current_temp else None,
            "current_fault": current_fault,
            "last_fault": self.last_fault_register,
            "initialization_attempts": self.initialization_attempts,
            "read_attempts": self.read_attempts,
            "successful_reads": self.successful_reads,
            "success_rate": success_rate,
            "cs_pin": str(self.cs_pin),
            "rtd_wires": self.rtd_wires,
            "health": self._get_health_status(),
        }

    def _get_health_status(self):
        """Determine RTD health status"""
        if not self.rtd_working:
            return "failed"
        elif self.last_fault_register and self.last_fault_register != 0:
            return "degraded"
        elif self.read_attempts > 0:
            success_rate = (self.successful_reads / self.read_attempts) * 100
            if success_rate > 95:
                return "healthy"
            elif success_rate > 80:
                return "degraded"
            else:
                return "failed"
        else:
            return "unknown"

    def clear_faults(self):
        """Clear RTD fault register"""
        if self.rtd_sensor:
            try:
                self.rtd_sensor.clear_faults()
                print("   🔧 RTD faults cleared")
                return True
            except Exception as e:
                print(f"   ❌ Failed to clear RTD faults: {e}")
                return False
        return False

    def reset(self):
        """Reset RTD sensor"""
        print("🔄 Resetting RTD sensor...")
        self.rtd_working = False
        self.rtd_sensor = None
        if self.cs_rtd:
            try:
                self.cs_rtd.deinit()
            except:
                pass
        self.cs_rtd = None

        # Reset statistics
        self.read_attempts = 0
        self.successful_reads = 0
        self.last_fault_register = None

        return self.initialize()


# Convenience function for backwards compatibility
def create_rtd_sensor(spi_bus, watchdog=None):
    """Create and initialize RTD sensor"""
    rtd = RTDSensor(spi_bus, watchdog=watchdog)
    rtd.initialize()
    return rtd
