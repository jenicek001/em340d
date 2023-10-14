import threading
import queue
import serial
import datetime
from datetime import timedelta
import yaml # pip install PyYAML
import sys
from logger import log
import paho.mqtt.client as mqtt
import json
import time

start_time = datetime.datetime.now()

#read_buffer = bytearray()

class MqttSender(threading.Thread):
    def __init__(self, mqtt_queue, config):
        threading.Thread.__init__(self)
        self.mqtt_queue = mqtt_queue
        self.config = config
        self.topic = self.config['mqtt']['topic'] + '/' + self.config['config']['name']
        self.client = mqtt.Client()
        self.client.username_pw_set(self.config['mqtt']['username'], self.config['mqtt']['password'])
        self.client.connect(self.config['mqtt']['broker'], self.config['mqtt']['port'], 60)
        log.info(f'Connected to MQTT broker: {self.config["mqtt"]["broker"]}:{self.config["mqtt"]["port"]}')

    def run(self):
        while True:
            try:
                data = self.mqtt_queue.get()
                topic = self.topic + '/'
                topic += data['subtopic'] if 'subtopic' in data else 'unkwnown'
                log.debug(f'topic: {topic}, data: {data}')
                self.client.publish(topic, json.dumps(data))
                #self.mqtt_queue.task_done()
            except Exception as e:
                log.error(f'Error publishing to MQTT broker: {e}')
                pass

# in GoodWe ModBus described CRC ：X^16+X^12+X^5+1
# ModBus standard: 0xA001

def calculate_crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc = crc ^ byte
        for i in range(8):
            last_bit = crc & 0x0001
            crc = crc >> 1
            if last_bit == 0x0001:
                crc = crc ^ 0xA001
#    log.info('crc: {}'.format(hex(crc)))
    #return crc
    return crc

def calculate_modbus_crc(data: bytes):
  """Calculates the Modbus CRC16 checksum of a byte array.

  Args:
    data: A byte array.

  Returns:
    A 16-bit CRC checksum.
  """

  crc = 0xFFFF
  for byte in data:
    crc ^= byte
    for i in range(8):
      if (crc & 0x0001) != 0:
        crc = (crc >> 1) ^ 0xA001
      else:
        crc >>= 1
  return crc

class SerialReader(threading.Thread):
    def __init__(self, port, baudrate, timeout, stopbits, recv_queue):
        threading.Thread.__init__(self)
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.stopbits = stopbits
        self.recv_queue = recv_queue
        #self.start_time = datetime.datetime.now()
        #self.last_character_time = self.start_time
        #self.read_buffer = bytearray()

    def run(self):
        with serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout, stopbits=self.stopbits) as ser:
            while True:
                x = ser.read()
                current_time = datetime.datetime.now()
                #relative_time_from_start = current_time - self.start_time
                #last_character_delay = current_time - self.last_character_time
                for c in x:
                    #self.read_buffer.append(c)
                    self.recv_queue.put((current_time, c))
                    self.last_character_time = current_time

from enum import IntEnum, unique
@unique
class ModBus_Parser_Status(IntEnum): # IntEnum or Enum, for Enum comparisons does not work well
    MODBUS_PARSER_WAITING_FOR_MASTER_REQUEST = 1
#    MODBUS_PARSER_READ_SLAVE_RESPONSE_MODBUS_ADDRESS = 2
    MODBUS_PARSER_READ_SLAVE_RESPONSE_FUNCTION_CODE = 3
    MODBUS_PARSER_READ_SLAVE_RESPONSE_AMOUNT_OF_BYTES = 4
    MODBUS_PARSER_READ_SLAVE_RESPONSE_DATA = 5
    MODBUS_PARSER_READ_SLAVE_RESPONSE_CRC_HIGH = 6
    MODBUS_PARSER_READ_SLAVE_RESPONSE_CRC_LOW = 7

