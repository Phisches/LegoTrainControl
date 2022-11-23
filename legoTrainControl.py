import sys

sys.path.append("")

from micropython import const

#import uuid
import uasyncio as asyncio
import aioble
import bluetooth
import hubs

class DuploTrainHub():
    """Duplo Steam train and Cargo Train
       This is hub is found in Lego sets 10874 and 10875
    """
    def __init__(self, query_port_info=False, ble_id=None):
        
        self.ble_name = 'Train Base'
        self.manufacturer_id = 32
        #self.uart_uuid = uuid.UUID('00001623-1212-efde-1623-785feabcd123')
        self.uart_uuid = '00001623-1212-efde-1623-785feabcd123'
        #self.char_uuid = uuid.UUID('00001624-1212-efde-1623-785feabcd123')
        self.char_uuid = '00001624-1212-efde-1623-785feabcd123'

async def find_ble(train):
    print("starting async call to scan ble")
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            if (result.name()  != None) and (result.name().find("Train") != -1):
                print(result, result.name(), result.rssi, result.services())
                return result.device
                
async def main():
    device = await find_ble(train)
    if not device:
        print("no ble device found")
        return

    try:
        print("Connecting to", device)
        connection = await device.connect()
    except asyncio.TimeoutError:
        print("Timeout during connection")
        return

train = DuploTrainHub()
print(train)
asyncio.run(main())
