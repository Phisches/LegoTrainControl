import sys

sys.path.append("")

from micropython import const

#import uuid
import uasyncio as asyncio
import aioble
import bluetooth
import hubs
import time
import machine

#from https://github.com/virantha/bricknil/blob/a908b98938ee1028373186e31cb2d43c68f54b76/bricknil/const.py#L25
class Color():
    """11 colors"""
    black = 0 
    pink = 1
    purple = 2
    blue = 3
    light_blue = 4
    cyan = 5
    green = 6
    yellow = 7
    orange = 8
    red = 9
    white = 10
    none = 255
    
class Sound():
    prep = [0x00, 0x41, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x01]
    horn = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 9]
    
    

class DuploTrainHub():
    """Duplo Steam train and Cargo Train
       This is hub is found in Lego sets 10874 and
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
    
    # color is set in the last byte
    color = [0x00, 0x81, 0x11, 0x01, 0x51, 0x00, 0x05 ]
    
    def setColor(self, value):
        """Value is from 0-11"""
        
        
        output = self.set_output(0x11, 0x00, value)
        self.color = output
        return output
        
    def set_output(self, port, mode, value):
        """Don't change this unless you're changing the way you do a Port Output command
        
           Outputs the following sequence to the sensor
            * 0x00 = hub id from common header
            * 0x81 = Port Output Command
            * port
            * 0x11 = Upper nibble (0=buffer, 1=immediate execution), Lower nibble (0=No ack, 1=command feedback)
            * 0x51 = WriteDirectModeData
            * mode
            * value(s)
        """
        b = [0x00, 0x81, port, 0x01, 0x51, mode, value ]
        return b
    async def send_message_plus_length(self, characteristic, msg):
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
        
        characteristic.write(values)
        
    
    
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
    values = bytearray(msg)
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
    
    BUTTON_PIN = 4
    
    CLW_PIN = 14
    CCW_PIN = 12
    
    clw_input = machine.Pin(CLW_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    ccw_input = machine.Pin(CCW_PIN, machine.Pin.IN, machine.Pin.PULL_UP)


    button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    await send_message_plus_length(my_characteristic, Sound.prep)
    while True:
        print(button.value())
        print("CLW Input %s" % clw_input.value())
        print("CCW Input %s" % ccw_input.value())

        if button.value() == 0:
            #await send_message_plus_length(my_characteristic, Sound.prep)
            await send_message_plus_length(my_characteristic, Sound.prep)
            await send_message_plus_length(my_characteristic, Sound.horn)
            
        if clw_input.value() == 0:
            print("can we start the motor? Speed 1 out of 3")
            await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x1e])
            
        if ccw_input.value() == 0:

            print("Stop!")
            await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x00])
            await asyncio.sleep_ms(1500)
           
            
        await asyncio.sleep_ms(500)

            
            

        
    
    
    
    
    
    

    
        
    
    #return my_characteristic
train = DuploTrainHub()
print(train)
asyncio.run(main())

