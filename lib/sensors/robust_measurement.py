# lib/sensors/robust_measurement.py
"""
Robust Measurement System - Statistical Processing Core
Provides multi-sample averaging with outlier detection and noise reduction
Professional-grade measurement precision for pH monitoring systems
"""
import time
import math


class MeasurementResult:
    """Container for robust measurement results with statistical analysis"""

    def __init__(self, samples, outliers_removed=0):
        self.raw_samples = samples
        self.outliers_removed = outliers_removed
        self.sample_count = len(samples)

        if samples:
            self._calculate_statistics()
        else:
            self.mean = None
            self.std_dev = float("inf")
            self.confidence_interval = (None, None)
            self.is_stable = False

    def _calculate_statistics(self):
        """Calculate statistical properties of the measurement samples"""
        n = len(self.raw_samples)

        # Calculate mean
        self.mean = sum(self.raw_samples) / n

        # Calculate standard deviation
        if n > 1:
            variance = sum((x - self.mean) ** 2 for x in self.raw_samples) / (n - 1)
            self.std_dev = math.sqrt(variance)
        else:
            self.std_dev = 0.0

        # Calculate 95% confidence interval (assuming normal distribution)
        if n > 1:
            # t-distribution critical value for 95% confidence (approximation for n>2)
            t_critical = (
                2.0 if n <= 3 else (2.776 if n <= 5 else 2.0)
            )  # Conservative estimate
            margin_of_error = t_critical * (self.std_dev / math.sqrt(n))
            self.confidence_interval = (
                self.mean - margin_of_error,
                self.mean + margin_of_error,
            )
        else:
            self.confidence_interval = (self.mean, self.mean)

        # Determine if measurement is stable (low noise)
        # For temperature: stable if std_dev < 0.1°C
        # For pH: stable if std_dev < 0.05
        if hasattr(self, "_measurement_type"):
            if self._measurement_type == "temperature":
                self.is_stable = self.std_dev < 0.1
            elif self._measurement_type == "ph":
                self.is_stable = self.std_dev < 0.05
            else:
                self.is_stable = self.std_dev < 0.1  # Default threshold
        else:
            # Auto-detect based on typical ranges
            if self.mean and 15 < self.mean < 50:  # Likely temperature in °C
                self.is_stable = self.std_dev < 0.1
            elif self.mean and 0 < self.mean < 14:  # Likely pH
                self.is_stable = self.std_dev < 0.05
            else:
                self.is_stable = self.std_dev < 0.1  # Default


