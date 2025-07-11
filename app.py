import asyncio
from bleak import BleakScanner, BleakClient
import logging
import json
import sys
import datetime
from collections import OrderedDict
import asyncclick as click
import rich
from rich.live import Live
from rich.table import Table

from bleak.backends.device import BLEDevice

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

# The bluetooth device name
#device_name = "DL24_BLE"
#device_name = "S1BP_BLE"
# The UUID of the characteristic to read - use ble-discovery.py to find it
char_uuid = '0000ffe1-0000-1000-8000-00805f9b34fb'

class DL24Logger:
    """ 
    Class for logging data from DL24 BLE device.
    """
    def __init__(self, format, device_name):
        self.format = format
        self.log_number = 0
        self.session_start = datetime.datetime.now()
        self.session_total_capacity = 0
        self.session_total_energy = 0
        self.last_read = datetime.datetime.now()
        self.live = None
        self.device_name = device_name
        
    def log(self, sender, data):
        """
    Log data from DL24 BLE device.

    This is the callback function that is called on every measurement
    """
        data_dict = OrderedDict()
        voltage = int.from_bytes(data[0x04:0x07], 'big', signed=False) / 10.0
        current = int.from_bytes(data[0x07:0x0a], 'big', signed=False)
        if (self.is_ac_meter(data)):
            power = int.from_bytes(data[0x0a:0x0d], 'big', signed=False) / 10.0
            capacity = -1
            self.session_total_capacity = -1
        else:
            power = voltage * current / 1000
            capacity = int.from_bytes(data[0x0a:0x0d], 'big', signed=False) * 10
            self.session_total_capacity = self.session_total_capacity + current / 3600

        resistance = -1
        if (voltage > 0 and current > 0):
            resistance = voltage / (current/1000)
        energy = int.from_bytes(data[0x0d:0x11]) * 10
        temperature = int.from_bytes(data[0x18:0x1a], 'big', signed=False)

        frequency = -1
        power_factor = -1
        if (self.is_ac_meter(data)):
            frequency = int.from_bytes(data[0x14:0x16], 'big', signed=False) / 10.0
            power_factor = int.from_bytes(data[0x16:0x18], 'big', signed=False) / 1000.0

        # Capacity in mAh on the basis of 1-second updates
        self.session_total_energy = self.session_total_energy + power / 3600

        data_dict['timestamp'] = datetime.datetime.now().isoformat()
        data_dict['voltage_V'] = voltage 
        data_dict['current_mA'] = current
        data_dict['power_W'] = f'{power:.2f}'
        data_dict['resistance_Ohm'] = f'{resistance:.2f}'
        data_dict['capacity_mAh'] = capacity
        data_dict['energy_Wh'] = energy
        data_dict['frequency_Hz'] = frequency
        data_dict['power_factor'] = power_factor
        data_dict['session_total_capacity_mAh'] = f'{self.session_total_capacity:.2f}'
        data_dict['session_total_energy_Wh'] = f'{self.session_total_energy:.2f}'

        data_dict['temperature_C'] = temperature

        if (self.format == 'csv'):
            self.csv(data_dict)
        elif (self.format == 'json'):
            self.json(data_dict)
        elif (self.format == 'table'):
            self.table(data_dict, self.is_ac_meter(data))
        else:
            self.raw(data, True)

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

    def raw(self, data_dict, pretty):
        if self.format == 'raw-decimal':
            formatter = '{:02d}'
        else:
            formatter = '{:02x}'

        if pretty:
            formatter = formatter + ' '

        data_raw = (''.join(formatter.format(x) for x in data_dict))
        
        print(data_raw)

    def table(self, data_dict, is_ac_meter):
        if self.live is None:
            raise Exception("Live is not initialized - this should not be possible and must be fixed")
        self.live.update(self.generate_table(data_dict, is_ac_meter))
    
    def generate_table(self, data_dict, is_ac_meter):
        table = Table(title=self.device_name)
        table.add_column("voltage_V", justify="right", style="blue")
        table.add_column("current_mA", justify="right", style="red")
        table.add_column("power_W", justify="right", style="yellow")
        table.add_column("energy_Wh", justify="right", style="red")
        if (is_ac_meter):
            table.add_column("frequency_Hz", justify="right", style="blue")
            table.add_column("power_factor", justify="right", style="red")
        else:
            table.add_column("capacity_mAh", justify="right", style="blue")
            table.add_column("session_total_capacity_mAh", justify="right", style="yellow")
        table.add_column("session_total_energy_Wh", justify="right", style="green")

        if data_dict is None:
            return table
        
        row = []
        for col in table.columns:
            row.append(str(data_dict[col.header]))

        table.add_row(*row) 

        return table
        
    def is_ac_meter(self, data):
        return data[0x03] == 0x01

async def discover_device(device_name) -> BLEDevice:
    """ 
    Discover DL24 BLE device given the name of the device
    """
    retries = 0
    while (retries < 5):
        devices = await BleakScanner.discover()
        for d in devices:
            logger.debug(f'Device {d.name} discovered')
            if (d is not None and d.name is not None and d.name.find(device_name) >= 0):
                return d
        retries += 1
        await asyncio.sleep(5)
    raise Exception(f'No device with name {device_name} found')

async def read(device, char_uuid, dl24logger, live):
    """ 
    Read data from DL24 BLE device given the device and the UUID of the characteristic
    """
    async with BleakClient(
        device,
        pair=False,
        timeout=60
    ) as client:
        logger.info("connected")

        dl24logger.live = live

        await client.start_notify(char_uuid, dl24logger.log)
        while (True):
            await asyncio.sleep(1)
            if (datetime.datetime.now() - dl24logger.last_read).total_seconds() > 30:
                raise Exception("No data received for 30 seconds")

@click.command()
@click.argument('format', required=True, type=click.Choice(['csv', 'json', 'raw', 'raw-decimal', 'table']))
@click.option('--debug', '-d', is_flag=True)
@click.option('--devicename', '-dn', default='DL24_BLE')
async def main(format, debug, devicename):
    dl24logger = DL24Logger(format, devicename)
    device = await discover_device(devicename)
    if (device != None):
        if (format == 'table'):
            with Live(refresh_per_second=4) as live:
                await read(device, char_uuid, dl24logger, live)
        else:
            await read(device, char_uuid, dl24logger, None)
    else:
        raise Exception(f'No device with name {devicename} found')
    
asyncio.run(main())