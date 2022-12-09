import sys

sys.path.append("")

from micropython import const

#import uuid
import uasyncio as asyncio
import aioble
import bluetooth
import hubs
import time

class DuploTrainHub():
    """Duplo Steam train and Cargo Train
       This is hub is found in Lego sets 10874 and 10875
    """
    
    connection = None
    service = None
    characteristic = None
    
    prep = bytearray([0x0a, 0x00, 0x41, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x01])
    horn_send = bytearray([0x08, 0x00, 0x81, 0x01, 0x11, 0x51, 0x01, 0x09])
    motor = bytearray([0x08, 0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x00])
    motor2 = bytearray([0x08, 0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x1e])
    
    b = [0x00, 0x41, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x01]
    b2 = [0x08, 0x00, 0x81, 0x01, 0x11, 0x51, 0x01, 0x09]
    
    color = [0x00, 0x81, 0x11, 0x01, 0x51, 0x00, 0x05 ]
    
    def __init__(self, query_port_info=False, ble_id=None):
        
        self.ble_name = 'Train Base'
        self.manufacturer_id = 32
        #self.uart_uuid = uuid.UUID('00001623-1212-efde-1623-785feabcd123')
        self.uart_uuid = bluetooth.UUID('00001623-1212-efde-1623-785feabcd123')
        #self.char_uuid = uuid.UUID('00001624-1212-efde-1623-785feabcd123')
        self.char_uuid = bluetooth.UUID('00001624-1212-efde-1623-785feabcd123')

async def find_ble(train):
    print("starting async call to scan ble")
    async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            if (result.name()  != None) and (result.name().find("Train") != -1):
                print(result, result.name(), result.rssi, result.services())
                return result.device
            
async def send_message_plus_length(characteristic, msg):
    """Prepends a byte with the length of the msg and writes it to
       the characteristic
       Arguments:
          characteristic : An object from bluefruit, or if using Bleak,
              a tuple (device, uuid : str)
          msg (bytearray) : Message with header
    """
    # Message needs to have length prepended
    length = len(msg)+1
    values = bytearray([length]+msg)

    
    await characteristic.write(values)
    
async def send_message_no_length(characterstic, msg):
    values = bytearray([msg])
    await characterstic.write(values)
                
async def main():
    device = await find_ble(train)
    if not device:
        print("no ble device found")
        return



    my_characteristic = None
    
    i = 0
    while my_characteristic == None and i < 10:
        try:
            print("Connecting to", device)
            connection = await device.connect(timeout_ms=2000)
        except asyncio.TimeoutError:
            print("Timeout during connection")
            
        print(connection)
        train.connection = connection
        i = i + 1
        try: 
            my_service = await connection.service(train.uart_uuid)
            print(my_service)
        except:
            print("no shirt, no service!")
            continue
        train.service = my_service
        
        try:
            my_characteristic = await my_service.characteristic(train.char_uuid)
        except:
            print("no characteristics")
            continue
        train.characteristic = my_characteristic
        data = await my_characteristic.subscribe(notify=True)
        print (data)
    print(my_characteristic)
    
    #await send_message_plus_length(my_characteristic, train.b)
    
    
    
    
    
    prep = bytearray([0x0a, 0x00, 0x41, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x01])
    horn_send = bytearray([0x08, 0x00, 0x81, 0x01, 0x11, 0x51, 0x01, 0x09])
    motor = bytearray([0x08, 0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x00])
    motor2 = bytearray([0x08, 0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x1e])
    res = await my_characteristic.write(prep)
    print(res)
    #await my_characteristic.read(timeout_ms=1000)
    
    res = await my_characteristic.write(horn_send)
    print(res)
    await asyncio.sleep_ms(5000)
    
    await send_message_plus_length(my_characteristic, train.color)
    await asyncio.sleep_ms(4000)
    await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x11, 0x01, 0x51, 0x00, 0x0a])
    
    #return my_characteristic
train = DuploTrainHub()
print(train)
asyncio.run(main())
