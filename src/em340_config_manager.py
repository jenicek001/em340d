#!/usr/bin/env python
"""
EM340 MQTT Configuration Module
Listens to MQTT configuration topics and applies settings to the EM340 device
"""

import json
import os
import time
import paho.mqtt.client as mqtt
from logger import log
from typing import Dict, Any, Optional, Union

def write_enabled_from_env() -> bool:
    """em340d's own switch (its environment, never MQTT): writes into the meter are off unless CONFIG_WRITE_ENABLED
    is true (#17)."""
    return os.getenv('CONFIG_WRITE_ENABLED', 'false').strip().lower() in ('1', 'true', 'yes', 'on')


class EM340ConfigManager:
    """Manages EM340 configuration via MQTT commands"""
    
    # The EM340's configuration registers (docs/EM330_EM340_ET330_ET340_CP.pdf, CP v2 rev 17, tables 2.9-1..2.9-6;
    # #17). The EM340 is direct-connected (input AV2): it has no CT or VT ratio. Writing goes into the meter itself.
    # critical: changes what the billing meter measures or locks the meter - the payload must repeat the serial number.
    CONFIG_REGISTERS = {
        'password': {
            'address': 0x1000, 'type': 'UINT16', 'min_value': 0, 'max_value': 9999,
            'description': 'Device password', 'writable': True, 'critical': True
        },
        'measuring_system': {
            'address': 0x1002, 'type': 'UINT16', 'min_value': 0, 'max_value': 2,
            'description': 'Measuring system configuration',
            'values': {0: '3-phase 4-wire with neutral', 1: '3-phase 3-wire without neutral', 2: '2-phase 3-wire'},
            'writable': True, 'critical': True
        },
        'display_mode': {
            'address': 0x1100, 'type': 'UINT16', 'min_value': 0, 'max_value': 1,
            'description': 'Display mode', 'values': {0: 'Full', 1: 'Easy'}, 'writable': True
        },
        'tariff_enabling': {
            'address': 0x1101, 'type': 'UINT16', 'min_value': 0, 'max_value': 1,
            'description': 'Tariff management enabling', 'values': {0: 'OFF', 1: 'ON'}, 'writable': True
        },
        'home_page_selection': {
            'address': 0x1102, 'type': 'UINT16', 'min_value': 0, 'max_value': 19,
            'description': 'Home page selection (cannot be changed on MID models PFA/PFB)', 'writable': True
        },
        'measurement_mode': {
            'address': 0x1103, 'type': 'UINT16', 'min_value': 0, 'max_value': 1,
            'description': 'Measurement mode selection',
            'values': {0: 'Easy connection mode (A)', 1: 'Bidirectional mode (B)'},
            'writable': True, 'critical': True
        },
        'wrong_connection_help': {
            'address': 0x1104, 'type': 'UINT16', 'min_value': 0, 'max_value': 1,
            'description': 'Wrong connection (installing help) enabling', 'values': {0: 'ON', 1: 'OFF'}, 'writable': True
        },
        'tariff_mode': {
            'address': 0x1200, 'type': 'UINT16', 'min_value': 0, 'max_value': 1,
            'description': 'Tariff mode selection', 'values': {0: 'via digital inputs', 1: 'via serial communication'},
            'writable': True
        },
        'tariff_number': {
            'address': 0x1201, 'type': 'UINT16', 'min_value': 1, 'max_value': 2,
            'description': 'Tariff number selection via serial communication', 'writable': True
        },
    }

    def __init__(self, mqtt_config: Dict[str, Any], bus, modbus_address: int):
        """Initialize the configuration manager. Every Modbus request goes through `bus`, the ModbusBus
        the poll uses (#12): a command arriving on the MQTT thread during a poll waits its turn instead of
        interleaving on the RS-485 bus (#8)."""
        self.mqtt_broker = mqtt_config.get('broker', 'localhost')
        self.mqtt_port = int(mqtt_config.get('port', 1883))
        self.bus = bus
        self.modbus_address = modbus_address
        
        # Initialize MQTT client for configuration
        self.config_mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.config_mqtt_client.username_pw_set(mqtt_config.get('username', ''), mqtt_config.get('password', ''))
        self.config_mqtt_client.on_connect = self.on_config_mqtt_connect
        self.config_mqtt_client.on_message = self.on_config_mqtt_message
        self.config_mqtt_client.on_disconnect = self.on_config_mqtt_disconnect
        
        # Configuration topic structure
        self.base_topic = mqtt_config.get('topic', 'em340')
        self.device_id = mqtt_config.get('device_id', 'unknown')
        self.config_topic_base = f"{self.base_topic}/{self.device_id}/config"
        self.write_enabled = bool(mqtt_config.get('write_enabled', False))
        log.info(f"Configuration writes into the meter: {'ENABLED' if self.write_enabled else 'disabled'}")
        
        log.info(f"EM340 Config Manager initialized for device {self.device_id}")
        log.info(f"Configuration topics base: {self.config_topic_base}")

    def start_config_service(self):
        """Start the MQTT configuration service"""
        try:
            self.config_mqtt_client.loop_start()
            self.config_mqtt_client.connect(self.mqtt_broker, self.mqtt_port)
            log.info("EM340 configuration service started")
            return True
        except Exception as e:
            log.error(f"Failed to start configuration service: {e}")
            return False

    def stop_config_service(self):
        """Stop the MQTT configuration service"""
        try:
            self.config_mqtt_client.loop_stop()
            self.config_mqtt_client.disconnect()
            log.info("EM340 configuration service stopped")
        except Exception as e:
            log.error(f"Error stopping configuration service: {e}")

    def on_config_mqtt_connect(self, client, userdata, flags, reason_code, properties=None):
        """Handle MQTT connection for configuration"""
        if reason_code == 0:
            log.info('Connected to MQTT broker for configuration')
            
            # Subscribe to configuration topics
            config_topics = [
                f"{self.config_topic_base}/+/set",           # Individual parameter set
                f"{self.config_topic_base}/+/get",           # Individual parameter get
                f"{self.config_topic_base}/batch/set",       # Batch configuration
                f"{self.config_topic_base}/reset",           # answered with an error: factory reset removed (#17)
                f"{self.config_topic_base}/backup",          # Backup current config
                f"{self.config_topic_base}/restore"          # Restore from backup
            ]
            
            for topic in config_topics:
                client.subscribe(topic)
                log.info(f"Subscribed to configuration topic: {topic}")
                
            # Publish available configuration parameters
            self.publish_available_parameters()
            
        else:
            log.error(f'Failed to connect to MQTT broker for configuration, return code {reason_code}')

    def on_config_mqtt_disconnect(self, client, userdata, flags, reason_code, properties=None):
        """Handle MQTT disconnect for configuration"""
        if reason_code != 0:
            log.warning('Unexpected MQTT disconnection from configuration service')
        else:
            log.info('MQTT configuration client disconnected')

    def on_config_mqtt_message(self, client, userdata, message):
        """Handle incoming configuration MQTT messages"""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')
            
            log.info(f"Received configuration message: {topic} = {payload}")
            
            # Parse topic structure
            sub = topic.replace(f"{self.config_topic_base}/", "")
            if sub == "batch/set":
                self.handle_batch_set(payload)
            elif sub == "backup":
                self.handle_backup()
            elif sub == "restore":
                self.handle_restore(payload)
            elif sub == "reset":
                # Factory reset removed (#17): it wrote measurement mode A, and so stopped the export counters
                log.error("config/reset is not supported (#17)")
                self.publish_error("config/reset is not supported (#17)")
            else:
                topic_parts = sub.split("/")
                if len(topic_parts) == 2:
                    parameter, action = topic_parts
                    if action == "set":
                        self.handle_parameter_set(parameter, payload)
                    elif action == "get":
                        self.handle_parameter_get(parameter)

        except Exception as e:
            log.error(f"Error processing configuration message: {e}")
            self.publish_error(f"Error processing message: {str(e)}")

    def handle_parameter_set(self, parameter: str, payload: str, serial: Optional[str] = None) -> str:
        """Write one parameter into the meter (Modbus, through the bus) and read it back.

        payload: a bare value ("1", "Easy") or JSON {"value": …, "serial": "…"}. A critical parameter is written only
        when the payload - or a batch/restore that carries it (`serial`) - repeats the meter's serial number. Writes
        are off unless em340d's environment enables them (CONFIG_WRITE_ENABLED). Returns the published status, which
        batch and restore report per parameter."""
        try:
            if parameter not in self.CONFIG_REGISTERS:
                raise ValueError(f"Unknown parameter: {parameter}")
            register_info = self.CONFIG_REGISTERS[parameter]
            if not register_info.get('writable', False):
                raise ValueError(f"Parameter {parameter} is read-only")
            if not self.write_enabled:
                raise ValueError("writes disabled (CONFIG_WRITE_ENABLED is not set in em340d's environment)")

            raw = payload.strip() if isinstance(payload, str) else payload
            if isinstance(raw, str) and raw.startswith('{'):
                data = json.loads(raw)
                raw = data.get('value')
                serial = data.get('serial', serial)
            if register_info.get('critical') and str(serial or '').strip() != str(self.device_id):
                raise ValueError(f"serial number confirmation required: {parameter} changes what the meter measures; "
                                 f"send {{\"value\": …, \"serial\": \"<the meter's serial number>\"}}")

            # Parse and validate value
            try:
                value = int(raw)
            except (TypeError, ValueError):
                reverse_values = {v: k for k, v in (register_info.get('values') or {}).items()}
                if raw in reverse_values:
                    value = reverse_values[raw]
                else:
                    raise ValueError(f"Invalid value '{raw}' for parameter {parameter}")
            if register_info.get('min_value') is not None and value < register_info['min_value']:
                raise ValueError(f"Value {value} below minimum {register_info['min_value']}")
            if register_info.get('max_value') is not None and value > register_info['max_value']:
                raise ValueError(f"Value {value} above maximum {register_info['max_value']}")

            # Write into the meter's register
            address = register_info['address']
            log.warning(f"Writing {parameter} = {value} to EM340 register 0x{address:04X}")
            self.bus.write_register(self.modbus_address, address, value)
            time.sleep(0.1)  # Let the meter apply the setting before the read-back

            # Verify write by reading back
            read_value = self.bus.read_register(self.modbus_address, address)
            if read_value == value:
                log.warning(f"Set {parameter} = {value} (read back)")
                self.publish_parameter_status(parameter, value, "success")
                return "success"
            log.error(f"Verification failed: wrote {value}, read {read_value}")
            self.publish_parameter_status(parameter, read_value, "verification_failed")
            return "verification_failed"

        except Exception as e:
            log.error(f"Error setting parameter {parameter}: {e}")
            self.publish_parameter_status(parameter, None, f"error: {str(e)}")
            return f"error: {str(e)}"

    def handle_parameter_get(self, parameter: str):
        """Handle getting a single parameter"""
        try:
            if parameter not in self.CONFIG_REGISTERS:
                raise ValueError(f"Unknown parameter: {parameter}")
                
            register_info = self.CONFIG_REGISTERS[parameter]
            address = register_info['address']
            
            value = self.bus.read_register(self.modbus_address, address)
            log.info(f"Read {parameter} = {value} from register 0x{address:04X}")
            
            # Convert to human-readable if possible
            display_value = value
            if 'values' in register_info and value in register_info['values']:
                display_value = f"{value} ({register_info['values'][value]})"
                
            self.publish_parameter_value(parameter, value, display_value)
            
        except Exception as e:
            log.error(f"Error getting parameter {parameter}: {e}")
            self.publish_parameter_status(parameter, None, f"error: {str(e)}")

    def handle_batch_set(self, payload: str):
        """Handle batch configuration set"""
        try:
            config_data = json.loads(payload)
            results = {}
            
            log.info(f"Processing batch configuration: {len(config_data)} parameters")
            
            serial = config_data.pop('serial', None)
            for parameter, value in config_data.items():
                results[parameter] = self.handle_parameter_set(parameter, str(value), serial=serial)
                    
            # Publish batch results
            self.publish_batch_result(results)
            
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in batch configuration: {e}")
            self.publish_error("Invalid JSON format")
        except Exception as e:
            log.error(f"Error in batch configuration: {e}")
            self.publish_error(f"Batch configuration error: {str(e)}")

    def handle_backup(self):
        """Create a backup of current configuration"""
        try:
            backup_data = {}
            
            for parameter, register_info in self.CONFIG_REGISTERS.items():
                try:
                    address = register_info['address']
                    value = self.bus.read_register(self.modbus_address, address)
                    backup_data[parameter] = {
                        'value': value,
                        'address': f"0x{address:04X}",
                        'description': register_info.get('description', '')
                    }
                except Exception as e:
                    log.warning(f"Could not backup parameter {parameter}: {e}")
                    backup_data[parameter] = {'error': str(e)}
            
            # Add metadata
            backup_data['_metadata'] = {
                'timestamp': time.time(),
                'device_id': self.device_id,
                'backup_version': '1.0'
            }
            
            # Publish backup
            backup_topic = f"{self.config_topic_base}/backup/data"
            backup_json = json.dumps(backup_data, indent=2)
            self.config_mqtt_client.publish(backup_topic, backup_json, retain=True)
            
            log.info(f"Configuration backup created with {len(backup_data)-1} parameters")
            self.publish_status("Backup completed successfully")
            
        except Exception as e:
            log.error(f"Error creating backup: {e}")
            self.publish_error(f"Backup error: {str(e)}")

    def handle_restore(self, payload: str):
        """Restore configuration from backup"""
        try:
            backup_data = json.loads(payload)
            
            if '_metadata' not in backup_data:
                raise ValueError("Invalid backup format: missing metadata")
                
            restored = 0
            errors = 0
            serial = backup_data.pop('serial', None)       # critical parameters only with the serial number

            for parameter, data in backup_data.items():
                if parameter.startswith('_'):
                    continue  # Skip metadata
                    
                if 'error' in data:
                    log.warning(f"Skipping parameter {parameter}: backup contains error")
                    continue
                    
                status = self.handle_parameter_set(parameter, str(data.get('value')), serial=serial)
                if status == "success":
                    restored += 1
                else:
                    errors += 1
            
            log.info(f"Restore completed: {restored} parameters restored, {errors} errors")
            self.publish_status(f"Restore completed: {restored} restored, {errors} errors")
            
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in restore data: {e}")
            self.publish_error("Invalid backup JSON format")
        except Exception as e:
            log.error(f"Error in restore: {e}")
            self.publish_error(f"Restore error: {str(e)}")

    def publish_available_parameters(self):
        """Publish list of available configuration parameters"""
        try:
            parameters_info = {}
            
            for param, info in self.CONFIG_REGISTERS.items():
                parameters_info[param] = {
                    'address': f"0x{info['address']:04X}",
                    'type': info['type'],
                    'description': info.get('description', ''),
                    'writable': info.get('writable', False),
                    'min_value': info.get('min_value'),
                    'max_value': info.get('max_value'),
                    'values': info.get('values'),
                    'critical': bool(info.get('critical', False))
                }
            
            topic = f"{self.config_topic_base}/available"
            payload = json.dumps(parameters_info, indent=2)
            self.config_mqtt_client.publish(topic, payload, retain=True)
            
            log.info(f"Published {len(parameters_info)} available parameters")
            
        except Exception as e:
            log.error(f"Error publishing available parameters: {e}")

    def publish_parameter_status(self, parameter: str, value: Optional[int], status: str):
        """Publish parameter operation status"""
        status_topic = f"{self.config_topic_base}/{parameter}/status"
        status_data = {
            'parameter': parameter,
            'value': value,
            'status': status,
            'timestamp': time.time()
        }
        payload = json.dumps(status_data)
        self.config_mqtt_client.publish(status_topic, payload)

    def publish_parameter_value(self, parameter: str, value: int, display_value: Union[int, str]):
        """Publish parameter current value"""
        value_topic = f"{self.config_topic_base}/{parameter}/value"
        value_data = {
            'parameter': parameter,
            'value': value,
            'display_value': str(display_value),
            'timestamp': time.time()
        }
        payload = json.dumps(value_data)
        self.config_mqtt_client.publish(value_topic, payload)

    def publish_batch_result(self, results: Dict[str, str]):
        """Publish batch operation results"""
        result_topic = f"{self.config_topic_base}/batch/result"
        result_data = {
            'results': results,
            'timestamp': time.time()
        }
        payload = json.dumps(result_data, indent=2)
        self.config_mqtt_client.publish(result_topic, payload)

    def publish_status(self, message: str):
        """Publish general status message"""
        status_topic = f"{self.config_topic_base}/status"
        status_data = {
            'message': message,
            'timestamp': time.time()
        }
        payload = json.dumps(status_data)
        self.config_mqtt_client.publish(status_topic, payload)

    def publish_error(self, error_message: str):
        """Publish error message"""
        error_topic = f"{self.config_topic_base}/error"
        error_data = {
            'error': error_message,
            'timestamp': time.time()
        }
        payload = json.dumps(error_data)
        self.config_mqtt_client.publish(error_topic, payload)
