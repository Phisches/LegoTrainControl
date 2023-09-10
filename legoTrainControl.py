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

speed1 = 2100
speed2 = 2500
speed3 = 2900

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
    
    @staticmethod
    def getBytesForColor(colorValue):
        port = 0x11
        mode = 0x00
        b = [0x00, 0x81, port, 0x01, 0x51, mode, colorValue]
        return b
    
class Sound():
    prep = [0x00, 0x41, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x01]
    sound2 = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 2] 
    brake = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 3]
    sound4 = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 4]
    station = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 5]
    sound6 = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 6]
    water = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 7]
    sound8 = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 8]
    horn = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 9]
    steam = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 10]
  
class Action():
    def __init__(self, the_bytes, pre_timer, post_timer):
        self.the_bytes = the_bytes
        self.pre_timer = pre_timer
        self.post_timer = post_timer
        
    def get_action():
        return self.the_bytes, self.pre_timer, self.post_timer
    
class Button():
    """Represents a button.
    Instance variables are
    @param pin: the GIO pin number of the button
    @param button_input: the configured GIO pin
    @param: state: 1 is pressed, 0 is depressed
    @param: name: a descriptive name that can be used in debug logs etc
    @param: sound that will be played
    @param: action_list: a list of actions that will be performed
    """
    #state = "pressed" #1 is pressed, 0 is depressed
    #pin = None #the pin of the esp
    #button_input = None
    
    def add_action(self, action):
        self.action_list.append(action)

    
    def __init__(self, pin, name, sound):
        self.pin = pin
        self.button_input = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)
        self.state = "pressed"  #1 is pressed, 0 is depressed
        self.name = name
        self.sound = sound
        self.action_list = []
  
class BreakButton(Button):
    def __init__(self, pin, name, sound):
        super().__init__(pin, name, sound)
    
    def activate_action():
        pass
        
        
    

class DuploTrainHub():
    """Duplo Steam train and Cargo Train
       This is hub is found in Lego sets 10874 and
    """
    
    connection = None
    service = None
    characteristic = None
    

    
    # color is set in the last byte
    #color = [0x00, 0x81, 0x11, 0x01, 0x51, 0x00, 0x05 ]
    
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
        self.uart_uuid = bluetooth.UUID('00001623-1212-efde-1623-785feabcd123')
        self.char_uuid = bluetooth.UUID('00001624-1212-efde-1623-785feabcd123')
        self.color = Color.getBytesForColor(Color.blue)
        self.light = True
        self.speed = 0
        self.direction = "forward"

async def find_ble(train):
    print("starting async call to scan ble")
    try:
        async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                if (result.name()  != None) and (result.name().find("Train") != -1):
                    print(result, result.name(), result.rssi, result.services())
                    return result.device
    except:
        machine.reset()
            
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
        except Exception():
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
    white_button = Button(WHITE_BUTTON_PIN, "light", Sound.steam)
    white_button.add_action(Action(Color.getBytesForColor(Color.white), 100, 100))
    blue_button = Button(BLUE_BUTTON_PIN, "water", Sound.water)
    yellow_button = Button(YELLOW_BUTTON_PIN, "horn", Sound.horn)
    red_button = Button(RED_BUTTON_PIN, "brake", Sound.brake)
    
    button_list = [white_button, blue_button, yellow_button, red_button]
    print(button_list)
    if my_characteristic is None:
        print("we didn't properly pair")
        machine.reset()
    await send_message_plus_length(my_characteristic, Sound.prep)
    while True:
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
                #print("the button state %s is %s" % (button.name, button.state))
        print(len(pressed_button_list))
        if len(pressed_button_list) == 1:
                await send_message_plus_length(my_characteristic, Sound.prep)
                #await asyncio.sleep_ms(150)
                print("I play the sound of button %s" % pressed_button_list[0].name)
                await send_message_plus_length(my_characteristic, pressed_button_list[0].sound)
                
                if pressed_button_list[0].name == "light":
                    print("check the lights...")
                    if train.light == True:
                        print("turn off lights")
                        await send_message_plus_length(my_characteristic, Color.getBytesForColor(Color.black))
                        train.light = False
                    elif train.light == False:
                        print("turn on lights")
                        await send_message_plus_length(my_characteristic, train.color)
                        #await send_message_plus_length(train.characteristic, Color.getBytesForColor(Color.white))
                        train.light = True
                        
                    
                        
        if len(pressed_button_list) == 2:
            print("two buttons pressed. Changing direction from %s to" % train.direction)
            #two buttons pressed, let's change train direction
            if train.direction.find("forward") > -1:
                train.direction = "reverse"
                print("reverse")
            else:
                train.direction = "forward"
                print("forward")
            
            await send_message_plus_length(train.characteristic, Color.getBytesForColor(Color.purple))
            await asyncio.sleep_ms(200)
            await send_message_plus_length(my_characteristic, Sound.prep)
            await asyncio.sleep_ms(250)
            #for sound_int in range(2,13):
            #    await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, sound_int])
            #    print(sound_int)
            #    time.sleep(3)
            await send_message_plus_length(my_characteristic, Sound.brake)
            await asyncio.sleep_ms(2000)
            
            await send_message_plus_length(my_characteristic, Sound.prep)
            await asyncio.sleep_ms(250)
            await send_message_plus_length(my_characteristic, Sound.steam)
               
        

            await asyncio.sleep_ms(600)
            await send_message_plus_length(my_characteristic, train.color)

            
        if len(pressed_button_list) == 4:
            print("Four buttons pressed... I restart")
            machine.reset()
        pressed_button_list = []
            
        await asyncio.sleep_ms(200)
    
        #max1280    
        if pot.read() >= speed3:
            #if train.speed == 3:
            #    continue
            if train.speed != 3:
                train.speed = 3
                print(f"Full speed: {train.speed} out of 3!")
            if train.direction == "forward":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x64])
            if train.direction == "reverse":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x9c])
        
        #medium 1987
        if pot.read() >= speed2 and pot.read() < speed3:
            #if train.speed == 2:
            #    continue
            if train.speed != 2:
                train.speed = 2
                print(f"Full speed: {train.speed} out of 3!")
            
            
            if train.direction == "forward":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x32])
            if train.direction == "reverse":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0xce])
            
            #await asyncio.sleep_ms(1500)
        if pot.read() >= speed1 and pot.read() < speed2:
            if train.speed != 1:
                train.speed = 1
                print(f"Full speed: {train.speed} out of 3!")
                
            #    continue
            
            if train.direction == "forward":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x1e])
            if train.direction == "reverse":
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0xe2])
        
        
        
        #min 70
        if pot.read() < speed1:
            if train.speed == 0:
                continue
            train.speed = 0
            print("Stop!")
            try:
                await send_message_plus_length(my_characteristic, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x00])
            except TypeError:
                machine.reset()
                
        #wait until we poll the pin states again  
        await asyncio.sleep_ms(350)

    #return my_characteristic
train = DuploTrainHub()
print(train)
asyncio.run(main())
sys.exit()

