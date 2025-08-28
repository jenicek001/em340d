#!/usr/bin/env python
"""
EM340 MQTT Configuration Module
Listens to MQTT configuration topics and applies settings to the EM340 device
"""

import json
import time
import paho.mqtt.client as mqtt
from logger import log
import minimalmodbus
from typing import Dict, Any, Optional, Union

class EM340ConfigManager:
    """Manages EM340 configuration via MQTT commands"""
    
    # ModBus register definitions based on EM340 specification
    CONFIG_REGISTERS = {
        # System Configuration (0x1000-0x1100 range)
        'password': {
            'address': 0x1000,
            'type': 'UINT16',
            'min_value': 0,
            'max_value': 9999,
            'description': 'Device password (EM only)',
            'writable': True
        },
        'measuring_system': {
            'address': 0x1002,
            'type': 'UINT16',
            'min_value': 0,
            'max_value': 2,
            'description': 'Measuring system configuration',
            'values': {
                0: '3-phase 4-wire with neutral',
                1: '3-phase 3-wire without neutral', 
                2: '2-phase 3-wire'
            },
            'writable': True
        },
        'display_mode': {
            'address': 0x1101,
            'type': 'UINT16',
            'description': 'Display mode configuration',
            'writable': True
        },
        'tariff_enabling': {
            'address': 0x1101,
            'type': 'UINT16',
            'description': 'Tariff management enabling',
            'writable': True
        },
        'home_page_selection': {
            'address': 0x1102,
            'type': 'UINT16',
            'description': 'Home page selection (EM only)',
            'writable': True
        },
        'measurement_mode': {
            'address': 0x1103,
            'type': 'UINT16',
            'min_value': 0,
            'max_value': 1,
            'description': 'Measurement mode selection',
            'values': {
                0: 'Easy connection mode (A)',
                1: 'Bidirectional mode (B)'
            },
            'writable': True
        },
        'wrong_connection_help': {
            'address': 0x1104,
            'type': 'UINT16',
            'description': 'Wrong connection installing help enabling',
            'writable': True
        },
        
        # PT/CT Configuration (estimated addresses - need verification)
        'pt_primary': {
            'address': 0x1200,
            'type': 'UINT16',
            'min_value': 1,
            'max_value': 65535,
            'description': 'Potential transformer primary voltage',
            'writable': True
        },
        'pt_secondary': {
            'address': 0x1201,
            'type': 'UINT16',
            'min_value': 1,
            'max_value': 65535,
            'description': 'Potential transformer secondary voltage',
            'writable': True
        },
        'ct_primary': {
            'address': 0x1202,
            'type': 'UINT16',
            'min_value': 1,
            'max_value': 65535,
            'description': 'Current transformer primary current',
            'writable': True
        },
        'ct_secondary': {
            'address': 0x1203,
            'type': 'UINT16',
            'min_value': 1,
            'max_value': 5,
            'description': 'Current transformer secondary current',
            'values': {1: '1A', 5: '5A'},
            'writable': True
        }
    }
    
    def __init__(self, mqtt_config: Dict[str, Any], modbus_device: str, modbus_address: int):
        """Initialize the configuration manager"""
        self.mqtt_config = mqtt_config
        self.modbus_device = modbus_device
        self.modbus_address = modbus_address
        
        # Initialize ModBus connection
        self.modbus = minimalmodbus.Instrument(modbus_device, modbus_address)
        self.modbus.serial.baudrate = 9600
        self.modbus.serial.bytesize = 8
        self.modbus.serial.parity = minimalmodbus.serial.PARITY_NONE
        self.modbus.serial.stopbits = 1
        self.modbus.serial.timeout = 1.0  # Longer timeout for config operations
        self.modbus.mode = minimalmodbus.MODE_RTU
        
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
        
        log.info(f"EM340 Config Manager initialized for device {self.device_id}")
        log.info(f"Configuration topics base: {self.config_topic_base}")

    def start_config_service(self):
        """Start the MQTT configuration service"""
        try:
            self.config_mqtt_client.loop_start()
            self.config_mqtt_client.connect(self.mqtt_config['broker'], self.mqtt_config['port'])
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
                f"{self.config_topic_base}/reset",           # Reset to defaults
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
            topic_parts = topic.replace(f"{self.config_topic_base}/", "").split("/")
            
            if len(topic_parts) >= 2:
                parameter = topic_parts[0]
                action = topic_parts[1]
                
                if action == "set":
                    self.handle_parameter_set(parameter, payload)
                elif action == "get":
                    self.handle_parameter_get(parameter)
                    
            elif len(topic_parts) == 1:
                action = topic_parts[0]
                
                if action == "batch/set":
                    self.handle_batch_set(payload)
                elif action == "reset":
                    self.handle_reset()
                elif action == "backup":
                    self.handle_backup()
                elif action == "restore":
                    self.handle_restore(payload)
                    
        except Exception as e:
            log.error(f"Error processing configuration message: {e}")
            self.publish_error(f"Error processing message: {str(e)}")

    def handle_parameter_set(self, parameter: str, payload: str):
        """Handle setting a single parameter"""
        try:
            if parameter not in self.CONFIG_REGISTERS:
                raise ValueError(f"Unknown parameter: {parameter}")
                
            register_info = self.CONFIG_REGISTERS[parameter]
            
            if not register_info.get('writable', False):
                raise ValueError(f"Parameter {parameter} is read-only")
            
            # Parse and validate value
            try:
                value = int(payload)
            except ValueError:
                # Try to parse as string for named values
                if 'values' in register_info:
                    reverse_values = {v: k for k, v in register_info['values'].items()}
                    if payload in reverse_values:
                        value = reverse_values[payload]
                    else:
                        raise ValueError(f"Invalid value '{payload}' for parameter {parameter}")
                else:
                    raise ValueError(f"Invalid numeric value: {payload}")
            
            # Validate range
            if 'min_value' in register_info and value < register_info['min_value']:
                raise ValueError(f"Value {value} below minimum {register_info['min_value']}")
            if 'max_value' in register_info and value > register_info['max_value']:
                raise ValueError(f"Value {value} above maximum {register_info['max_value']}")
                
            # Write to ModBus register
            address = register_info['address']
            log.info(f"Writing {parameter} = {value} to register 0x{address:04X}")
            
            self.modbus.write_register(address, value, functioncode=6)
            time.sleep(0.1)  # Short delay after write
            
            # Verify write by reading back
            read_value = self.modbus.read_register(address)
            if read_value == value:
                log.info(f"Successfully set {parameter} = {value}")
                self.publish_parameter_status(parameter, value, "success")
            else:
                log.error(f"Verification failed: wrote {value}, read {read_value}")
                self.publish_parameter_status(parameter, read_value, "verification_failed")
                
        except Exception as e:
            log.error(f"Error setting parameter {parameter}: {e}")
            self.publish_parameter_status(parameter, None, f"error: {str(e)}")

    def handle_parameter_get(self, parameter: str):
        """Handle getting a single parameter"""
        try:
            if parameter not in self.CONFIG_REGISTERS:
                raise ValueError(f"Unknown parameter: {parameter}")
                
            register_info = self.CONFIG_REGISTERS[parameter]
            address = register_info['address']
            
            value = self.modbus.read_register(address)
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
            
            for parameter, value in config_data.items():
                try:
                    self.handle_parameter_set(parameter, str(value))
                    results[parameter] = "success"
                except Exception as e:
                    results[parameter] = f"error: {str(e)}"
                    log.error(f"Batch set error for {parameter}: {e}")
                    
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
                    value = self.modbus.read_register(address)
                    backup_data[parameter] = {
                        'value': value,
                        'address': f"0x{address:04X}",
                        'description': register_info.get('description', '')
                    }
                    time.sleep(0.05)  # Small delay between reads
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
            
            for parameter, data in backup_data.items():
                if parameter.startswith('_'):
                    continue  # Skip metadata
                    
                if 'error' in data:
                    log.warning(f"Skipping parameter {parameter}: backup contains error")
                    continue
                    
                try:
                    value = data['value']
                    self.handle_parameter_set(parameter, str(value))
                    restored += 1
                except Exception as e:
                    log.error(f"Error restoring parameter {parameter}: {e}")
                    errors += 1
            
            log.info(f"Restore completed: {restored} parameters restored, {errors} errors")
            self.publish_status(f"Restore completed: {restored} restored, {errors} errors")
            
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in restore data: {e}")
            self.publish_error("Invalid backup JSON format")
        except Exception as e:
            log.error(f"Error in restore: {e}")
            self.publish_error(f"Restore error: {str(e)}")

    def handle_reset(self):
        """Reset configuration to factory defaults"""
        try:
            # Define factory defaults (based on typical EM340 settings)
            factory_defaults = {
                'measuring_system': 0,      # 3-phase 4-wire with neutral
                'measurement_mode': 0,      # Easy connection mode (A)
                'pt_primary': 400,          # 400V primary
                'pt_secondary': 400,        # 400V secondary (1:1)
                'ct_primary': 5,            # 5A primary
                'ct_secondary': 5           # 5A secondary (1:1)
            }
            
            reset_count = 0
            for parameter, default_value in factory_defaults.items():
                if parameter in self.CONFIG_REGISTERS:
                    try:
                        self.handle_parameter_set(parameter, str(default_value))
                        reset_count += 1
                    except Exception as e:
                        log.error(f"Error resetting parameter {parameter}: {e}")
            
            log.info(f"Factory reset completed: {reset_count} parameters reset")
            self.publish_status(f"Factory reset completed: {reset_count} parameters reset")
            
        except Exception as e:
            log.error(f"Error in factory reset: {e}")
            self.publish_error(f"Factory reset error: {str(e)}")

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
                    'values': info.get('values')
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
