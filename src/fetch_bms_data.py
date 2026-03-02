"""
Seplos V2 / V15 BMS Data Fetcher
Reads one or more Seplos protocol v2.0 BMS (in parallel) via
(remote) serial connection(s) and publishes their data to MQTT
"""
import sys
import os
import signal
import logging
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import json
from typing import Optional, Dict, Any, Union, List, Callable, Tuple
import serial
from serial.serialutil import SerialException
import paho.mqtt.client as mqtt
from paho.mqtt import MQTTException
from ha_auto_discovery import AutoDiscoveryConfig

# Type aliases for clarity
ConfigValue = Union[int, float, bool, str, None]
BatteryData = Dict[str, Any]

# State container for shared application state
class AppState:
    """Container for globally shared runtime objects."""
    def __init__(self):
        self.mqtt_client: Optional[mqtt.Client] = None
        self.serial_instance: Optional[serial.Serial] = None
        self.battery_packs: List[Dict[str, Any]] = []

app_state = AppState()

logger: Optional[logging.Logger] = None

# --- Health/Watchdog state ---
# Timestamp of last successful BMS poll (seconds since epoch).
last_bms_update_ts: float = 0.0
# MQTT connection state as seen by callbacks.
mqtt_connected: bool = False


def _serial_is_open() -> bool:
    """Compatibility wrapper across pyserial versions."""
    s = app_state.serial_instance
    if not s:
        return False
    # Newer pyserial: property
    if hasattr(s, "is_open"):
        return bool(getattr(s, "is_open"))
    # Older pyserial: method
    if hasattr(s, "isOpen"):
        try:
            return bool(s.isOpen())
        except Exception:
            return False
    return False


def _mqtt_loop_running() -> bool:
    """Best-effort check whether Paho's network loop thread is alive."""
    c = app_state.mqtt_client
    if not c:
        return False
    t = getattr(c, "_thread", None)
    return bool(t and getattr(t, "is_alive", lambda: False)())


def _compute_max_age_seconds() -> int:
    """Derive an acceptable age for the last BMS poll from the polling cadence."""
    # The main loop sleeps 1s after each pack poll, plus an optional pause after a full cycle.
    packs = len(app_state.battery_packs) or int(getattr(Config, "NUMBER_OF_PACKS", 1) or 1)
    per_pack_delay = 1
    cycle_pause = int(getattr(Config, "MQTT_UPDATE_INTERVAL", 0) or 0)
    expected_cycle = packs * per_pack_delay + max(cycle_pause, 0)
    # Add a little slack for serial hiccups and startup.
    return max(15, int(expected_cycle * 3 + 5))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        now = time.time()
        max_age = _compute_max_age_seconds()

        healthy = (
            mqtt_connected
            and _mqtt_loop_running()
            and _serial_is_open()
            and (now - last_bms_update_ts) < max_age
        )

        if healthy:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"unhealthy")

    def log_message(self, format, *args):
        # Keep addon logs clean
        return


def _start_health_server() -> None:
    server = HTTPServer(("0.0.0.0", 8080), HealthHandler)
    server.serve_forever()


def graceful_exit(signum: Optional[int] = None, _frame: Optional[Any] = None) -> None:
    """Handle script exit to disconnect MQTT gracefully and cleanup."""

    try:
        # Close MQTT client if connected
        if app_state.mqtt_client and app_state.mqtt_client.is_connected():
            if logger:
                logger.info("Sending offline status to MQTT")
            app_state.mqtt_client.publish(f"{os.getenv('MQTT_TOPIC', 'seplos')}/availability", "offline", retain=True)
            for pack in app_state.battery_packs:
                app_state.mqtt_client.publish(_pack_availability_topic(pack["address"]), "offline", retain=False)
            if logger:
                logger.info("Disconnecting MQTT client")
            app_state.mqtt_client.disconnect()
            app_state.mqtt_client.loop_stop()

        # Close serial connection if open
        if _serial_is_open():
            if logger:
                logger.info("Closing serial connection")
            app_state.serial_instance.close()
    except Exception as e:
        if logger:
            logger.error("Error during graceful exit: %s", e)

    if signum is not None:
        sys.exit(0)