class RobustMeasurementBase:
    """Base class for robust measurement implementations"""

    def __init__(self, sample_delay=0.3):
        self.sample_delay = sample_delay
        self.total_measurements = 0
        self.successful_measurements = 0
        self.noise_reduction_history = []
        self.last_measurement_time = 0

        # Statistical thresholds
        self.outlier_threshold = 2.0  # Standard deviations for outlier detection
        self.max_outliers_percent = 0.3  # Max 30% outliers allowed

    def _collect_samples(self, sample_count, sensor_function):
        """Collect multiple samples from sensor with timing and error handling"""
        samples = []
        errors = []

        print(f"     Collecting {sample_count} samples...")

        for i in range(sample_count):
            try:
                start_time = time.monotonic()

                # Get sample from sensor
                sample = sensor_function()

                # Handle different return types
                if isinstance(sample, tuple):
                    value = sample[0]  # Extract value from (value, source) tuple
                elif isinstance(sample, (int, float)):
                    value = sample
                else:
                    print(f"     Sample {i+1}: Invalid type {type(sample)}")
                    continue

                # Validate sample
                if (
                    isinstance(value, (int, float))
                    and not math.isnan(value)
                    and not math.isinf(value)
                ):
                    samples.append(value)
                    elapsed = time.monotonic() - start_time
                    print(f"     Sample {i+1}: {value:.3f} ({elapsed:.2f}s)")
                else:
                    print(f"     Sample {i+1}: Invalid value {value}")
                    errors.append(f"Invalid value: {value}")

                # Delay between samples (except for last sample)
                if i < sample_count - 1:
                    time.sleep(self.sample_delay)

            except Exception as e:
                print(f"     Sample {i+1}: Error - {e}")
                errors.append(str(e))

                # Still delay on error to maintain timing
                if i < sample_count - 1:
                    time.sleep(self.sample_delay)

        print(f"     Collected {len(samples)}/{sample_count} valid samples")
        if errors:
            print(f"     Errors encountered: {len(errors)}")

        return samples, errors

    def _remove_outliers(self, samples):
        """Remove statistical outliers using modified Z-score method"""
        if len(samples) < 3:
            return samples, 0  # Need at least 3 samples for outlier detection

        # Calculate median and median absolute deviation (MAD)
        sorted_samples = sorted(samples)
        n = len(sorted_samples)
        median = (
            sorted_samples[n // 2]
            if n % 2 == 1
            else (sorted_samples[n // 2 - 1] + sorted_samples[n // 2]) / 2
        )

        # Calculate MAD
        deviations = [abs(x - median) for x in samples]
        mad = sorted(deviations)[len(deviations) // 2] if deviations else 0

        # Modified Z-score threshold (more robust than standard deviation)
        threshold = 3.5  # Conservative threshold for outlier detection

        # Identify outliers
        filtered_samples = []
        outliers_removed = 0

        for sample in samples:
            if mad == 0:
                # If MAD is 0, all samples are identical - no outliers
                filtered_samples.append(sample)
            else:
                modified_z_score = 0.6745 * (sample - median) / mad
                if abs(modified_z_score) <= threshold:
                    filtered_samples.append(sample)
                else:
                    outliers_removed += 1
                    print(
                        f"     Outlier removed: {sample:.3f} (z-score: {modified_z_score:.2f})"
                    )

        # Ensure we don't remove too many samples
        max_outliers = int(len(samples) * self.max_outliers_percent)
        if outliers_removed > max_outliers:
            print(
                f"     Too many outliers detected ({outliers_removed}), keeping original samples"
            )
            return samples, 0

        if outliers_removed > 0:
            print(
                f"     Removed {outliers_removed} outliers, {len(filtered_samples)} samples remain"
            )

        return filtered_samples, outliers_removed

    def take_measurement(self, sample_count, sensor_function):
        """Take a robust measurement with multiple samples and statistical processing"""
        self.total_measurements += 1
        self.last_measurement_time = time.monotonic()

        start_time = time.monotonic()

        try:
            # Collect raw samples
            raw_samples, errors = self._collect_samples(sample_count, sensor_function)

            if len(raw_samples) < 2:
                print(
                    f"     ❌ Insufficient samples: {len(raw_samples)}/{sample_count}"
                )
                return None

            # Remove outliers
            filtered_samples, outliers_removed = self._remove_outliers(raw_samples)

            if len(filtered_samples) < 2:
                print(
                    f"     ❌ Too few samples after outlier removal: {len(filtered_samples)}"
                )
                return None

            # Create measurement result
            result = MeasurementResult(filtered_samples, outliers_removed)

            # Calculate noise reduction (compared to single sample standard deviation)
            if len(raw_samples) > 1:
                single_sample_noise = max(raw_samples) - min(raw_samples)
                robust_noise = (
                    result.confidence_interval[1] - result.confidence_interval[0]
                )
                noise_reduction = max(0, single_sample_noise - robust_noise)
                self.noise_reduction_history.append(noise_reduction)

                # Keep only recent history
                if len(self.noise_reduction_history) > 20:
                    self.noise_reduction_history.pop(0)

            elapsed = time.monotonic() - start_time

            if result.is_stable:
                self.successful_measurements += 1
                print(
                    f"     ✅ Robust measurement complete: {result.mean:.3f} ± {result.std_dev:.3f} ({elapsed:.2f}s)"
                )
            else:
                print(
                    f"     ⚠️ Measurement unstable: {result.mean:.3f} ± {result.std_dev:.3f} ({elapsed:.2f}s)"
                )

            return result

        except Exception as e:
            print(f"     ❌ Robust measurement failed: {e}")
            return None

    def get_statistics(self):
        """Get measurement statistics and performance metrics"""
        success_rate = (
            (self.successful_measurements / self.total_measurements * 100)
            if self.total_measurements > 0
            else 0
        )

        avg_noise_reduction = (
            (sum(self.noise_reduction_history) / len(self.noise_reduction_history))
            if self.noise_reduction_history
            else 0
        )

        return {
            "total_measurements": self.total_measurements,
            "successful_measurements": self.successful_measurements,
            "success_rate": round(success_rate, 1),
            "average_noise_reduction": round(avg_noise_reduction, 4),
            "sample_delay": self.sample_delay,
            "last_measurement_age": (
                time.monotonic() - self.last_measurement_time
                if self.last_measurement_time
                else None
            ),
        }


class RobustTemperatureMeasurement(RobustMeasurementBase):
    """Robust temperature measurement with multi-sample averaging"""

    def __init__(self, sensor_function, sample_delay=0.3):
        super().__init__(sample_delay)
        self.sensor_function = sensor_function

    def take_measurement(self, sample_count=5):
        """Take robust temperature measurement"""
        print(
            f"   🔬 Taking robust temperature measurement ({sample_count} samples)..."
        )

        result = super().take_measurement(sample_count, self.sensor_function)

        if result:
            result._measurement_type = "temperature"
            # Recalculate stability with temperature-specific threshold
            result.is_stable = result.std_dev < 0.1  # 0.1°C threshold for temperature

        return result


class RobustpHMeasurement(RobustMeasurementBase):
    """Robust pH measurement with multi-sample averaging and I2C safety"""

    def __init__(self, ph_sensor, i2c_safe, sample_delay=0.3):
        super().__init__(sample_delay)
        self.ph_sensor = ph_sensor
        self.i2c_safe = i2c_safe

    def _safe_ph_read(self):
        """Safely read pH using I2C safety wrapper"""
        return self.i2c_safe.safe_read_sensor(
            self.ph_sensor.read_ph, "pH_robust_sample"
        )

    def take_measurement(self, sample_count=10):
        """Take robust pH measurement with I2C safety"""
        print(f"   🔬 Taking robust pH measurement ({sample_count} samples)...")

        result = super().take_measurement(sample_count, self._safe_ph_read)

        if result:
            result._measurement_type = "ph"
            # Recalculate stability with pH-specific threshold
            result.is_stable = result.std_dev < 0.05  # 0.05 pH units threshold

        return result


# Utility functions for backwards compatibility and testing
def test_robust_measurements():
    """Test function for robust measurement system"""
    print("🧪 Testing robust measurement system...")

    # Test with simulated noisy data
    def noisy_sensor():
        import random

        base_value = 7.0
        noise = random.uniform(-0.2, 0.2)
        return base_value + noise

    # Create test measurement
    test_measurement = RobustMeasurementBase()
    result = test_measurement.take_measurement(10, noisy_sensor)

    if result:
        print(f"   Test result: {result.mean:.3f} ± {result.std_dev:.3f}")
        print(f"   Stable: {result.is_stable}")
        print(
            f"   Confidence interval: {result.confidence_interval[0]:.3f} - {result.confidence_interval[1]:.3f}"
        )
    else:
        print("   Test failed")

    return result is not None


if __name__ == "__main__":
    # Run test if module is executed directly
    test_robust_measurements()
