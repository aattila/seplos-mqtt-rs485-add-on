"""
Handle creation and publishing of auto discovery configs for Home Assistant.
"""
import json
import logging
import copy
from typing import Optional, Dict, Any, List

logger = logging.getLogger("SeplosBMS.Discovery")

# Base sensor template
BASE_SENSOR = {
    "name": "",
    "uniq_id": "",  # unique_id
    "obj_id": "",  # object_id
    "stat_t": "",  # state_topic
    "val_tpl": "",  # value_template
    "avty": [],  # availability
    "dev": {}  # device
}

DEVICE_BASE_CONFIG = {
    "hw": "1101-ZH43",  # hw_version
    "sw": "2.7",  # sw_version
    "mdl": "BMS V2",  # model
    "mf": "Seplos"  # manufacturer
}

# Telemetry sensor templates
TELEMETRY_SENSOR_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "Min Cell Voltage",
        "value_template_key": "min_cell_voltage",
        "device_class": "voltage",
        "unit_of_measurement": "V",
        "suggested_display_precision": 3,
        "icon": "mdi:cog"
    },
    {
        "name": "Max Cell Voltage",
        "value_template_key": "max_cell_voltage",
        "device_class": "voltage",
        "unit_of_measurement": "V",
        "suggested_display_precision": 3,
        "icon": "mdi:cog"
    },
    {
        "name": "Min Pack Voltage",
        "value_template_key": "min_pack_voltage",
        "device_class": "voltage",
        "unit_of_measurement": "V",
        "suggested_display_precision": 2,
        "icon": "mdi:cog"
    },
    {
        "name": "Max Pack Voltage",
        "value_template_key": "max_pack_voltage",
        "device_class": "voltage",
        "unit_of_measurement": "V",
        "suggested_display_precision": 2,
        "icon": "mdi:cog"
    },
    {
        "name": "Average Cell Voltage",
        "value_template_key": "average_cell_voltage",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit_of_measurement": "V",
        "suggested_display_precision": 3,
        "icon": "mdi:chart-line"
    },
    {
        "name": "Lowest Cell",
        "value_template_key": "lowest_cell",
        "icon": "mdi:numeric"
    },
    {
        "name": "Lowest Cell Voltage",
        "value_template_key": "lowest_cell_voltage",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit_of_measurement": "V",
        "suggested_display_precision": 3,
        "icon": "mdi:arrow-down-thin"
    },
    {
        "name": "Highest Cell",
        "value_template_key": "highest_cell",
        "icon": "mdi:numeric"
    },
    {
        "name": "Highest Cell Voltage",
        "value_template_key": "highest_cell_voltage",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit_of_measurement": "V",
        "suggested_display_precision": 3,
        "icon": "mdi:arrow-up-thin"
    },
    {
        "name": "Delta Cell Voltage",
        "value_template_key": "delta_cell_voltage",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit_of_measurement": "V",
        "suggested_display_precision": 3,
        "icon": "mdi:delta"
    },
    {
        "name": "Delta Cell Temperature",
        "value_template_key": "delta_cell_temperature",
        "device_class": "temperature_delta",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "suggested_display_precision": 1,
        "icon": "mdi:delta"
    },
    {
        "name": "Ambient Temperature",
        "value_template_key": "ambient_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "suggested_display_precision": 1,
        "icon": "mdi:thermometer"
    },
    {
        "name": "Components Temperature",
        "value_template_key": "components_temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "suggested_display_precision": 1,
        "icon": "mdi:thermometer"
    },
    {
        "name": "Dis-/Charge Current",
        "value_template_key": "dis_charge_current",
        "invert_value": True,
        "device_class": "current",
        "state_class": "measurement",
        "unit_of_measurement": "A",
        "suggested_display_precision": 2,
        "icon": "mdi:current-dc"
    },
    {
        "name": "Dis-/Charge Power",
        "value_template_key": "dis_charge_power",
        "invert_value": True,
        "device_class": "power",
        "state_class": "measurement",
        "unit_of_measurement": "W",
        "suggested_display_precision": 2,
        "icon": "mdi:flash"
    },
    {
        "name": "Total Pack Voltage",
        "value_template_key": "total_pack_voltage",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit_of_measurement": "V",
        "suggested_display_precision": 2,
        "icon": "mdi:server"
    },
    {
        "name": "Rated Capacity",
        "value_template_key": "rated_capacity",
        "unit_of_measurement": "Ah",
        "suggested_display_precision": 2,
        "icon": "mdi:battery"
    },
    {
        "name": "Battery Capacity",
        "value_template_key": "battery_capacity",
        "unit_of_measurement": "Ah",
        "state_class": "measurement",
        "suggested_display_precision": 2,
        "icon": "mdi:battery"
    },
    {
        "name": "Residual Capacity",
        "value_template_key": "residual_capacity",
        "state_class": "measurement",
        "unit_of_measurement": "Ah",
        "suggested_display_precision": 2,
        "icon": "mdi:battery-50"
    },
    {
        "name": "State of Charge",
        "value_template_key": "state_of_charge",
        "device_class": "battery",
        "state_class": "measurement",
        "unit_of_measurement": "%",
        "suggested_display_precision": 1,
        "icon": "mdi:battery"
    },
    {
        "name": "Charging Cycles",
        "value_template_key": "charging_cycles",
        "unit_of_measurement": "cycles",
        "state_class": "total_increasing",
        "icon": "mdi:counter"
    },
    {
        "name": "State of Health",
        "value_template_key": "state_of_health",
        "state_class": "measurement",
        "unit_of_measurement": "%",
        "suggested_display_precision": 1,
        "icon": "mdi:battery-heart"
    },
    {
        "name": "Port Voltage",
        "value_template_key": "port_voltage",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit_of_measurement": "V",
        "suggested_display_precision": 2,
        "icon": "mdi:flash-triangle"
    }
]



