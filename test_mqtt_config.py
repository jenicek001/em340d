#!/usr/bin/env python
"""
EM340 MQTT Configuration Test Script
Demonstrates how to use MQTT topics to configure EM340 device parameters
"""

import json
import time
import paho.mqtt.client as mqtt
from datetime import datetime

class EM340ConfigTester:
    """Test client for EM340 MQTT configuration"""
    
    def __init__(self, mqtt_broker='localhost', mqtt_port=1883, device_id='235411W'):
        self.broker = mqtt_broker
        self.port = mqtt_port
        self.device_id = device_id
        self.base_topic = f"em340/{device_id}/config"
        
        # MQTT client for testing
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        print(f"EM340 Configuration Tester")
        print(f"Device ID: {device_id}")
        print(f"Base topic: {self.base_topic}")

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        """Handle MQTT connection"""
        if reason_code == 0:
            print(f"✅ Connected to MQTT broker at {self.broker}:{self.port}")
            
            # Subscribe to all response topics
            client.subscribe(f"{self.base_topic}/+/status")
            client.subscribe(f"{self.base_topic}/+/value")
            client.subscribe(f"{self.base_topic}/batch/result")
            client.subscribe(f"{self.base_topic}/status")
            client.subscribe(f"{self.base_topic}/error")
            client.subscribe(f"{self.base_topic}/available")
            
            print("📡 Subscribed to configuration response topics")
        else:
            print(f"❌ Failed to connect: {reason_code}")

    def on_message(self, client, userdata, message):
        """Handle MQTT messages"""
        topic = message.topic
        payload = message.payload.decode('utf-8')
        
        print(f"\n📨 Response: {topic}")
        try:
            data = json.loads(payload)
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print(f"Raw: {payload}")

    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            time.sleep(2)  # Wait for connection
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()

    def get_available_parameters(self):
        """Request list of available parameters"""
        print("\n🔍 Requesting available parameters...")
        topic = f"{self.base_topic}/available/get"
        self.client.publish(topic, "")

    def get_parameter(self, parameter):
        """Get a specific parameter value"""
        print(f"\n📖 Getting parameter: {parameter}")
        topic = f"{self.base_topic}/{parameter}/get"
        self.client.publish(topic, "")

    def set_parameter(self, parameter, value):
        """Set a specific parameter value"""
        print(f"\n✏️ Setting parameter: {parameter} = {value}")
        topic = f"{self.base_topic}/{parameter}/set"
        self.client.publish(topic, str(value))

    def batch_configure(self, config_dict):
        """Configure multiple parameters at once"""
        print(f"\n📦 Batch configuration: {len(config_dict)} parameters")
        topic = f"{self.base_topic}/batch/set"
        payload = json.dumps(config_dict)
        self.client.publish(topic, payload)

    def backup_configuration(self):
        """Create configuration backup"""
        print(f"\n💾 Creating configuration backup...")
        topic = f"{self.base_topic}/backup"
        self.client.publish(topic, "")

    def restore_configuration(self, backup_data):
        """Restore configuration from backup"""
        print(f"\n🔄 Restoring configuration...")
        topic = f"{self.base_topic}/restore"
        payload = json.dumps(backup_data)
        self.client.publish(topic, payload)

    def factory_reset(self):
        """Reset to factory defaults"""
        print(f"\n🏭 Factory reset...")
        topic = f"{self.base_topic}/reset"
        self.client.publish(topic, "")

def run_demo():
    """Run configuration demo"""
    print("=" * 60)
    print("EM340 MQTT Configuration Demo")
    print("=" * 60)
    
    # Initialize tester
    tester = EM340ConfigTester()
    
    if not tester.connect():
        return
    
    try:
        # Demo sequence
        print("\n🎯 Starting configuration demo...")
        
        # 1. Get available parameters
        tester.get_available_parameters()
        time.sleep(2)
        
        # 2. Get current measurement mode
        tester.get_parameter("measurement_mode")
        time.sleep(2)
        
        # 3. Get current measuring system
        tester.get_parameter("measuring_system")
        time.sleep(2)
        
        # 4. Set measurement mode to bidirectional (B)
        tester.set_parameter("measurement_mode", 1)
        time.sleep(2)
        
        # 5. Verify the change
        tester.get_parameter("measurement_mode")
        time.sleep(2)
        
        # 6. Set measuring system to 3-phase without neutral
        tester.set_parameter("measuring_system", 1)
        time.sleep(2)
        
        # 7. Batch configuration example
        batch_config = {
            "measurement_mode": 0,        # Easy connection mode (A)
            "measuring_system": 0,        # 3-phase 4-wire with neutral
            "pt_primary": 400,            # 400V primary
            "ct_primary": 5               # 5A primary
        }
        tester.batch_configure(batch_config)
        time.sleep(3)
        
        # 8. Create backup
        tester.backup_configuration()
        time.sleep(2)
        
        print("\n✅ Demo completed! Check the responses above.")
        
    except KeyboardInterrupt:
        print("\n⏹️ Demo interrupted by user")
    
    finally:
        tester.disconnect()

def run_interactive():
    """Run interactive configuration tool"""
    print("=" * 60)
    print("EM340 Interactive Configuration Tool")
    print("=" * 60)
    
    tester = EM340ConfigTester()
    
    if not tester.connect():
        return
    
    try:
        while True:
            print("\n" + "─" * 40)
            print("Configuration Options:")
            print("1. Get available parameters")
            print("2. Get parameter value")
            print("3. Set parameter value")
            print("4. Batch configure")
            print("5. Create backup")
            print("6. Factory reset")
            print("7. Run demo")
            print("0. Exit")
            print("─" * 40)
            
            choice = input("Select option (0-7): ").strip()
            
            if choice == "0":
                break
            elif choice == "1":
                tester.get_available_parameters()
            elif choice == "2":
                param = input("Parameter name: ").strip()
                if param:
                    tester.get_parameter(param)
            elif choice == "3":
                param = input("Parameter name: ").strip()
                value = input("Value: ").strip()
                if param and value:
                    tester.set_parameter(param, value)
            elif choice == "4":
                print("Enter JSON configuration (e.g., {'measurement_mode': 1}):")
                config_str = input().strip()
                try:
                    config_dict = json.loads(config_str)
                    tester.batch_configure(config_dict)
                except json.JSONDecodeError:
                    print("❌ Invalid JSON format")
            elif choice == "5":
                tester.backup_configuration()
            elif choice == "6":
                confirm = input("⚠️ This will reset all settings. Continue? (yes/no): ")
                if confirm.lower() == "yes":
                    tester.factory_reset()
            elif choice == "7":
                run_demo()
                break
            else:
                print("❌ Invalid option")
            
            time.sleep(1)  # Small delay for responses
            
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
    
    finally:
        tester.disconnect()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        run_demo()
    else:
        run_interactive()
