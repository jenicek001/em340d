#!/usr/bin/env python
"""
Test script to check configuration error handling
"""
import os
import sys
import tempfile
import yaml

# Import just the config loader without logger dependency
sys.path.insert(0, '.')
from config_loader import load_yaml_with_env

def test_missing_sections():
    """Test behavior when entire sections are missing"""
    
    print("=== Testing Missing Configuration Sections ===")
    
    # Test 1: Missing 'config' section
    test_yaml = """
mqtt:
  broker: localhost
  port: 1883
  topic: em340
sensor:
  - id: test
    name: Test
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(test_yaml)
        f.flush()
        
        try:
            config = load_yaml_with_env(f.name)
            device = config['config']['device']  # This should fail
            print("❌ ERROR: Should have failed on missing 'config' section")
        except KeyError as e:
            print(f"✅ GOOD: KeyError caught for missing 'config' section: {e}")
        except Exception as e:
            print(f"⚠️ UNEXPECTED: Got {type(e).__name__}: {e}")
        finally:
            os.unlink(f.name)

def test_missing_config_keys():
    """Test behavior when config section keys are missing"""
    
    print("\n=== Testing Missing Config Keys ===")
    
    # Test missing device key
    test_yaml = """
config:
  modbus_address: 1
  t_delay_ms: 50
mqtt:
  broker: localhost
  port: 1883
  topic: em340
sensor: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(test_yaml)
        f.flush()
        
        try:
            config = load_yaml_with_env(f.name)
            device = config['config']['device']  # Missing key
            print("❌ ERROR: Should have failed on missing 'device' key")
        except KeyError as e:
            print(f"✅ GOOD: KeyError caught for missing 'device' key: {e}")
        except Exception as e:
            print(f"⚠️ UNEXPECTED: Got {type(e).__name__}: {e}")
        finally:
            os.unlink(f.name)

def test_missing_mqtt_keys():
    """Test behavior when MQTT section keys are missing"""
    
    print("\n=== Testing Missing MQTT Keys ===")
    
    # Test missing broker key
    test_yaml = """
config:
  device: /dev/ttyUSB0
  modbus_address: 1
  t_delay_ms: 50
mqtt:
  port: 1883
  topic: em340
sensor: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(test_yaml)
        f.flush()
        
        try:
            config = load_yaml_with_env(f.name)
            broker = config['mqtt']['broker']  # Missing key
            print("❌ ERROR: Should have failed on missing 'broker' key")
        except KeyError as e:
            print(f"✅ GOOD: KeyError caught for missing 'broker' key: {e}")
        except Exception as e:
            print(f"⚠️ UNEXPECTED: Got {type(e).__name__}: {e}")
        finally:
            os.unlink(f.name)

def test_missing_env_variable():
    """Test behavior when environment variable is missing"""
    
    print("\n=== Testing Missing Environment Variables ===")
    
    # Test required env var (no default)
    test_yaml = """
config:
  device: ${MISSING_DEVICE}
  modbus_address: 1
mqtt:
  broker: localhost
sensor: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(test_yaml)
        f.flush()
        
        try:
            # Make sure the env var doesn't exist
            if 'MISSING_DEVICE' in os.environ:
                del os.environ['MISSING_DEVICE']
                
            config = load_yaml_with_env(f.name)
            print("❌ ERROR: Should have failed on missing required env var")
        except ValueError as e:
            print(f"✅ GOOD: ValueError caught for missing required env var: {e}")
        except Exception as e:
            print(f"⚠️ UNEXPECTED: Got {type(e).__name__}: {e}")
        finally:
            os.unlink(f.name)

def test_sensor_missing_keys():
    """Test behavior when sensor configuration has missing keys"""
    
    print("\n=== Testing Missing Sensor Keys ===")
    
    # Test sensor with missing required fields
    test_yaml = """
config:
  device: /dev/ttyUSB0
  modbus_address: 1
  t_delay_ms: 50
mqtt:
  broker: localhost
  port: 1883
  topic: em340
sensor:
  - id: test_sensor
    name: "Test Sensor"
    # Missing: address, value_type, multiply
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(test_yaml)
        f.flush()
        
        try:
            config = load_yaml_with_env(f.name)
            # This would typically fail during sensor processing
            sensor = config['sensor'][0]
            address = sensor['address']  # Missing key
            print("❌ ERROR: Should have failed on missing 'address' key")
        except KeyError as e:
            print(f"✅ GOOD: KeyError caught for missing sensor 'address' key: {e}")
        except Exception as e:
            print(f"⚠️ UNEXPECTED: Got {type(e).__name__}: {e}")
        finally:
            os.unlink(f.name)

if __name__ == '__main__':
    print("Testing EM340D Configuration Error Handling")
    print("=" * 50)
    
    test_missing_sections()
    test_missing_config_keys()
    test_missing_mqtt_keys()
    test_missing_env_variable()
    test_sensor_missing_keys()
    
    print("\n" + "=" * 50)
    print("Configuration error testing completed")