# Register signal handler for SIGTERM
signal.signal(signal.SIGTERM, graceful_exit)
signal.signal(signal.SIGINT, graceful_exit)


def get_env_value(var_name: str, default: Any = None, return_type: type = str) -> ConfigValue:
    """
    Get configuration value from environment variable with type casting.

    Args:
        var_name: Environment variable name
        default: Default value if not set
        return_type: Target type for casting (int, float, bool, str)

    Returns:
        Casted value or default
    """
    value = os.getenv(var_name, default)

    if value is None or value == "":
        return default

    try:
        if return_type == int:
            return int(value)
        elif return_type == float:
            return float(value)
        elif return_type == bool:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ['true', '1', 'yes', 'on']
        else:
            return str(value)
    except (ValueError, TypeError):
        return default


# Configuration from environment variables with defaults
class Config:
    """Configuration class holding all settings from environment variables."""

    # BMS Configuration
    MIN_CELL_VOLTAGE = get_env_value("MIN_CELL_VOLTAGE", 2.500, float)
    MAX_CELL_VOLTAGE = get_env_value("MAX_CELL_VOLTAGE", 3.650, float)
    NUMBER_OF_PACKS = get_env_value("NUMBER_OF_PACKS", 1, int)

    # Serial Configuration
    SERIAL_INTERFACE = get_env_value("SERIAL_INTERFACE", "/dev/ttyUSB0", str)

    # MQTT Configuration
    MQTT_HOST = get_env_value("MQTT_HOST", "192.168.1.100", str)
    MQTT_PORT = get_env_value("MQTT_PORT", 1883, int)
    MQTT_USERNAME = get_env_value("MQTT_USERNAME", "seplos-mqtt", str)
    MQTT_PASSWORD = get_env_value("MQTT_PASSWORD", "", str)
    MQTT_TOPIC = get_env_value("MQTT_TOPIC", "seplos", str)
    MQTT_UPDATE_INTERVAL = get_env_value("MQTT_UPDATE_INTERVAL", 30, int)

    # Home Assistant Discovery
    ENABLE_HA_DISCOVERY_CONFIG = get_env_value("ENABLE_HA_DISCOVERY_CONFIG", True, bool)
    HA_DISCOVERY_PREFIX = get_env_value("HA_DISCOVERY_PREFIX", "homeassistant", str)
    INVERT_HA_DIS_CHARGE_MEASUREMENTS = get_env_value("INVERT_HA_DIS_CHARGE_MEASUREMENTS", True, bool)

    # Logging
    LOGGING_LEVEL = get_env_value("LOGGING_LEVEL", "info", str).upper()


# Logging setup
logging.basicConfig(
    format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("SeplosBMS")

# Set log level based on configuration
log_levels = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}
logger.setLevel(log_levels.get(Config.LOGGING_LEVEL, logging.INFO))

# Log configuration on startup
logger.info("Starting Seplos BMS Data Fetcher")
logger.debug("Configuration loaded: %s", vars(Config))


def _pack_availability_topic(pack_no: int) -> str:
    return f"{Config.MQTT_TOPIC}/pack-{pack_no}/availability"


def _pack_heartbeat_topic(pack_no: int) -> str:
    return f"{Config.MQTT_TOPIC}/pack-{pack_no}/heartbeat"


def _publish_pack_availability(pack_state: Dict[str, Any], now: float) -> None:
    if not app_state.mqtt_client:
        return

    max_age = _compute_max_age_seconds()
    last_success = pack_state.get("last_success_ts", 0.0)
    is_online = last_success > 0 and (now - last_success) <= max_age
    desired = "online" if is_online else "offline"

    if pack_state.get("availability") != desired:
        topic = _pack_availability_topic(pack_state["address"])
        app_state.mqtt_client.publish(topic, desired, retain=False)
        pack_state["availability"] = desired