class AutoDiscoveryConfig:
    """Handle Home Assistant auto-discovery configuration creation and publishing."""

    def __init__(self, mqtt_topic: str, discovery_prefix: str, invert_ha_dis_charge_measurements: bool, mqtt_client) -> None:
        """
        Initialize AutoDiscoveryConfig.

        Args:
            mqtt_topic: MQTT topic where sensor data gets published
            discovery_prefix: Discovery prefix for Home Assistant (defaults to 'homeassistant')
            invert_ha_dis_charge_measurements: Inverts dis-/charge values for power and current
            mqtt_client: MQTT client instance for publishing
        """
        self.mqtt_topic = mqtt_topic
        self.discovery_prefix = discovery_prefix
        self.invert_ha_dis_charge_measurements = invert_ha_dis_charge_measurements
        self.mqtt_client = mqtt_client
        self._device_info_published = set()

    # -------------------------------------------------------------------------
    # Interne Hilfsfunktionen zur Vereinheitlichung
    # -------------------------------------------------------------------------

    def _add_device_info(self, entity: Dict[str, Any], pack_no: int) -> None:
        """Setze passende device-Infos für das gegebene Pack."""
        if pack_no not in self._device_info_published:
            entity["dev"] = {**DEVICE_BASE_CONFIG}
            entity["dev"]["name"] = f"Seplos BMS Pack-{pack_no} ({'Master' if pack_no == 0 else 'Slave'})"
            entity["dev"]["ids"] = f"seplos_bms_pack_{pack_no}"
            if pack_no > 0:
                entity["dev"]["via_device"] = "seplos_bms_pack_0"
            self._device_info_published.add(pack_no)
        else:
            entity["dev"] = {"ids": f"seplos_bms_pack_{pack_no}"}
            if pack_no > 0:
                entity["dev"]["via_device"] = "seplos_bms_pack_0"

    def _build_availability(self, pack_no: int) -> List[Dict[str, str]]:
        return [
            {"t": f"{self.mqtt_topic}/availability"},
            {"t": f"{self.mqtt_topic}/pack-{pack_no}/availability"},
        ]

    def _build_base_entity(
        self,
        pack_no: int,
        name: str,
        value_template: str,
        uniq_obj_id: str,
        state_topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Erzeuge Grundstruktur eines Sensors/Binary Sensors basierend auf BASE_SENSOR."""
        entity = copy.deepcopy(BASE_SENSOR)

        # Device-Infos
        self._add_device_info(entity, pack_no)

        # Required fields
        entity["name"] = name
        entity["avty"] = self._build_availability(pack_no)
        entity["avty_mode"] = "all"
        entity["stat_t"] = state_topic or f"{self.mqtt_topic}/pack-{pack_no}/sensors"
        entity["val_tpl"] = value_template
        entity["uniq_id"] = uniq_obj_id
        entity["obj_id"] = uniq_obj_id

        return entity

    def _apply_optional_fields(self, entity: Dict[str, Any], optional_fields: Dict[str, Any]) -> None:
        """Füge optionale Felder hinzu, wenn sie nicht None sind."""
        for key, value in optional_fields.items():
            if value is not None:
                entity[key] = value

    def _publish_config(
        self,
        entity_type: str,
        pack_no: int,
        name: str,
        value_template_key: str,
        config: Dict[str, Any],
    ) -> None:
        """Generische Publish-Funktion für Sensoren und Binary-Sensoren."""
        discovery_topic = f"{self.discovery_prefix}/{entity_type}/seplos-mqtt-pack-{pack_no}/{value_template_key}/config"

        try:
            self.mqtt_client.publish(
                discovery_topic,
                json.dumps(config),
                retain=True,
                qos=1
            )
            logger.debug(
                "Published discovery config for pack %s, %s: %s",
                pack_no,
                entity_type,
                name,
            )
        except Exception as e:
            logger.error("Failed to publish discovery config: %s", e)

    # -------------------------------------------------------------------------
    # Build-Funktionen
    # -------------------------------------------------------------------------

    def _build_binary_sensor_config(
        self,
        pack_no: int,
        name: str,
        value_template_group: str,
        value_template_key: str,
        icon: Optional[str] = None,
        entity_category: Optional[str] = None,
        device_class: Optional[str] = None,
        payload_on: Optional[str] = None,
        payload_off: Optional[str] = None,
        options: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build binary sensor configuration dictionary.
        """
        value_template = f"{{{{ value_json.{value_template_group}.binary.{value_template_key} }}}}"
        binary_sensor = self._build_base_entity(
            pack_no=pack_no,
            name=name,
            value_template=value_template,
            uniq_obj_id = f"seplos_bms_pack_{pack_no}_{value_template_key}",
        )

        optional_fields = {
            "ic": icon,
            "ent_cat": entity_category,
            "dev_cla": device_class,
            "pl_on": payload_on,
            "pl_off": payload_off,
            "ops": options
        }
        self._apply_optional_fields(binary_sensor, optional_fields)

        return binary_sensor

    def _build_sensor_config(
        self,
        pack_no: int,
        name: str,
        value_template_group: str,
        value_template_key: str,
        invert_value: Optional[bool] = False,
        unit_of_measurement: Optional[str] = None,
        suggested_display_precision: Optional[int] = None,
        icon: Optional[str] = None,
        device_class: Optional[str] = None,
        state_class: Optional[str] = None,
        entity_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build sensor configuration dictionary.
        """

        value_template_expr = f"value_json.{value_template_group}.normal.{value_template_key}"

        sensor = self._build_base_entity(
            pack_no=pack_no,
            name=name,
            value_template=f"{{{{ ({value_template_expr} | float) * -1 }}}}" if invert_value and self.invert_ha_dis_charge_measurements else f"{{{{ {value_template_expr} }}}}",
            uniq_obj_id=f"seplos_bms_pack_{pack_no}_{value_template_key}",
        )

        optional_fields = {
            "stat_cla": state_class,
            "unit_of_meas": unit_of_measurement,
            "sug_dsp_prc": suggested_display_precision,
            "ic": icon,
            "ent_cat": entity_category,
            "dev_cla": device_class
        }
        self._apply_optional_fields(sensor, optional_fields)

        return sensor

    # -------------------------------------------------------------------------
    # Publish-Funktionen (API unverändert)
    # -------------------------------------------------------------------------

    def _publish_binary_sensor_config(
        self,
        pack_no: int,
        binary_sensor_name: str,
        value_template_key: str,
        binary_sensor_config: Dict[str, Any]
    ) -> None:
        """
        Publish binary sensor configuration to MQTT.
        """
        self._publish_config(
            entity_type="binary_sensor",
            pack_no=pack_no,
            name=binary_sensor_name,
            value_template_key=value_template_key,
            config=binary_sensor_config,
        )

    def _publish_sensor_config(
        self,
        pack_no: int,
        sensor_name: str,
        value_template_key: str,
        sensor_config: Dict[str, Any]
    ) -> None:
        """
        Publish sensor configuration to MQTT.
        """
        self._publish_config(
            entity_type="sensor",
            pack_no=pack_no,
            name=sensor_name,
            value_template_key=value_template_key,
            config=sensor_config,
        )

    # -------------------------------------------------------------------------
    # Öffentliche Erzeugungs-Funktionen
    # -------------------------------------------------------------------------

    def create_binary_sensor_config(
        self,
        pack_no: int,
        name: str,
        value_template_group: str,
        value_template_key: str,
        icon: Optional[str] = None,
        device_class: Optional[str] = None,
        entity_category: Optional[str] = None,
        payload_on: Optional[str] = None,
        payload_off: Optional[str] = None,
        options: Optional[List[str]] = None
    ) -> None:
        """
        Create and publish unique binary sensor configuration.
        """

        logger.debug(
            "Creating auto-discovery binary sensors for pack %s",
            pack_no,
        )

        binary_sensor_config = self._build_binary_sensor_config(
            pack_no=pack_no,
            value_template_group=value_template_group,
            name=name,
            value_template_key=value_template_key,
            icon=icon,
            device_class=device_class,
            entity_category=entity_category,
            payload_on=payload_on,
            payload_off=payload_off,
            options=options
        )

        self._publish_binary_sensor_config(pack_no, name, value_template_key, binary_sensor_config)

        logger.debug(
            "Auto-discovery binary sensors published for pack %s",
            pack_no,
        )

    def create_sensor_config(
        self,
        pack_no: int,
        value_template_group: str,
        name: str,
        value_template_key: str,
        invert_value: Optional[bool] = False,
        unit_of_measurement: Optional[str] = None,
        suggested_display_precision: Optional[int] = None,
        icon: Optional[str] = None,
        device_class: Optional[str] = None,
        state_class: Optional[str] = None,
        entity_category: Optional[str] = None
    ) -> None:
        """
        Create and publish unique sensor configuration.
        """

        logger.debug(
            "Creating auto-discovery sensors for pack %s",
            pack_no,
        )


        sensor_config = self._build_sensor_config(
            pack_no=pack_no,
            value_template_group=value_template_group,
            name=name,
            value_template_key=value_template_key,
            invert_value=invert_value,
            unit_of_measurement=unit_of_measurement,
            suggested_display_precision=suggested_display_precision,
            icon=icon,
            device_class=device_class,
            state_class=state_class,
            entity_category=entity_category
        )

        self._publish_sensor_config(pack_no, name, value_template_key, sensor_config)

        logger.debug(
            "Auto-discovery sensors published for pack %s",
            pack_no,
        )

    def create_heartbeat_sensor_config(self, pack_no: int) -> None:
        """Create and publish a heartbeat sensor for the pack."""
        name = "Last Publish"
        value_template_key = "last_publish"
        state_topic = f"{self.mqtt_topic}/pack-{pack_no}/heartbeat"
        value_template = "{{ value_json.last_publish }}"

        sensor = self._build_base_entity(
            pack_no=pack_no,
            name=name,
            value_template=value_template,
            uniq_obj_id=f"seplos_bms_pack_{pack_no}_{value_template_key}",
            state_topic=state_topic,
        )

        self._apply_optional_fields(
            sensor,
            {
                "ic": "mdi:update",
                "ent_cat": "diagnostic",
            },
        )

        self._publish_sensor_config(pack_no, name, value_template_key, sensor)

    def create_similar_binary_sensor_config(
        self,
        num_sensors: int,
        pack_no: int,
        value_template_group: str,
        base_value_template_key: str,
        base_name: str,
        entity_category: Optional[str] = None,
        device_class: Optional[str] = None,
        icon: Optional[str] = None,
        payload_on: Optional[str] = None,
        payload_off: Optional[str] = None,
        options: Optional[List[str]] = None
    ) -> None:
        """
        Create multiple similar binary sensor configurations.
        """
        for i in range(1, num_sensors + 1):
            name = f"{base_name} {i}"
            value_template_key = f"{base_value_template_key}_{i}"

            self.create_binary_sensor_config(
                pack_no=pack_no,
                name=name,
                value_template_group=value_template_group,
                value_template_key=value_template_key,
                entity_category=entity_category,
                device_class=device_class,
                icon=icon,
                payload_on=payload_on,
                payload_off=payload_off,
                options=options
            )

    def create_similar_sensor_config(
        self,
        num_sensors: int,
        pack_no: int,
        value_template_group: str,
        base_value_template_key: str,
        base_name: str,
        entity_category: Optional[str] = None,
        device_class: Optional[str] = None,
        state_class: Optional[str] = None,
        unit_of_measurement: Optional[str] = None,
        suggested_display_precision: Optional[int] = None,
        icon: Optional[str] = None
    ) -> None:
        """
        Create multiple similar sensor configurations.
        """
        for i in range(1, num_sensors + 1):
            name = f"{base_name} {i}"
            value_template_key = f"{base_value_template_key}_{i}"

            self.create_sensor_config(
                pack_no=pack_no,
                name=name,
                value_template_group=value_template_group,
                value_template_key=value_template_key,
                entity_category=entity_category,
                device_class=device_class,
                state_class=state_class,
                unit_of_measurement=unit_of_measurement,
                suggested_display_precision=suggested_display_precision,
                icon=icon
            )

    def create_autodiscovery_sensors(self, pack_no: int) -> None:
        """
        Create all Home Assistant auto-discovery sensors for a pack.

        Args:
            pack_no: Pack number to create sensors for
        """
        # Clear device info flag for this pack to ensure it's included in first sensor
        self._device_info_published.discard(pack_no)

        ## Telemetry sensors

        # Create cell voltage sensors
        self.create_similar_sensor_config(
            num_sensors=15,
            pack_no=pack_no,
            value_template_group="telemetry",
            base_value_template_key="voltage_cell",
            base_name="Voltage Cell",
            device_class="voltage",
            state_class="measurement",
            unit_of_measurement="V",
            suggested_display_precision=3,
            icon="mdi:battery-outline"
        )

        # Create cell temperature sensors
        self.create_similar_sensor_config(
            num_sensors=4,
            pack_no=pack_no,
            value_template_group="telemetry",
            base_value_template_key="cell_temperature",
            base_name="Cell Temperature",
            device_class="temperature",
            state_class="measurement",
            unit_of_measurement="°C",
            suggested_display_precision=1,
            icon="mdi:thermometer"
        )

        # Create telemetry sensors
        for config in TELEMETRY_SENSOR_TEMPLATES:
            self.create_sensor_config(
                pack_no=pack_no,
                value_template_group="telemetry",
                **config
            )

        # Create heartbeat sensor
        self.create_heartbeat_sensor_config(pack_no=pack_no)
