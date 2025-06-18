# lib/core/system_init.py
"""
System Initialization Module
Handles initialization of all system managers and components
Extracted from main code.py for better organization
"""
import board
from lib.core.lean_state import StateManager
from lib.networking.lean_wifi import WiFiManager
from lib.networking.robust_mqtt import MQTTManager
from lib.time_sync.robust_time import TimeManager
from lib.utilities.i2c_safe import I2CSafeWrapper, create_safe_sensor_reader
from lib.sensors.ph_sensor import AtlasScientificPH
from lib.sensors.rtd_sensor import RTDSensor
from lib.sensors.measurement_integration import create_measurement_manager
from lib.oled_display.oled_display import (
    initialize_display,
    create_display_group,
)


def initialize_system_managers(
    watchdog_enabled,
    wdt,
    i2c,
    spi,
    pixel,
    wifi_ssid,
    wifi_password,
    io_username,
    io_key,
    tz_offset,
    safe_read_temperature,
):
    """Initialize all system managers and components"""
    print("🔧 Initializing robust system management...")
    if watchdog_enabled:
        wdt.feed()

    # Initialize state manager
    state_manager = StateManager(watchdog=wdt if watchdog_enabled else None)

    # Initialize I2C safety wrapper
    print("🛡️ Initializing I2C safety wrapper...")
    i2c_safe = I2CSafeWrapper(i2c, state_manager)

    # Register all components
    state_manager.register_component("wifi")
    state_manager.register_component("time")
    state_manager.register_component("temperature")
    state_manager.register_component("ph")
    state_manager.register_component("mqtt")
    state_manager.register_component("display")
    state_manager.register_component("i2c")

    if watchdog_enabled:
        wdt.feed()

    # Test I2C health first
    if i2c_safe.check_i2c_health():
        print("✅ I2C bus health check passed")
        state_manager.update_component_health("i2c", "healthy")
    else:
        print("⚠️ I2C bus health check failed")
        state_manager.update_component_health("i2c", "degraded", "Health check failed")

    if watchdog_enabled:
        wdt.feed()

    # Initialize sensors
    ph_sensor = AtlasScientificPH(i2c)

    # Initialize RTD sensor
    print("🌡️ Initializing RTD sensor...")
    try:
        rtd_sensor = RTDSensor(spi, board.D12, rtd_wires=3)
        rtd_initialized = rtd_sensor.initialize()
        if rtd_initialized:
            print("✅ RTD sensor initialized successfully")
        else:
            print("❌ RTD sensor initialization failed")
    except Exception as e:
        print(f"❌ RTD sensor error: {e}")
        rtd_sensor = None

    # Initialize TFT display with shared SPI
    print("🖥️ Initializing TFT display with shared SPI...")
    try:
        display = initialize_display(shared_spi=spi)
        display_group, ph_label, temp_c_label, temp_f_label, rssi_label, time_label = (
            create_display_group()
        )
        display.root_group = display_group
        print("✅ TFT display initialized successfully")
        state_manager.update_component_health("display", "healthy")
    except Exception as e:
        print(f"❌ Display initialization failed: {e}")
        state_manager.update_component_health("display", "failed", str(e))
        display = None
        ph_label = temp_c_label = temp_f_label = rssi_label = time_label = None

    # Create safe sensor reading functions
    safe_read_ph = create_safe_sensor_reader(i2c_safe, ph_sensor, "read_ph")

    # Initialize measurement manager
    print("📊 Initializing measurement integration...")
    measurement_manager = create_measurement_manager(
        state_manager, safe_read_temperature, safe_read_ph
    )

    # Initialize robust measurements
    measurement_manager.initialize_robust_measurements(ph_sensor, i2c_safe)

    if watchdog_enabled:
        wdt.feed()

    # Initialize robust managers
    print("🌐 Initializing robust WiFi manager...")
    wifi_manager = WiFiManager(
        state_manager,
        wifi_ssid,
        wifi_password,
        backup_ssid=None,
        backup_password=None,
        pixel=pixel,
    )

    print("🕐 Initializing robust time manager...")
    time_manager = TimeManager(state_manager, wifi_manager, timezone_offset=tz_offset)

    print("📡 Initializing robust MQTT manager...")
    mqtt_manager = MQTTManager(state_manager, wifi_manager, io_username, io_key)

    if watchdog_enabled:
        wdt.feed()

    return {
        "state_manager": state_manager,
        "i2c_safe": i2c_safe,
        "ph_sensor": ph_sensor,
        "rtd_sensor": rtd_sensor,
        "display": display,
        "ph_label": ph_label,
        "temp_c_label": temp_c_label,
        "temp_f_label": temp_f_label,
        "rssi_label": rssi_label,
        "time_label": time_label,
        "safe_read_ph": safe_read_ph,
        "wifi_manager": wifi_manager,
        "time_manager": time_manager,
        "mqtt_manager": mqtt_manager,
        "measurement_manager": measurement_manager,
    }