class Telemetry:
    """Holds numeric states for different sensors."""

    def __init__(self):
        # From pack
        self.voltage_cell: List[Optional[float]] = [None] * 15
        self.cell_temperature: List[Optional[float]] = [None] * 4
        self.ambient_temperature: Optional[float] = None
        self.components_temperature: Optional[float] = None
        self.dis_charge_current: Optional[float] = None
        self.total_pack_voltage: Optional[float] = None
        self.residual_capacity: Optional[float] = None
        self.battery_capacity: Optional[float] = None
        self.state_of_charge: Optional[float] = None
        self.rated_capacity: Optional[float] = None
        self.charging_cycles: Optional[int] = None
        self.state_of_health: Optional[float] = None
        self.port_voltage: Optional[float] = None

        # From user settings
        self.min_cell_voltage: Optional[float] = None
        self.max_cell_voltage: Optional[float] = None

        # Calculated
        self.average_cell_voltage: Optional[float] = None
        self.delta_cell_voltage: Optional[float] = None
        self.lowest_cell: Optional[int] = None
        self.lowest_cell_voltage: Optional[float] = None
        self.highest_cell: Optional[int] = None
        self.highest_cell_voltage: Optional[float] = None
        self.min_pack_voltage: Optional[float] = None
        self.max_pack_voltage: Optional[float] = None
        self.delta_cell_temperature: Optional[float] = None
        self.dis_charge_power: Optional[float] = None


