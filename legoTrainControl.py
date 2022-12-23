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
    water = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 7]
    brake = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 3]
    station = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 5]
    steam = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 10]
    
class Button():
    #state = "pressed" #1 is pressed, 0 is depressed
    #pin = None #the pin of the esp
    #button_input = None

    
    def __init__(self, pin, name, sound):
        self.pin = pin
        self.button_input = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)
        self.state = "pressed"  #1 is pressed, 0 is depressed
        self.name = name
        self.sound = sound
    
    

class DuploTrainHub():
    """Duplo Steam train and Cargo Train
       This is hub is found in Lego sets 10874 and
    """
    
    connection = None
    service = None
    characteristic = None
    

    
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
        
        self.direction = "forward"

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
    
    device = None
    while device is None:
        #await aioble.cancel()
        device = await find_ble(train)
        if not device:
            print("no ble device found")
    #        print("press button to try again")
    #    return



    my_characteristic = None
    
    i = 0
    while my_characteristic == None and i < 10:
        try:
            print("Connecting to", device)
            try:
                connection = await device.connect(timeout_ms=2000)
            except OSError:
                machine.reset()
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
    
    WHITE_BUTTON_PIN = 4
    RED_BUTTON_PIN = 18
    BLUE_BUTTON_PIN = 19
    YELLOW_BUTTON_PIN = 21
    

    POT_PIN = 32
    

    pot = machine.ADC(machine.Pin(POT_PIN))
    pot.atten(machine.ADC.ATTN_11DB)


    #button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    horn_button = Button(WHITE_BUTTON_PIN, "horn", Sound.horn)
    blue_button = Button(BLUE_BUTTON_PIN, "water", Sound.water)
    yellow_button = Button(YELLOW_BUTTON_PIN, "steam", Sound.steam)
    red_button = Button(RED_BUTTON_PIN, "brake", Sound.brake)
    
    button_list = [horn_button, blue_button, yellow_button, red_button]
    print(button_list)
    
    await send_message_plus_length(my_characteristic, Sound.prep)
    while True:
        #print(horn_button.button_input.value())
        #print("CLW Input %s" % clw_button.button_input.value())
        #print("CCW Input %s" % ccw_button.button_input.value())
        print("Pot Input %s" % pot.read())
        
        pressed_button_list =[]
        
        for button in button_list:
            
            if button.button_input.value() == 0: #this means the button was pressed
                print("input = 0, the button %s state is %s" % (button.name, button.state))
                if button.state == "unpressed": # so the button was open previously, else someone else is still
                                                # pressing the same button and we continue until the finger
                                                # is lifted
                    button.state = "pressed"
                    print("I have set the button %s state to pressed? -> %s" % (button.name, button.state))
                    pressed_button_list.append(button)

            if button.button_input.value() == 1:
            
                button.state = "unpressed"
                print("the button state %s is %s" % (button.name, button.state))
        print(len(pressed_button_list))
        if len(pressed_button_list) == 1:
                await send_message_plus_length(my_characteristic, Sound.prep)
                await asyncio.sleep_ms(100)
                await send_message_plus_length(my_characteristic, button.sound)
        if len(pressed_button_list) == 2:
            print("two buttons pressed. Changing direction from %s to" % train.direction)
            #two buttons pressed, let's change train direction
            if train.direction.find("forward") > -1:
                train.direction = "reverse"
                print("reverse")
            else:
                train.direction = "forward"
                print("forward")
        pressed_button_list = []
            
                    
                
            
            
        #max2377    
        if pot.read() >= 2000:
            print("Full setting: 3 out of 3!")
            if train.direction == "forward":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x64])
            if train.direction == "reverse":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x9c])
        
        #medium 1987
        if pot.read() >= 1700 and pot.read() < 2000:

            
            print("Speed setting: 2 out of 3!")
            if train.direction == "forward":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x32])
            if train.direction == "reverse":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0xce])
            
            await asyncio.sleep_ms(1500)
        if pot.read() >= 1300 and pot.read() < 1700:
            print("can we start the motor? Speed 1 out of 3")
            if train.direction == "forward":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x1e])
            if train.direction == "reverse":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0xe2])
        
        
        #min 1184
        if pot.read() < 1300:
            print("Stop!")
            try:
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x00])
            except TypeError:
                machine.reset()
                
           
            
        await asyncio.sleep_ms(300)

            
            

        
    
    
    
    
    
    

    
        
    
    #return my_characteristic
train = DuploTrainHub()
print(train)
asyncio.run(main())
sys.exit()

