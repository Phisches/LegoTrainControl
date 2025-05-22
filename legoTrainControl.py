"""
legoTrainControl.py

Controls a LEGO Duplo Train (Sets 10874/10875) using a Raspberry Pi Pico W (RP2040)
and MicroPython. 
Features:
- Connects to the train via Bluetooth Low Energy (BLE).
- Controls train speed using a potentiometer.
- Handles button inputs for various actions:
    - Single button press: Plays a sound and toggles the train's light.
    - Double button press: Changes train direction.
    - Four button press: Resets the microcontroller.
- Manages train light color and state.

The script uses uasyncio for asynchronous operations, primarily for BLE communication
and handling inputs.
"""
import sys

sys.path.append("")

from micropython import const

#import uuid # Not currently used
import uasyncio as asyncio
import aioble
import bluetooth
import hubs # LEGO Hub specific library
import time # For delays, though asyncio.sleep_ms is preferred for async operations
import machine

# --- Pin Definitions ---
WHITE_BUTTON_PIN = const(4)
RED_BUTTON_PIN = const(18)
BLUE_BUTTON_PIN = const(19)
YELLOW_BUTTON_PIN = const(21)
POT_PIN = const(32) # Potentiometer Pin

# --- Global Constants ---
SPEED_THRESHOLDS = {'low': 2100, 'medium': 2500, 'high': 2900} # Potentiometer thresholds for speed levels

# Motor Command Bytes (Port 0x00, Mode 0x00 for motor control)
# Structure: [Hub ID, Command Type, Port, Feedback/Execution, Mode, Value(s)]
CMD_MOTOR_STOP = [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x00]
CMD_MOTOR_FORWARD_SPEED_1 = [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x1e]
CMD_MOTOR_FORWARD_SPEED_2 = [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x32]
CMD_MOTOR_FORWARD_SPEED_3 = [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x64]
CMD_MOTOR_REVERSE_SPEED_1 = [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0xe2]
CMD_MOTOR_REVERSE_SPEED_2 = [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0xce]
CMD_MOTOR_REVERSE_SPEED_3 = [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x9c]


#from https://github.com/virantha/bricknil/blob/a908b98938ee1028373186e31cb2d43c68f54b76/bricknil/const.py#L25
class Color:
    """
    Represents the 11 available colors for the train's LED.
    Provides a method to generate the byte command for setting a color.
    """
    BLACK = 0
    PINK = 1
    PURPLE = 2
    BLUE = 3
    LIGHT_BLUE = 4
    CYAN = 5
    GREEN = 6
    YELLOW = 7
    ORANGE = 8
    RED = 9
    WHITE = 10
    NONE = 255
    
    @staticmethod
    def getBytesForColor(colorValue):
        """
        Generates the byte command to set the train's LED to a specific color.
        Args:
            colorValue (int): The integer value representing the color (e.g., Color.BLUE).
        Returns:
            list[int]: The byte array command for setting the color.
        """
        port = 0x11 # Port for LED control on the Duplo train hub
        mode = 0x00 # Mode for direct color setting
        # Structure: [Hub ID, Command Type, Port, Feedback/Execution, Command, Mode, Value]
        b = [0x00, 0x81, port, 0x01, 0x51, mode, colorValue]
        return b
    
class Sound:
    """
    Container for various sound byte commands that can be sent to the train.
    Sound commands are sent to Port 0x01, Mode 0x01.
    """
    # This command is sent before playing many sounds. Its exact function is
    # not fully documented but seems to prepare or enable the sound system on the hub.
    # Structure might be [Hub ID, Command Type, Port, Feedback/Execution, SubCommand?, Parameters...]
    PREPARE_SOUND = [0x00, 0x41, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x01] 
    SOUND_BRAKE = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 3]
    SOUND_STATION_DEPART = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 5] # Station announcement sound
    SOUND_WATER_REFILL = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 7] # Water refilling
    SOUND_HORN = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 9]
    SOUND_STEAM = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 10]
    # Generic sounds, keep if specific names aren't clear or for variety
    SOUND_2 = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 2] 
    SOUND_4 = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 4]
    SOUND_6 = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 6]
    SOUND_8 = [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 8]

  