class SeplosBatteryPack:
    """Handles all methods for fetching, validating and parsing BMS data."""

    FRAME_READ_RETRIES = 5
    FRAME_MIN_LENGTH = 81
    STATUS_MAP_24_BYTE_ALARM = {
        0: "OK",
        1: "Alarm (low)",
        2: "Alarm (high)"
    }
    STATUS_MAP_20_BIT_ALARM = {
        "on_off": ("ON", "OFF"),
        "fault_normal": ("Fault", "OK"),
        "warning_normal": ("Warning", "OK"),
        "protection_normal": ("Protection", "OK"),
    }

    def __init__(self, pack_address: int):
        self.pack_address = pack_address
        self.last_status: Optional[BatteryData] = None
        self.telemetry = Telemetry()

    @staticmethod
    def calculate_frame_checksum(frame: bytes) -> int:
        """Calculate frame checksum."""
        checksum = sum(frame) % 0xFFFF
        checksum ^= 0xFFFF
        checksum += 1
        return checksum

    @staticmethod
    def is_valid_hex_string(data: bytes) -> bool:
        """Check if given ASCII data is valid hex."""
        try:
            bytes.fromhex(data.decode("ascii"))
            logger.debug("Frame has hex only: OK")
            return True
        except (ValueError, UnicodeDecodeError):
            logger.debug("Frame includes non-hexadecimal characters: %s", data)
            return False

    @staticmethod
    def is_valid_length(data: bytes, expected_length: int) -> bool:
        """Check if given data matches expected length."""
        actual_length = len(data)
        if actual_length != expected_length:
            logger.debug(
                "Frame length mismatch - expected: %s, got: %s",
                expected_length,
                actual_length
            )
            return False
        logger.debug("Frame length OK: %s", expected_length)
        return True

    @staticmethod
    def int_from_1byte_hex_ascii(data: bytes, offset: int, signed: bool = False) -> int:
        """Return (signed) int value from 1 byte ASCII hex data."""
        return int.from_bytes(
            bytes.fromhex(data[offset:offset + 2].decode("ascii")),
            byteorder="big",
            signed=signed
        )

    @staticmethod
    def int_from_2byte_hex_ascii(data: bytes, offset: int, signed: bool = False) -> int:
        """Return (signed) int value from 2 byte ASCII hex data."""
        return int.from_bytes(
            bytes.fromhex(data[offset:offset + 4].decode("ascii")),
            byteorder="big",
            signed=signed
        )

    @staticmethod
    def status_from_24_byte_alarm(data: bytes, offset: int) -> str:
        """Return status string from 24 byte alarm data."""
        alarm_type = bytes.fromhex(data.decode("ascii"))[offset]
        return SeplosBatteryPack.STATUS_MAP_24_BYTE_ALARM.get(alarm_type, "Alarm (other)")

    @staticmethod
    def status_from_20_bit_alarm(
        data: bytes,
        offset: int,
        mode: str,
        first_bit: int,
        second_bit: Optional[int] = None
    ) -> str:
        """Return a status string based on 20-bit alarm data."""

        # Decode hex data into a byte value
        data_byte = bytes.fromhex(data.decode("ascii"))[offset]

        # helper
        def bit_set(bit: int) -> bool:
            return bool(data_byte & (1 << bit))

        # one bit mode
        if mode in SeplosBatteryPack.STATUS_MAP_20_BIT_ALARM:
            active, inactive = SeplosBatteryPack.STATUS_MAP_20_BIT_ALARM[mode]
            return active if bit_set(first_bit) else inactive

        # two bit mode
        if mode == "protection_alarm_normal":
            if bit_set(first_bit):
                return "Alarm"
            if second_bit is not None and bit_set(second_bit):
                return "Protection"
            return "OK"

        if mode == "lockout_protection_normal":
            if bit_set(first_bit):
                return "Protection"
            if second_bit is not None and bit_set(second_bit):
                return "Lockout"
            return "OK"

        return "unknown"

    def is_valid_frame(self, data: bytes) -> bool:
        """
        Check validity of frame: length, checksum and error flag.
        - Checksum must be valid
        - cid2 must be 00 (no error)
        """
        try:
            # Check frame checksum
            chksum = self.calculate_frame_checksum(data[1:-5])
            expected = self.int_from_2byte_hex_ascii(data, -5)
            if chksum != expected:
                logger.debug(
                    "Frame checksum mismatch - got: %s, expected: %s",
                    chksum,
                    expected
                )
                return False
            logger.debug("Frame checksum OK: %s", chksum)

            # Check frame cid2 flag
            cid2 = data[7:9]
            if cid2 != b"00":
                logger.debug(
                    "Frame error flag (cid2) set - expected b'00', got: %s",
                    cid2
                )
                return False
            logger.debug("Frame error flag OK: %s", cid2)

            return True

        except (UnicodeDecodeError, ValueError) as e:
            logger.debug("Frame validation error: %s", e)
            return False

    @staticmethod
    def get_info_length(info: bytes) -> int:
        """Calculate info length with checksum."""
        lenid = len(info)
        if lenid == 0:
            return 0

        lchksum = (lenid & 0xF) + ((lenid >> 4) & 0xF) + ((lenid >> 8) & 0xF)
        lchksum %= 15
        lchksum ^= 0xF
        lchksum += 1

        return (lchksum << 12) + lenid

    def encode_cmd(self, address: int, cid2: int, info: bytes = b"01") -> bytes:
        """Encode command for battery pack using its address."""
        cid1 = 0x46
        info_length = self.get_info_length(info)
        frame = f"{0x20:02X}{address:02X}{cid1:02X}{cid2:02X}{info_length:04X}".encode()
        frame += info
        checksum = self.calculate_frame_checksum(frame)
        return b"~" + frame + f"{checksum:04X}".encode() + b"\r"

    def get_lowest_cell(self) -> Dict[str, Any]:
        """Get lowest cell number and voltage."""
        valid_cells = [v for v in self.telemetry.voltage_cell if v is not None]
        if not valid_cells:
            return {"lowest_cell": 0, "lowest_cell_voltage": 0}

        lowest_voltage = min(valid_cells)
        lowest_cell = self.telemetry.voltage_cell.index(lowest_voltage)
        return {"lowest_cell": lowest_cell, "lowest_cell_voltage": lowest_voltage}

    def get_highest_cell(self) -> Dict[str, Any]:
        """Get highest cell number and voltage."""
        valid_cells = [v for v in self.telemetry.voltage_cell if v is not None]
        if not valid_cells:
            return {"highest_cell": 0, "highest_cell_voltage": 0}

        highest_voltage = max(valid_cells)
        highest_cell = self.telemetry.voltage_cell.index(highest_voltage)
        return {"highest_cell": highest_cell, "highest_cell_voltage": highest_voltage}

    def decode_telemetry_feedback_frame(self, data: bytes) -> Dict[str, Any]:
        """Decode battery pack telemetry feedback frame."""
        telemetry_feedback = {"normal": {}}
        feedback = telemetry_feedback["normal"]

        logger.debug("Data: %s", data)

        # Number of cells
        number_of_cells = self.int_from_1byte_hex_ascii(data, offset=4)
        logger.debug(
            "Number of cells %s",
            number_of_cells
        )

        # Static values from configs

        ## calculate min/max cell and pack voltages
        self.telemetry.min_cell_voltage = Config.MIN_CELL_VOLTAGE
        self.telemetry.max_cell_voltage = Config.MAX_CELL_VOLTAGE
        self.telemetry.min_pack_voltage = Config.MIN_CELL_VOLTAGE * number_of_cells
        self.telemetry.max_pack_voltage = Config.MAX_CELL_VOLTAGE * number_of_cells

        ### Add to telemetry_feedback
        feedback.update({
            "min_cell_voltage": self.telemetry.min_cell_voltage,
            "max_cell_voltage": self.telemetry.max_cell_voltage,
            "min_pack_voltage": self.telemetry.min_pack_voltage,
            "max_pack_voltage": self.telemetry.max_pack_voltage
        })

        # Dynamic values from the BMS

        # 00010F0CF80CF60CF80CF80CF90CF80CF70CF80CD80CF80CF80CF70CF80CF80CF7060B9B0B9A0B9B0B9A0BB40B9DFF3413701E560A27100308271002F003E813740000000000000000

        #         Pack Nr.: 0001
        #            Cells: 0F
        #     Voltage/Cell: 0CF8 0CF6 0CF8 0CF8 0CF9 0CF8 0CF7 0CF8 0CD8 0CF8 0CF8 0CF7 0CF8 0CF8 0CF7
        #     Tmp. sensors: 06
        #            Temps: 0B9B 0B9A 0B9B 0B9A 0BB4 0B9D 
        #          Current: FF34
        #     Pack Voltage: 1370
        #   Remaining Cap.: 1E56 
        #         Reserved: 0A
        # Battery Capacity: 2710
        #              SoC: 0308
        #   Rated Capacity: 2710
        #      Cycle count: 02F0
        #              SoH: 03E8
        #     Ports Votage: 1374
        #            Flags: 0000000000000000


        telemetry_fields = {
            'voltage_cell':             { 'offset': 6,   'scale': 1/1000, 'round': 3, 'amount': number_of_cells },
            'cell_temperature':         { 'offset': 68,  'scale': 1/10,   'round': 1,  'bias': -2731, 'amount': 4 },
            'ambient_temperature':      { 'offset': 84,  'scale': 1/10,   'round': 1,  'bias': -2731 },
            'components_temperature':   { 'offset': 88,  'scale': 1/10,   'round': 1,  'bias': -2731 },
            'dis_charge_current':       { 'offset': 92,  'scale': 1/100,  'round': 2, 'signed': True },
            'total_pack_voltage':       { 'offset': 96,  'scale': 1/100,  'round': 2 },
            'residual_capacity':        { 'offset': 100, 'scale': 1/100,  'round': 2 }, 
            'battery_capacity':         { 'offset': 106, 'scale': 1/100,  'round': 2 }, 
            'state_of_charge':          { 'offset': 110, 'scale': 1/10,   'round': 1 },  
            'rated_capacity':           { 'offset': 114, 'scale': 1/100,  'round': 2 }, 
            'charging_cycles':          { 'offset': 118, 'scale': 1,      'round': 1 },     
            'state_of_health':          { 'offset': 122, 'scale': 1/10,   'round': 1 },  
            'port_voltage':             { 'offset': 126, 'scale': 1/100,  'round': 2 } 
        }

        ## Fetch values for all telemetry fields
        for attr, cfg in telemetry_fields.items():
            offset = cfg["offset"]
            scale = cfg.get("scale", 1)
            rounding = cfg.get("round", None)
            bias = cfg.get("bias", 0)
            signed = cfg.get("signed", False)
            amount = cfg.get("amount", 1)

            #logger.debug("Decoding telemetry field: %s", attr)

            if amount > 1:
                for i in range(amount):
                    raw = self.int_from_2byte_hex_ascii(
                        data,
                        offset + i * 4,
                        signed=signed
                    )
                    value = (raw + bias) * scale

                    #logger.debug("Raw field: %s, value: %s", raw, value)

                    if rounding is not None:
                        value = round(value, rounding)
                    getattr(self.telemetry, attr)[i] = value

                    ### Add to telemetry_feedback
                    feedback[f"{attr}_{i + 1}"] = value
            else:
                raw = self.int_from_2byte_hex_ascii(
                    data,
                    offset,
                    signed=signed
                )
                value = (raw + bias) * scale

                #logger.debug("Raw field: %s, value: %s", raw, value)

                if rounding is not None:
                    value = round(value, rounding)
                setattr(self.telemetry, attr, value)

                ### Add to telemetry_feedback
                feedback[attr] = value

        # Calculated values

        # Get values from previous readings
        dis_charge_current  = self.telemetry.dis_charge_current
        total_pack_voltage  = self.telemetry.total_pack_voltage
        cell_voltages       = self.telemetry.voltage_cell
        cell_temps          = self.telemetry.cell_temperature

        ## Dis-/charge power
        dis_charge_power = round(dis_charge_current * total_pack_voltage, 2)
        self.telemetry.dis_charge_power = dis_charge_power

        ## Average cell voltage
        avg_voltage = round(sum(cell_voltages) / len(cell_voltages), 3)
        self.telemetry.average_cell_voltage = avg_voltage

        ## Highest/lowest cell and voltage
        lowest_idx, lowest_voltage = min(
            enumerate(cell_voltages), key=lambda x: x[1]
        )
        highest_idx, highest_voltage = max(
            enumerate(cell_voltages), key=lambda x: x[1]
        )

        self.telemetry.lowest_cell = lowest_idx
        self.telemetry.lowest_cell_voltage = lowest_voltage
        self.telemetry.highest_cell = highest_idx
        self.telemetry.highest_cell_voltage = highest_voltage

        ## Delta cell voltage
        delta_cell_voltage = round(highest_voltage - lowest_voltage, 3)
        self.telemetry.delta_cell_voltage = delta_cell_voltage

        # Delta cell temperature
        delta_cell_temperature = round(
            max(cell_temps) - min(cell_temps), 1
        )
        self.telemetry.delta_cell_temperature = delta_cell_temperature

        ### Add to telemetry_feedback
        feedback.update({
            "dis_charge_power": dis_charge_power,
            "average_cell_voltage": avg_voltage,
            "lowest_cell": lowest_idx + 1,      # 1-based for display
            "lowest_cell_voltage": lowest_voltage,
            "highest_cell": highest_idx + 1,    # 1-based for display
            "highest_cell_voltage": highest_voltage,
            "delta_cell_voltage": delta_cell_voltage,
            "delta_cell_temperature": delta_cell_temperature
        })

        return telemetry_feedback

    def _request_feedback_frame(
        self,
        cid2: int,
        expected_length: int,
        decoder: Callable[[bytes], Dict[str, Any]],
        frame_label: str
    ) -> Optional[Dict[str, Any]]:
        
        """Request a feedback frame with retry/validation."""
        
        if not app_state.serial_instance:
            logger.error("Serial instance not initialized")
            return None, False

        command = self.encode_cmd(address=self.pack_address, cid2=cid2)
        logger.debug("Pack%s:%s_command: %s", self.pack_address, frame_label, command)

        for attempt in range(self.FRAME_READ_RETRIES):
            app_state.serial_instance.write(command)
            raw_data = app_state.serial_instance.read_until(b'\r')

            if len(raw_data) < self.FRAME_MIN_LENGTH:
                logger.debug(
                    "Pack%s:%s attempt %s: insufficient length",
                    self.pack_address,
                    frame_label,
                    attempt + 1
                )
                continue

            pack_address_data = raw_data[3:-77]
            info_frame_data = raw_data[13:-5]

            if (
                self.is_valid_hex_string(pack_address_data) and
                self.int_from_1byte_hex_ascii(pack_address_data, 0) == self.pack_address and
                self.is_valid_length(info_frame_data, expected_length=expected_length) and
                self.is_valid_hex_string(info_frame_data) and
                self.is_valid_frame(raw_data)
            ):
                feedback = decoder(info_frame_data)
                feedback_dump = json.dumps(feedback, indent=2)
                logger.info("Pack%s:%s received", self.pack_address, frame_label)
                logger.debug(
                    "Pack%s:%s: %s",
                    self.pack_address,
                    frame_label,
                    feedback_dump
                )
                return feedback

            logger.debug(
                "Pack%s:%s attempt %s: validation failed",
                self.pack_address,
                frame_label,
                attempt + 1
            )

        logger.error(
            "Pack%s:Failed to read %s after %s retries",
            self.pack_address,
            frame_label.lower(),
            self.FRAME_READ_RETRIES
        )
        return None

    def read_serial_data(self) -> Tuple[Optional[BatteryData], bool]:
        """Read data for battery pack from serial interface."""
        logger.info("Pack%s:Requesting data...", self.pack_address)

        if not app_state.serial_instance:
            logger.error("Serial instance not initialized")
            return None

        battery_pack_data = {
            "telemetry": {},
        }

        try:
            # Flush serial buffers
            app_state.serial_instance.flushOutput()
            app_state.serial_instance.flushInput()

            # Request telemetry data
            telemetry_feedback = self._request_feedback_frame(
                cid2=0x42,
                expected_length=146,
                decoder=self.decode_telemetry_feedback_frame,
                frame_label="Telemetry"
            )
            if telemetry_feedback is None:
                return None, False
            battery_pack_data["telemetry"] = telemetry_feedback

            # Mandatory delay between each request or there will be corrupt data
            time.sleep(1)

            # Check if data has changed
            if self.last_status is None or self.last_status != battery_pack_data:
                self.last_status = battery_pack_data
                return battery_pack_data, True

            return None, True
        except Exception as e:
            logger.error("Pack%s:Error reading serial data: %s", self.pack_address, e)
            return None, False


