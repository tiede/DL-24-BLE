import asyncio
from bleak import BleakScanner, BleakClient
import logging
import json
import sys
import datetime
from collections import OrderedDict

from bleak.backends.device import BLEDevice

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

device_name = "DL24_BLE"
char_uuid = '0000ffe1-0000-1000-8000-00805f9b34fb'

class DL24Logger:
    """ 
    Class for logging data from DL24 BLE device.
    """
    def __init__(self, format):
        self.format = format
        self.log_number = 0
        self.session_start = datetime.datetime.now()
        self.session_total_capacity = 0
        self.last_read = datetime.datetime.now()
        
    def log(self, sender, data):
        """
    Log data from DL24 BLE device.

    This is the callback function that is called on every measurement
    """
        data_dict = OrderedDict()
        voltage = int.from_bytes(data[0x04:0x07], 'big', signed=False) / 10.0
        current = int.from_bytes(data[0x07:0x0a], 'big', signed=False)
        power = voltage * (current / 1000)
        resistance = 0
        if (voltage > 0 and current > 0):
            resistance = voltage / (current/1000)
        capacity = int.from_bytes(data[0x0a:0x0d], 'big', signed=False) * 10
        energy = int.from_bytes(data[0x0d:0x11]) * 10
        temperature = int.from_bytes(data[0x18:0x1a], 'big', signed=False)

        # Capacity in mAh on the basis of 1-second updates
        self.session_total_capacity = self.session_total_capacity + current / 3600

        data_dict['timestamp'] = datetime.datetime.now().isoformat()
        data_dict['voltage_V'] = voltage 
        data_dict['current_mA'] = current
        data_dict['power_W'] = f'{power:.2f}'
        data_dict['resistance_Ohm'] = f'{resistance:.2f}'
        data_dict['capacity_mAh'] = capacity
        data_dict['energy_Wh'] = energy
        data_dict['session_total_capacity_mAh'] = f'{self.session_total_capacity:.2f}'

        data_dict['temperature_C'] = temperature

        if (self.format == 'csv'):
            self.csv(data_dict)
        elif (self.format == 'json'):
            self.json(data_dict)

        self.log_number += 1
        self.last_read = datetime.datetime.now()

    def csv(self, data_dict):
        """ 
        Log data in CSV format.
        """
        if self.log_number == 0:
            print(','.join(data_dict.keys()))
        print(','.join([str(x) for x in data_dict.values()]))

    def json(self, data_dict):
        """ 
        Log data in JSON format.
        """
        json.dump(data_dict, sys.stdout)
        
async def discover_device(device_name) -> BLEDevice:
    """ 
    Discover DL24 BLE device given the name of the device
    """
    while (True):
        devices = await BleakScanner.discover()
        for d in devices:
            logger.debug(f'Device {d.name} discovered')
            if (d.name.find(device_name) >= 0):
                return d

async def read(device, char_uuid, dl24logger):
    """ 
    Read data from DL24 BLE device given the device and the UUID of the characteristic
    """
    async with BleakClient(
        device,
        pair=True,
        timeout=60
    ) as client:
        logger.info("connected")

        await client.start_notify(char_uuid, dl24logger.log)
        while (True):
            await asyncio.sleep(1)
            if (datetime.datetime.now() - dl24logger.last_read).total_seconds() > 30:
                raise Exception("No data received for 30 seconds")

async def main():
    dl24logger = DL24Logger('csv')
    #dl24logger = DL24Logger('json')
    device = await discover_device(device_name)
    if (device != None):
        await read(device, char_uuid, dl24logger)
    else:
        raise Exception(f'No device with name {device_name} found')
    
asyncio.run(main())