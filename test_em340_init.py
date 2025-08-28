#!/usr/bin/env python
"""
Test what happens when EM340 class encounters missing config parameters
"""
import os
import sys
import tempfile

# Create a minimal config with missing parameters
def test_em340_init_errors():
    """Test EM340 initialization with missing parameters"""
    
    print("=== Testing EM340 Initialization Errors ===")
    
    # Test 1: Missing config section
    test_yaml_missing_config = """
mqtt:
  broker: localhost
  port: 1883
  username: ""
  password: ""
  topic: em340
sensor: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(test_yaml_missing_config)
        f.flush()
        
        try:
            # Import here to avoid initialization issues
            sys.path.insert(0, '.')
            from em340 import EM340
            em340 = EM340(f.name)
            print("❌ ERROR: Should have failed on missing 'config' section")
        except SystemExit:
            print("✅ GOOD: Application exits gracefully on missing 'config' section")
        except KeyError as e:
            print(f"✅ GOOD: KeyError caught: {e}")
        except Exception as e:
            print(f"⚠️ UNEXPECTED: Got {type(e).__name__}: {e}")
        finally:
            os.unlink(f.name)

    # Test 2: Missing MQTT broker
    test_yaml_missing_mqtt = """
config:
  device: /dev/ttyUSB0
  modbus_address: 1
  t_delay_ms: 50
  serial_number: TEST123A
mqtt:
  port: 1883
  username: ""  
  password: ""
  topic: em340
sensor: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(test_yaml_missing_mqtt)
        f.flush()
        
        try:
            from em340 import EM340
            em340 = EM340(f.name)
            print("❌ ERROR: Should have failed on missing MQTT 'broker'")
        except SystemExit:
            print("✅ GOOD: Application exits gracefully on missing MQTT 'broker'")
        except KeyError as e:
            print(f"✅ GOOD: KeyError caught: {e}")
        except Exception as e:
            print(f"⚠️ UNEXPECTED: Got {type(e).__name__}: {e}")
        finally:
            os.unlink(f.name)

if __name__ == '__main__':
    test_em340_init_errors()