def on_mqtt_connect(
    _client: mqtt.Client,
    _userdata: Any,
    _flags: Any,
    reason_code: int
) -> None:
    """Handle MQTT connection."""
    global mqtt_connected
    if reason_code == 0:
        mqtt_connected = True
        logger.info(
            "Connected to MQTT broker (%s:%s)",
            Config.MQTT_HOST,
            Config.MQTT_PORT
        )
    else:
        mqtt_connected = False
        logger.error("Failed to connect to MQTT broker: %s", reason_code)


def on_mqtt_disconnect(
    _client: mqtt.Client,
    _userdata: Any,
    _reason_code: int,
    _properties: Any = None,
) -> None:
    """Handle MQTT disconnect."""
    global mqtt_connected
    mqtt_connected = False


def initialize_mqtt() -> mqtt.Client:
    """Initialize and connect MQTT client."""
    client = mqtt.Client()
    client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD)
    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect
    client.will_set(f"{Config.MQTT_TOPIC}/availability", payload="offline", qos=2, retain=False)

    try:
        client.connect(Config.MQTT_HOST, Config.MQTT_PORT, keepalive=60)
        client.loop_start()
        return client
    except MQTTException as e:
        logger.error("MQTT connection failed: %s", e)
        sys.exit(1)


def initialize_serial() -> serial.Serial:
    """Initialize serial connection."""
    try:
        baudrate = 19200
        logger.info(
            "Initializing serial interface %s at %s baud",
            Config.SERIAL_INTERFACE,
            baudrate
        )
        return serial.Serial(
            port=Config.SERIAL_INTERFACE,
            baudrate=baudrate,
            timeout=0.5
        )
    except SerialException as e:
        logger.error("Serial initialization failed: %s", e)
        sys.exit(1)