class DataPrinter(threading.Thread):
    def __init__(self, recv_queue, mqtt_queue, config):
        threading.Thread.__init__(self)
        self.recv_queue = recv_queue
        self.last_character_time = datetime.datetime.now()
        self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_WAITING_FOR_MASTER_REQUEST
        self.modbus_slave_address = 0
        self.modbus_function_code = 0
        self.modbus_register_address = 0
        self.modbus_amount_of_registers = 0
        self.modbus_slave_data = bytearray()
        self.modbus_slave_crc_high = 0
        self.modbus_slave_crc_low = 0
        self.config = config
        self.mqtt_queue = mqtt_queue

    def run(self):
        last_character_delay = timedelta()
        read_buffer = bytearray() # ModBus packet buffer
        while True:
            data = self.recv_queue.get() # blocking function to read from queue
            char_recv_time = data[0]
            byte = data[1]

            read_buffer.append(byte) # add byte to ModBus packet buffer
            last_character_delay = char_recv_time - self.last_character_time
            self.last_character_time = char_recv_time

            # print zero-padded byte in 0x00 format
            #log.debug('recv. byte: {}'.format(f'{byte:#0{4}x}'))
            log.debug('recv. byte: {} {}'.format(f'{byte:#0{4}x}', last_character_delay))

            # synchronization within RS485 data stream - looking for a ModBus Master request
            if self.modbus_parser_status == ModBus_Parser_Status.MODBUS_PARSER_WAITING_FOR_MASTER_REQUEST:

                # check for a ModBus delay of 4ms between characters (for 9600 baudrate) - see https://minimalmodbus.readthedocs.io/en/stable/serialcommunication.html
                if last_character_delay > timedelta(milliseconds=4):
                    
                    # print all the bytes in the buffer in the zero padded format 0x00 to a single line
                    log.debug('looking for ModBus Master request - read_buffer after 4ms delay: size={} {}'.format(len(read_buffer), [f'{i:#0{4}x}' for i in read_buffer]))

                    # decode the ModBus message
                    if len(read_buffer) >= 9: # incl. first characters of next message
                        self.modbus_slave_address = read_buffer[0]
                        self.modbus_function_code = read_buffer[1]
                        self.modbus_register_address = read_buffer[2] << 8 | read_buffer[3]
                        self.modbus_amount_of_registers = read_buffer[4] << 8 | read_buffer[5]
                        modbus_crc = read_buffer[7] << 8 | read_buffer[6] # this does not correspond to GoodWe documentation, however works
                        calculated_crc = calculate_crc16(read_buffer[0:6])
                        #calculated_crc_3 = calculate_modbus_crc(read_buffer[0:6])

                        if calculated_crc == modbus_crc:
                            #log.debug('modbus_slave_address: {}'.format(self.modbus_slave_address))
                            #log.debug('modbus_function_code: {}'.format(self.modbus_function_code))
                            #log.debug('modbus_register_address: {}'.format(self.modbus_register_address))
                            #log.debug('modbus_amount_of_registers: {}'.format(self.modbus_amount_of_registers))
                            #log.debug('modbus_crc: {}'.format(hex(modbus_crc)))
                            #log.debug('calculated_crc: {}'.format(hex(calculated_crc)))
                            #log.debug('calculated_crc_3: {}'.format(hex(calculated_crc_3)))
                            log.debug(f'ModBus Master request CRC ok - waiting for slave registers address: {hex(self.modbus_register_address)}, amount of registers: {self.modbus_amount_of_registers}')
                            #self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_MODBUS_ADDRESS
                            
                            # last byte is already first byte of slave response (slave address)
                            if read_buffer[8] == self.modbus_slave_address:
                                self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_FUNCTION_CODE
                            else:
                                log.error(f'modbus_slave_address error: recv {hex(read_buffer[8])}, expected: {hex(self.modbus_slave_address)})')
                                # print error with red color terminal text
                                print('\033[91m' + f'modbus_slave_address error: recv {hex(read_buffer[8])}, expected: {hex(self.modbus_slave_address)})' + '\033[0m')
                                self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_WAITING_FOR_MASTER_REQUEST
                            
                        else:
                            log.error('crc error: modbus_crc={} calculated_crc={}'.format(hex(modbus_crc), hex(calculated_crc)))

                        # captured combination of packets, delete parsed packet from buffer
                        # keep only characters of the next message (starting with character 9 - first character of the next message)
                        log.debug('before reduction: size={} {}'.format(len(read_buffer), [f'{i:#0{4}x}' for i in read_buffer]))
                        read_buffer = read_buffer[8:]
                        log.debug('reduced read buffer: size={} {}'.format(len(read_buffer), [f'{i:#0{4}x}' for i in read_buffer]))
                    
                    else:
                        log.debug('after inter-message delay read_buffer too small: size={} {}, waiting for additional data...'.format(len(read_buffer), [f'{i:#0{4}x}' for i in read_buffer]))

            # elif self.modbus_parser_status == ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_MODBUS_ADDRESS:
            #     if byte == self.modbus_slave_address:
            #         self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_FUNCTION_CODE
            #     else:
            #         log.error(f'modbus_slave_address error: recv {hex(byte)}, expected: {hex(self.modbus_slave_address)})')
            #         self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_WAITING_FOR_MASTER_REQUEST
                
            elif self.modbus_parser_status == ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_FUNCTION_CODE:
                if byte == self.modbus_function_code:
                    self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_AMOUNT_OF_BYTES
                else:
                    log.error(f'modbus_function_code error: recv {hex(byte)}, expected: {hex(self.modbus_function_code)})')
                    self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_WAITING_FOR_MASTER_REQUEST
            
            elif self.modbus_parser_status == ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_AMOUNT_OF_BYTES:
                if byte == self.modbus_amount_of_registers * 2:
                    self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_DATA
                    self.modbus_slave_data.clear()
                else:
                    #log.debug('read_buffer: size={} {}'.format(len(read_buffer), [f'{i:#0{4}x}' for i in read_buffer]))
                    log.error(f'modbus_amount_of_bytes error - could be repeated Master Request: recv {hex(byte)}, expected: {hex(self.modbus_amount_of_registers * 2)})' + ', read_buffer: size={} {}'.format(len(read_buffer), [f'{i:#0{4}x}' for i in read_buffer]))
                    self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_WAITING_FOR_MASTER_REQUEST

            elif self.modbus_parser_status == ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_DATA:
                self.modbus_slave_data.append(byte)
                if len(self.modbus_slave_data) == self.modbus_amount_of_registers * 2:
                    self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_CRC_HIGH
                    # print all response data in 0x00 zero padded format
                    #log.error('modbus_slave_data: {}'.format([f'{i:#0{4}x}' for i in self.modbus_slave_data]))
            
            elif self.modbus_parser_status == ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_CRC_HIGH:
                self.modbus_slave_crc_high = byte
                self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_CRC_LOW
            
            elif self.modbus_parser_status == ModBus_Parser_Status.MODBUS_PARSER_READ_SLAVE_RESPONSE_CRC_LOW:
                self.modbus_slave_crc_low = byte
                modbus_crc = self.modbus_slave_crc_low << 8 | self.modbus_slave_crc_high # this does not correspond to GoodWe documentation, however works
                data_for_crc = bytearray()
                data_for_crc.append(self.modbus_slave_address)
                data_for_crc.append(self.modbus_function_code)
                data_for_crc.append(self.modbus_amount_of_registers * 2)
                data_for_crc.extend(self.modbus_slave_data)
                calculated_crc = calculate_crc16(data_for_crc)
                if calculated_crc == modbus_crc:
                    # log.error(f'modbus_crc: {hex(modbus_crc)} calculated_crc: {hex(calculated_crc)}')
                    log.debug('recv. crc ok, modbus_slave_data payload: {} - parsing...'.format([f'{i:#0{4}x}' for i in self.modbus_slave_data]))
                else:
                    log.error(f'crc error: modbus_crc={hex(modbus_crc)} calculated_crc={hex(calculated_crc)}')
                self.modbus_parser_status = ModBus_Parser_Status.MODBUS_PARSER_WAITING_FOR_MASTER_REQUEST
                read_buffer.clear()

                smart_meter_data = {}
                smart_meter_data['timestamp'] = datetime.datetime.now().isoformat()
                register_address = self.modbus_register_address
                if register_address == 0x0000:
                    smart_meter_data['subtopic'] = 'voltage_current'
                elif register_address == 0x0012:
                    smart_meter_data['subtopic'] = 'active_power'
                elif register_address == 0x004E:
                    smart_meter_data['subtopic'] = 'total_exported_energy'
                elif register_address == 0x0034:
                    smart_meter_data['subtopic'] = 'total_imported_energy'
                else:
                    smart_meter_data['subtopic'] = 'unknown'

                while len(self.modbus_slave_data) > 0:

                    log.debug(f'register_address: {hex(register_address)}')

                    for register in self.config['sensor']:
                        if register['address'] == register_address:

                            log.debug(f'{register["name"]} {register["value_type"]} {register["multiply"]} {register["unit_of_measurement"]}')

                            number_of_registers = 0
                            if register['value_type'] == "INT16" or register['value_type'] == "UINT16":
                                number_of_registers = 1
                            elif register['value_type'] == "INT32" or register['value_type'] == "UINT32":
                                number_of_registers = 2
                            elif register['value_type'] == "INT64" or register['value_type'] == "UINT64":
                                number_of_registers = 4
                            else:
                                log.error(f"Unknown value type {register['value_type']}")
                                raise ValueError(f"Unknown value type {register['value_type']}")
                    
                            value = None
                            if register['value_type'] == "INT16":
                                value = self.modbus_slave_data[0] << 8 | self.modbus_slave_data[1]
                                if value & 0x8000:
                                    value = -0x10000 + value
                            elif register['value_type'] == "UINT16":
                                value = self.modbus_slave_data[0] << 8 | self.modbus_slave_data[1]
                            elif register['value_type'] == "INT32":
                                value = self.modbus_slave_data[0] << 8 | self.modbus_slave_data[1] | self.modbus_slave_data[2] << 24 | self.modbus_slave_data[3] << 16
                                if value & 0x80000000:
                                    value = -0x100000000 + value
                            elif register['value_type'] == "UINT32":
                                value = self.modbus_slave_data[0] | self.modbus_slave_data[1] << 16 | self.modbus_slave_data[2] << 8 | self.modbus_slave_data[3] << 24
                            elif register['value_type'] == "INT64":
                                value = self.modbus_slave_data[0] | self.modbus_slave_data[1] << 16 | self.modbus_slave_data[2] << 32 | self.modbus_slave_data[3] << 48 | self.modbus_slave_data[4] << 8 | self.modbus_slave_data[5] << 24 | self.modbus_slave_data[6] << 40 | self.modbus_slave_data[7] << 56
                                if value & 0x8000000000000000:
                                    value = -0x10000000000000000 + value
                            elif register['value_type'] == "UINT64":
                                value = self.modbus_slave_data[0] | self.modbus_slave_data[1] << 16 | self.modbus_slave_data[2] << 32 | self.modbus_slave_data[3] << 48 | self.modbus_slave_data[4] << 8 | self.modbus_slave_data[5] << 24 | self.modbus_slave_data[6] << 40 | self.modbus_slave_data[7] << 56

                            value = value * float(register['multiply'])
                            units = register['unit_of_measurement'] if 'unit_of_measurement' in register else ''
                            log.debug(f'{register["name"]} {value} {units}')
                            smart_meter_data[register['id']] = value

                            break

                    register_address += number_of_registers
                    self.modbus_slave_data = self.modbus_slave_data[(number_of_registers*2):]
                        
                # push data to MQTT queue
                log.debug(f'pushing to mqtt_queue: {smart_meter_data}')
                self.mqtt_queue.put(smart_meter_data)
                

if __name__ == '__main__':
    log.info('Starting EM340 ModBus sniffer to MQTT...')

    try:
        em340_config = yaml.load(open('em340.yaml'), Loader=yaml.FullLoader)
    except Exception as e:
        log.error(f'Error loading YAML file: {e}')
        sys.exit()

    device = em340_config['config']['device']
    modbus_address = em340_config['config']['modbus_address']
    t_delay_seconds = em340_config['config']['t_delay_ms'] / 1000.0

    q = queue.Queue()
    mqtt_q = queue.Queue()
    reader = SerialReader(port=device, baudrate=9600, timeout=1, stopbits=serial.STOPBITS_ONE, recv_queue=q)
    printer = DataPrinter(recv_queue=q, mqtt_queue=mqtt_q, config=em340_config)
    sender = MqttSender(mqtt_queue=mqtt_q, config=em340_config)
    reader.start()
    printer.start()
    sender.start()
    try:
        # sleep forever and let threads do their job
        while True:
            # sleep to reduce CPU usage
            time.sleep(10)
            pass
            
    except KeyboardInterrupt:
        reader.join()
        printer.join()
        sender.join()
