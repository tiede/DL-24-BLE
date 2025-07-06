import asyncio
from bleak import BleakScanner, BleakClient
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

#device_name = "DL24_BLE"
device_name = "S1BP_BLE"
device = None

async def discover_device(device_name):
    while (True):
        devices = await BleakScanner.discover()
        for d in devices:
            logger.debug(f'Device {d.name} discovered')
            if (d is not None and d.name is not None and d.name.find(device_name) >= 0):
                return d

async def discover_devices():
    while (True):
        devices = await BleakScanner.discover()
        for d in devices:
            logger.info(f'Device {d.name} discovered')

async def explore_device(device):
    async with BleakClient(
        device,
        pair=False,
        timeout=60
    ) as client:
        logger.info("connected")

        if (len(client.services.services) < 1):
             raise Exception(f'No services for device {device_name}')

        for service in client.services:
            logger.info("[Service] %s", service)

            # if (len(service.characteristics) < 1):
            #     raise Exception(f'No characteristics for service {service.uuid}')

            for char in service.characteristics:
                #await client.start_notify(char.uuid, callback)
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        extra = f", Value: {value}"
                    except Exception as e:
                        extra = f", Error: {e}"
                else:
                    extra = ""

                if "write-without-response" in char.properties:
                    extra += f", Max write w/o rsp size: {char.max_write_without_response_size}"

                logger.info(
                    "  [Characteristic] %s (%s)%s",
                    char,
                    ",".join(char.properties),
                    extra,
                )

                for descriptor in char.descriptors:
                    try:
                        value = await client.read_gatt_descriptor(descriptor.handle)
                        logger.info("    [Descriptor] %s, Value: %r", descriptor, value)
                    except Exception as e:
                        logger.error("    [Descriptor] %s, Error: %s", descriptor, e)

        logger.info("disconnecting...")

    logger.info("disconnected")

async def main():
    #await discover_devices()
    device = await discover_device(device_name)
    
    if (device != None):
        await explore_device(device)
    else:
        raise Exception(f'No device with name {device_name} found')
    
asyncio.run(main())