class Action:
    """
    Represents an action to be performed, typically involving sending bytes to the train.
    Currently used to associate a byte command with pre and post delay timers for potential future use,
    though timers are not actively used in the current button implementation.
    The `action_list` on a Button object can hold these Action instances.
    """
    def __init__(self, the_bytes, pre_timer, post_timer):
        """
        Initializes an Action instance.
        Args:
            the_bytes (list[int]): The byte command associated with this action.
            pre_timer (int): Delay in milliseconds before the action (currently unused).
            post_timer (int): Delay in milliseconds after the action (currently unused).
        """
        self.the_bytes = the_bytes
        self.pre_timer = pre_timer 
        self.post_timer = post_timer
    
class Button:
    """
    Represents a physical button connected to a GPIO pin.
    Instance variables are:
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
        """
        Initializes a Button instance.
        Args:
            pin (int): The GPIO pin number the button is connected to (using Pin Definitions at top).
            name (str): A descriptive name for the button (e.g., "light", "horn").
            sound (list[int]): The sound byte array (from Sound class) to be played when this button is pressed.
        """
        self.pin = pin
        self.button_input = machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)
        self.state = "unpressed"  # Initial state: "unpressed" or "pressed"
        self.name = name
        self.sound = sound # Sound command to play
        self.action_list = [] # List of Action objects associated with this button
  
class BreakButton(Button):
    """
    A specialized button for break actions. Currently a placeholder.
    Inherits from Button.
    """
    def __init__(self, pin, name, sound):
        super().__init__(pin, name, sound)
    
    def activate_action(self):
        # TODO: Implement specific break action for this button if needed,
        # or remove this class if it remains unused in favor of generic Button handling.
        pass
        
        
    

class DuploTrainHub:
    """
    Represents the LEGO Duplo Train Hub (e.g., from sets 10874, 10875).
    Manages BLE connection details, train state (speed, direction, light color),
    and provides methods for interacting with the train.
    """
    
    connection = None
    service = None
    characteristic = None
    

    
    # color is set in the last byte
    #color = [0x00, 0x81, 0x11, 0x01, 0x51, 0x00, 0x05 ]
    
    def setColor(self, color_value):
        """Sets and stores the train's intended light color value.
           color_value should be one of the constants from the Color class.
        """
        self.color_value = color_value
        print(f"Train's intended light color value set to: {self.color_value}")
        # Note: This method only updates the state.
        # Actually changing the light on the train happens in response to button presses, etc.
        
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
    # Removed synchronous send_message_plus_length method
    
    
    def __init__(self, query_port_info=False, ble_id=None):
        """
        Initializes the DuploTrainHub instance.
        Args:
            query_port_info (bool): If true, would theoretically query port info (not implemented).
            ble_id (str, optional): Specific BLE address to connect to (not currently used by find_ble_device).
        """
        self.ble_name = 'Train Base' # Expected BLE name of the Duplo train hub
        self.manufacturer_id = 32 # LEGO's manufacturer ID for BLE
        self.uart_uuid = bluetooth.UUID('00001623-1212-efde-1623-785feabcd123') # LEGO Wireless Protocol Service UUID
        self.char_uuid = bluetooth.UUID('00001624-1212-efde-1623-785feabcd123') # LEGO Wireless Protocol Characteristic UUID
        
        # Connection state attributes, initialized to None
        self.connection = None
        self.service = None
        self.characteristic = None
        
        self.color_value = Color.BLUE # Default LED color value
        self.light = True # Initial state of the light (on/off)
        self.speed = 0 # Initial speed level (0-3)
        self.direction = "forward" # Initial direction: "forward" or "reverse"

async def find_ble_device():
    """
    Scans for a BLE device with 'Train' in its name.
    Returns:
        aioble.Device: The found device, or None if not found or an error occurred.
    """
    print("Starting BLE scan for train...")
    try:
        async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                if result.name() and "Train" in result.name():
                    print(f"Found: {result.name()} ({result.device}) RSSI: {result.rssi}")
                    return result.device
    except Exception as e:
        print(f"Error during BLE scan: {e}")
    return None

async def connect_to_train(train_hub):
    """
    Connects to the specified Duplo Train hub via BLE.
    Handles scanning, connection, service and characteristic discovery, and subscription.
    Args:
        train_hub (DuploTrainHub): The train hub instance to configure with connection details.
    Returns:
        bool: True if connection and setup were successful, False otherwise.
    """
    print("Attempting to connect to the train...")
    device = None
    while device is None: # Loop until a device is found
        device = await find_ble_device()
        if not device:
            print("No BLE device found matching 'Train'. Retrying scan in 2 seconds...")
            await asyncio.sleep_ms(2000) 

    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            print(f"Connecting to {device} (Attempt {attempt + 1}/{max_attempts})")
            # Increased timeout for connection to potentially more robustly handle pairing
            connection = await device.connect(timeout_ms=10000) 
            train_hub.connection = connection
            print("Connected.")
            
            print("Discovering UART service...")
            train_hub.service = await connection.service(train_hub.uart_uuid)
            print(f"Service discovered: {train_hub.service}")

            print("Discovering characteristic...")
            train_hub.characteristic = await train_hub.service.characteristic(train_hub.char_uuid)
            print(f"Characteristic discovered: {train_hub.characteristic}")

            print("Subscribing to characteristic notifications...")
            await train_hub.characteristic.subscribe(notify=True)
            print("Subscription successful.")
            return True # Connection and setup fully successful

        except asyncio.TimeoutError:
            print("Timeout during connection or discovery phase.")
        except OSError as e:
            print(f"OSError during connection/discovery: {e}")
        except Exception as e: # Catch any other unexpected errors during connection
            print(f"An unexpected error occurred during connection: {e}")
        
        if train_hub.connection: # If connection was made but a later step failed
            try:
                await train_hub.connection.disconnect()
                print("Disconnected due to error in setup sequence.")
            except Exception as e:
                print(f"Error during disconnect: {e}")
        
        print("Retrying connection in 1 second...")
        await asyncio.sleep_ms(1000) 

    print("Failed to connect and setup BLE characteristic after multiple attempts.")
    return False

async def send_message_plus_length(characteristic, msg):
    """
    Prepends a byte with the length of the message and writes it to the characteristic.
    This is the standard way to send commands to LEGO hubs.
    Args:
        characteristic: The BLE characteristic to write to.
        msg (list[int] or bytearray): The message/command to send.
    """
    length = len(msg) + 1 # Total length including the length byte itself
    values = bytearray([length] + msg)
    try:
        await characteristic.write(values)
    except Exception as e:
        print(f"Error writing message with length: {e}")
        # Consider re-raising or specific error handling if machine reset is too drastic
        # machine.reset() 

async def send_message_no_length(characteristic, msg): # Renamed for clarity
    """
    Sends a message to the characteristic without prepending its length.
    Used for specific commands that don't require the length prefix (if any).
    Args:
        characteristic: The BLE characteristic to write to.
        msg (list[int] or bytearray): The message/command to send.
    """
    values = bytearray(msg)
    try:
        await characteristic.write(values)
    except Exception as e:
        print(f"Error writing message without length: {e}")

def initialize_buttons():
    """
    Initializes all buttons used in the application using global Pin Definitions.
    Returns:
        list[Button]: A list of initialized Button objects.
    """
    # Pin definitions (WHITE_BUTTON_PIN, etc.) are global constants at the top of the script.
    white_button = Button(WHITE_BUTTON_PIN, "light", Sound.SOUND_STEAM)
    # Example action for white button, can be expanded or managed differently if Action class evolves.
    white_button.add_action(Action(Color.getBytesForColor(Color.WHITE), 100, 100)) 
    blue_button = Button(BLUE_BUTTON_PIN, "water", Sound.SOUND_WATER_REFILL)
    yellow_button = Button(YELLOW_BUTTON_PIN, "horn", Sound.SOUND_HORN)
    red_button = Button(RED_BUTTON_PIN, "brake", Sound.SOUND_BRAKE)
    
    button_list = [white_button, blue_button, yellow_button, red_button]
    print("Buttons initialized:", [btn.name for btn in button_list])
    return button_list

async def handle_button_inputs(button_list, train_hub, characteristic):
    """
    Checks the state of each button and performs actions based on button presses.
    - Single press: Plays sound, toggles light.
    - Double press: Changes train direction.
    - Quadruple press: Resets the system.
    Args:
        button_list (list[Button]): The list of button objects.
        train_hub (DuploTrainHub): The train hub instance.
        characteristic: The BLE characteristic for sending commands.
    """
    pressed_button_list = []
    for button in button_list:
        if button.button_input.value() == 0: # Button pressed (pin pulled low)
            if button.state == "unpressed":
                button.state = "pressed"
                print(f"Button {button.name} pressed.")
                pressed_button_list.append(button)
        else: # Button not pressed (pin is high)
            if button.state == "pressed":
                print(f"Button {button.name} released.")
                button.state = "unpressed"

    num_pressed = len(pressed_button_list)

    if num_pressed == 1:
        button = pressed_button_list[0]
        print(f"Single button press: {button.name}")
        await send_message_plus_length(characteristic, Sound.PREPARE_SOUND)
        await asyncio.sleep_ms(50) # Short delay after sound prep, seems beneficial
        await send_message_plus_length(characteristic, button.sound)
        
        if button.name == "light": # Specific action for the "light" button
            if train_hub.light:
                print("Turning off light.")
                await send_message_plus_length(characteristic, Color.getBytesForColor(Color.BLACK))
                train_hub.light = False
            else:
                print(f"Turning on light to color: {train_hub.color_value}") 
                await send_message_plus_length(characteristic, Color.getBytesForColor(train_hub.color_value))
                train_hub.light = True
    
    elif num_pressed == 2:
        print("Two buttons pressed. Changing direction.")
        train_hub.direction = "reverse" if "forward" in train_hub.direction else "forward"
        print(f"Train direction set to: {train_hub.direction}")
        
        await send_message_plus_length(characteristic, Color.getBytesForColor(Color.PURPLE)) # Indicate direction change with purple light
        await asyncio.sleep_ms(200)
        await send_message_plus_length(characteristic, Sound.PREPARE_SOUND)
        await asyncio.sleep_ms(250)
        await send_message_plus_length(characteristic, Sound.SOUND_BRAKE)
        await asyncio.sleep_ms(1000) # Allow brake sound to play
        await send_message_plus_length(characteristic, Sound.PREPARE_SOUND)
        await asyncio.sleep_ms(250)
        await send_message_plus_length(characteristic, Sound.SOUND_STEAM) # Steam sound for departure
        await asyncio.sleep_ms(600)
        
        # Restore light to its previous state or the train's set color
        light_cmd = Color.getBytesForColor(train_hub.color_value) if train_hub.light else Color.getBytesForColor(Color.BLACK)
        await send_message_plus_length(characteristic, light_cmd)

    elif num_pressed == 4:
        print("Four buttons pressed. Restarting machine.")
        machine.reset() # System reset

    if num_pressed > 0: # If any button press was processed
        await asyncio.sleep_ms(200) # Debounce/cool-down period after processing presses


async def handle_speed_control(pot, train_hub, characteristic, speed_thresholds_map):
    """
    Reads the potentiometer value and adjusts the train's speed accordingly.
    Sends motor commands only when the target speed level changes.
    Args:
        pot (machine.ADC): The ADC object for the potentiometer.
        train_hub (DuploTrainHub): The train hub instance.
        characteristic: The BLE characteristic for sending motor commands.
        speed_thresholds_map (dict): Mapping of speed levels ('low', 'medium', 'high') to potentiometer thresholds.
    """
    current_pot_value = pot.read()
    new_speed_level = 0 # Default to stopped

    if current_pot_value >= speed_thresholds_map['high']:
        new_speed_level = 3
    elif current_pot_value >= speed_thresholds_map['medium']:
        new_speed_level = 2
    elif current_pot_value >= speed_thresholds_map['low']:
        new_speed_level = 1
    # else: new_speed_level remains 0 (stopped)

    if new_speed_level != train_hub.speed: # Only act if the desired speed level has changed
        train_hub.speed = new_speed_level
        print(f"Speed changed to level: {train_hub.speed}/3")
        
        command = CMD_MOTOR_STOP # Default to stop
        if train_hub.speed == 3:
            command = CMD_MOTOR_FORWARD_SPEED_3 if train_hub.direction == "forward" else CMD_MOTOR_REVERSE_SPEED_3
        elif train_hub.speed == 2:
            command = CMD_MOTOR_FORWARD_SPEED_2 if train_hub.direction == "forward" else CMD_MOTOR_REVERSE_SPEED_2
        elif train_hub.speed == 1:
            command = CMD_MOTOR_FORWARD_SPEED_1 if train_hub.direction == "forward" else CMD_MOTOR_REVERSE_SPEED_1
        
        await send_message_plus_length(characteristic, command)
    
    await asyncio.sleep_ms(350) # Polling interval for speed control

                
async def main():
    """
    Main asynchronous function to run the train control system.
    Initializes hardware, connects to the train, and enters the main control loop.
    """
    global train # Access the global train hub instance, created at script start
    
    print(f"Train hub initialized: {train.ble_name}")

    if not await connect_to_train(train):
        print("Failed to connect to the train. Halting program.")
        # Consider a more robust error state, e.g., blinking an LED on the Pico
        return # Exit main if connection fails

    # Use the characteristic from the successfully connected train object
    my_characteristic = train.characteristic 
    # This check should ideally not be needed if connect_to_train ensures it or raises an error
    if my_characteristic is None: 
        print("Characteristic not available after connection attempt. Halting.")
        return 

    # Initialize Potentiometer (using global POT_PIN)
    pot = machine.ADC(machine.Pin(POT_PIN))
    pot.atten(machine.ADC.ATTN_11DB) # Set attenuation for full 0-3.3V range on ADC pin

    button_list = initialize_buttons()
    
    # Send initial sound preparation command once after connection
    await send_message_plus_length(my_characteristic, Sound.PREPARE_SOUND)
    await asyncio.sleep_ms(100) # Small delay after initial sound prep

    print("Main control loop starting...")
    while True:
        try:
            await handle_button_inputs(button_list, train, my_characteristic)
            await handle_speed_control(pot, train, my_characteristic, SPEED_THRESHOLDS)
            # Main loop sleeps are handled within the respective handler functions.
            # A minimal global sleep here (e.g., 10-50ms) could be added if handlers could return too quickly
            # and cause a very tight loop, but current sleeps within handlers should suffice.
            # await asyncio.sleep_ms(10) 
        except Exception as e:
            print(f"Error in main loop: {e}")
            # Decide on recovery strategy: re-throw, reset, or try to continue
            # For now, just printing and continuing. A more robust system might try to reconnect.
            # machine.reset() # Or await connect_to_train(train) again?

# --- Script Execution ---
if __name__ == "__main__":
    train = DuploTrainHub() # Create the global train hub instance
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program stopped by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"Unhandled exception in asyncio.run(main()): {e}")
    finally:
        # Cleanup actions if needed.
        # Note: Reliable BLE disconnect in MicroPython aioble can be tricky,
        # especially after errors or KeyboardInterrupt.
        # `train.connection.disconnect()` might not always work as expected or be available.
        if hasattr(train, 'connection') and train.connection:
            try:
                # This is a placeholder; aioble's `disconnect` might need to be called on the `Device`
                # or `Connection` object differently, or might not be fully effective.
                # await train.connection.disconnect() # This line might error if not proper method
                print("BLE disconnect attempt (actual method may vary).")
            except Exception as e:
                print(f"Error during BLE disconnect attempt: {e}")
        print("Exiting program.")
        sys.exit()