def main():
    """Main application loop."""
    global last_bms_update_ts
    try:
        # Initialize MQTT
        app_state.mqtt_client = initialize_mqtt()

        # Initialize battery packs
        app_state.battery_packs.clear()
        
        _pack_address = 0

        for i in range(Config.NUMBER_OF_PACKS):
            if Config.NUMBER_OF_PACKS > 1:
                _pack_address = i + 1 # Multiple packs address starts with 1
            else:
                _pack_address = i # Single pack address is 0
            pack_instance = SeplosBatteryPack(pack_address=_pack_address)
            app_state.battery_packs.append({
                "pack_instance": pack_instance,
                "address": _pack_address,
                "last_success_ts": 0.0,
                "publish_counter": 0,
                "availability": "offline",
            })
        logger.info("Initialized %s battery pack(s)", Config.NUMBER_OF_PACKS)

        for pack in app_state.battery_packs:
            app_state.mqtt_client.publish(_pack_availability_topic(pack["address"]), "offline", retain=False)

        # Initial grace: consider startup healthy until the first successful poll updates the timestamp.
        last_bms_update_ts = time.time()

        # Start minimal HTTP health endpoint for HA Supervisor watchdog
        health_thread = threading.Thread(target=_start_health_server, daemon=True)
        health_thread.start()
        logger.info("Health endpoint started on http://0.0.0.0:8080/health")

        # Send Home Assistant Auto-Discovery configurations on startup
        if Config.ENABLE_HA_DISCOVERY_CONFIG:
            logger.info("Sending Home Assistant Auto-Discovery configurations")
            auto_discovery = AutoDiscoveryConfig(
                mqtt_topic=Config.MQTT_TOPIC,
                discovery_prefix=Config.HA_DISCOVERY_PREFIX,
                invert_ha_dis_charge_measurements=Config.INVERT_HA_DIS_CHARGE_MEASUREMENTS,
                mqtt_client=app_state.mqtt_client
            )
            for pack in app_state.battery_packs:
                auto_discovery.create_autodiscovery_sensors(pack_no=pack['address'])
            logger.info("Auto-Discovery configurations sent")

        # Main loop
        pack_index = 0
        while True:
            try:

                # Initialize Serial
                app_state.serial_instance = initialize_serial()

                current_pack = app_state.battery_packs[pack_index]
                pack_instance = current_pack["pack_instance"]
                pack_address = current_pack["address"]

                # Fetch battery pack data
                pack_data, poll_success = pack_instance.read_serial_data()
                now = time.time()

                if poll_success:
                    last_bms_update_ts = now
                    current_pack["last_success_ts"] = now
                    current_pack["publish_counter"] += 1
                    heartbeat_payload = {
                        "last_publish": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "publish_counter": current_pack["publish_counter"],
                    }
                    app_state.mqtt_client.publish(
                        _pack_heartbeat_topic(pack_address),
                        json.dumps(heartbeat_payload),
                        retain=False,
                    )
                    app_state.mqtt_client.publish(
                        _pack_availability_topic(pack_address),
                        "online",
                        retain=False,
                    )
                    current_pack["availability"] = "online"

                if pack_data:
                    # Publish updated data to MQTT
                    logger.info("Pack%s:Publishing updated data to MQTT", pack_address)
                    topic = f"{Config.MQTT_TOPIC}/pack-{pack_address}/sensors"
                    payload = {**pack_data}
                    app_state.mqtt_client.publish(topic, json.dumps(payload, indent=2))
                elif poll_success:
                    logger.info("Pack%s:No changes detected", pack_address)

                for pack_state in app_state.battery_packs:
                    _publish_pack_availability(pack_state, now)

                # Publish availability
                app_state.mqtt_client.publish(f"{Config.MQTT_TOPIC}/availability", "online", retain=False)

                # Mandatory delay between each request or there will be corrupt data
                time.sleep(1)

                app_state.serial_instance.close()

                # Move to next pack
                pack_index += 1
                if pack_index >= len(app_state.battery_packs):
                    pack_index = 0
                    if Config.MQTT_UPDATE_INTERVAL > 0:
                        logger.info(
                            "Waiting %s seconds before next cycle",
                            Config.MQTT_UPDATE_INTERVAL
                        )
                        time.sleep(Config.MQTT_UPDATE_INTERVAL)

            except Exception as e:
                logger.error("Error in main loop: %s", e)
                time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Shutdown requested via keyboard interrupt")
    except Exception as e:
        logger.error("Fatal error: %s", e)
    finally:
        graceful_exit()


if __name__ == "__main__":
    main()
