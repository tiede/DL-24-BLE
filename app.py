import asyncio
from bleak import BleakScanner, BleakClient
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
device_name = "DL24_BLE"

def callback(sender, data):
    print(', '.join('{:02d}'.format(x) for x in data))

async def main():
    device = None
    while (device == None):
        devices = await BleakScanner.discover()
        for d in devices:
            logger.debug(f'Device {d.name} discovered')
            if (d.name.find(device_name) >= 0):
                device = d

    if (device == None):
        raise Exception(f'No device with name {device_name} found')
    
    async with BleakClient(
        device,
        pair=True,
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

                # for descriptor in char.descriptors:
                #     try:
                #         value = await client.read_gatt_descriptor(descriptor.handle)
                #         logger.info("    [Descriptor] %s, Value: %r", descriptor, value)
                #     except Exception as e:
                #         logger.error("    [Descriptor] %s, Error: %s", descriptor, e)

        char_uuid = '0000ffe1-0000-1000-8000-00805f9b34fb'

        #characteristic = client.
        await client.start_notify(char_uuid, callback)
        while (True):
            await asyncio.sleep(1)

        logger.info("disconnecting...")

    logger.info("disconnected")
    

#loop = asyncio.get_event_loop()
#loop.set_debug(True)
#loop.run_until_complete(main())'

asyncio.run(main())

# from bleak import BleakClient

# address = "65:F8:C4:AE:A3:BF"
# MODEL_NBR_UUID = "2A24"

# async def main(address):
#      async with BleakClient(address) as client:
#          model_number = await client.read_gatt_char(MODEL_NBR_UUID)
#          print("Model Number: {0}".format("".join(map(chr, model_number))))

# asyncio.run(main(address))