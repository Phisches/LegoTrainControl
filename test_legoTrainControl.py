import sys
import unittest
from unittest.mock import MagicMock, patch

# --- Mock hardware-dependent modules BEFORE importing legoTrainControl ---
# These modules are imported by legoTrainControl.py at its module level.
# They need to be available (even as mocks) when the Python interpreter
# first loads legoTrainControl.py.

# Mock 'machine' module and its classes Pin and ADC
mock_machine = MagicMock()
mock_machine.Pin = MagicMock()
mock_machine.ADC = MagicMock()
sys.modules['machine'] = mock_machine

# Mock 'aioble' module
sys.modules['aioble'] = MagicMock()

# Mock 'bluetooth' module and its UUID class
mock_bluetooth = MagicMock()
mock_bluetooth.UUID = MagicMock(return_value="mock-uuid-string") # UUID constructor mock
sys.modules['bluetooth'] = mock_bluetooth

# Mock 'uasyncio' and its components like sleep_ms, run
mock_uasyncio = MagicMock()
mock_uasyncio.sleep_ms = MagicMock()
mock_uasyncio.run = MagicMock()
sys.modules['uasyncio'] = mock_uasyncio
sys.modules['asyncio'] = mock_uasyncio # legoTrainControl uses 'import uasyncio as asyncio'

# Mock 'hubs' module (assuming it's a custom module for this project)
sys.modules['hubs'] = MagicMock()

# --- Now import from legoTrainControl ---
# The mocks above should prevent ImportError for the hardware modules.
from legoTrainControl import (
    Color, Sound, Button, DuploTrainHub, Action,
    SPEED_THRESHOLDS,
    CMD_MOTOR_STOP, CMD_MOTOR_FORWARD_SPEED_1, CMD_MOTOR_FORWARD_SPEED_2, CMD_MOTOR_FORWARD_SPEED_3,
    CMD_MOTOR_REVERSE_SPEED_1, CMD_MOTOR_REVERSE_SPEED_2, CMD_MOTOR_REVERSE_SPEED_3,
    # Pin definitions are used by legoTrainControl, but we mock machine.Pin directly in tests where needed
    # We don't need to import the pin consts themselves into the test file unless we directly use them.
)

# --- Test Classes ---

class TestColor(unittest.TestCase):
    def test_get_bytes_for_color(self):
        self.assertEqual(Color.getBytesForColor(Color.RED), [0x00, 0x81, 0x11, 0x01, 0x51, 0x00, Color.RED])
        self.assertEqual(Color.getBytesForColor(Color.BLUE), [0x00, 0x81, 0x11, 0x01, 0x51, 0x00, Color.BLUE])
        self.assertEqual(Color.getBytesForColor(Color.BLACK), [0x00, 0x81, 0x11, 0x01, 0x51, 0x00, Color.BLACK])

class TestSound(unittest.TestCase):
    def test_sound_byte_arrays(self):
        # Verify a few key sound byte arrays
        self.assertEqual(Sound.PREPARE_SOUND, [0x00, 0x41, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x01])
        self.assertEqual(Sound.SOUND_BRAKE, [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 3])
        self.assertEqual(Sound.SOUND_HORN, [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 9])
        self.assertEqual(Sound.SOUND_STEAM, [0x00, 0x81, 0x01, 0x01, 0x51, 0x01, 10])

class TestButton(unittest.TestCase):
    def setUp(self):
        # It's important to patch 'machine.Pin' where it's LOOKED UP,
        # which is in the legoTrainControl module's scope.
        self.mock_pin_patcher = patch('legoTrainControl.machine.Pin')
        self.MockPinClass = self.mock_pin_patcher.start()
        # This MockPinClass is now the class 'machine.Pin' within legoTrainControl
        # We can also get the instance created by Button:
        self.mock_pin_instance = self.MockPinClass.return_value 

    def tearDown(self):
        self.mock_pin_patcher.stop()

    def test_button_initialization(self):
        test_pin_num = 10
        test_button_name = "TestBtn"
        test_sound_cmd = Sound.SOUND_HORN

        button = Button(pin=test_pin_num, name=test_button_name, sound=test_sound_cmd)

        self.assertEqual(button.pin, test_pin_num)
        self.assertEqual(button.name, test_button_name)
        self.assertEqual(button.sound, test_sound_cmd)
        self.assertEqual(button.state, "unpressed")
        self.assertEqual(button.action_list, [])

        # Check that machine.Pin was called correctly
        # sys.modules['machine'] is already a MagicMock from the top of the file.
        # We need to access its Pin attribute that we also mocked.
        # The mock_machine.Pin used in legoTrainControl is self.MockPinClass
        self.MockPinClass.assert_called_once_with(test_pin_num, mock_machine.Pin.IN, mock_machine.Pin.PULL_UP)

    def test_button_add_action(self):
        button = Button(pin=12, name="ActionBtn", sound=Sound.SOUND_STEAM)
        mock_action = MagicMock(spec=Action) # Create a mock Action object
        
        button.add_action(mock_action)
        self.assertIn(mock_action, button.action_list)
        self.assertEqual(len(button.action_list), 1)

        mock_action_2 = MagicMock(spec=Action)
        button.add_action(mock_action_2)
        self.assertIn(mock_action_2, button.action_list)
        self.assertEqual(len(button.action_list), 2)

class TestDuploTrainHub(unittest.TestCase):
    def setUp(self):
        # bluetooth.UUID is already mocked globally in sys.modules.
        # We can specific further behavior if needed per test, but for now, the global mock is fine.
        pass

    def test_duplotrainhub_initialization(self):
        hub = DuploTrainHub()

        self.assertEqual(hub.ble_name, 'Train Base')
        self.assertEqual(hub.manufacturer_id, 32)
        
        # Check that bluetooth.UUID was called for uart_uuid and char_uuid
        # The mock_bluetooth.UUID was set up to return "mock-uuid-string"
        # So we assert that the attributes are this mock value.
        # We can also check call_args_list if we want to verify the input to UUID constructor.
        mock_bluetooth.UUID.assert_any_call('00001623-1212-efde-1623-785feabcd123')
        mock_bluetooth.UUID.assert_any_call('00001624-1212-efde-1623-785feabcd123')
        self.assertEqual(hub.uart_uuid, "mock-uuid-string") # Assuming global mock returns this
        self.assertEqual(hub.char_uuid, "mock-uuid-string")

        self.assertEqual(hub.color_value, Color.BLUE)
        self.assertTrue(hub.light)
        self.assertEqual(hub.speed, 0)
        self.assertEqual(hub.direction, "forward")

        self.assertIsNone(hub.connection)
        self.assertIsNone(hub.service)
        self.assertIsNone(hub.characteristic)

    def test_duplotrainhub_set_output(self):
        hub = DuploTrainHub()
        test_port = 0x01
        test_mode = 0x02
        test_value = 0xAB
        expected_bytes = [0x00, 0x81, test_port, 0x01, 0x51, test_mode, test_value]
        
        result_bytes = hub.set_output(test_port, test_mode, test_value)
        self.assertEqual(result_bytes, expected_bytes)

    def test_duplotrainhub_set_color(self):
        hub = DuploTrainHub()
        hub.setColor(Color.GREEN)
        self.assertEqual(hub.color_value, Color.GREEN)

        hub.setColor(Color.ORANGE)
        self.assertEqual(hub.color_value, Color.ORANGE)

class TestCommandConstants(unittest.TestCase):
    def test_motor_command_values(self):
        self.assertEqual(CMD_MOTOR_STOP, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x00])
        self.assertEqual(CMD_MOTOR_FORWARD_SPEED_1, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x1e])
        self.assertEqual(CMD_MOTOR_FORWARD_SPEED_2, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x32])
        self.assertEqual(CMD_MOTOR_FORWARD_SPEED_3, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x64])
        self.assertEqual(CMD_MOTOR_REVERSE_SPEED_1, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0xe2])
        self.assertEqual(CMD_MOTOR_REVERSE_SPEED_2, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0xce])
        self.assertEqual(CMD_MOTOR_REVERSE_SPEED_3, [0x00, 0x81, 0x00, 0x01, 0x51, 0x00, 0x9c])

# More test classes will be added here

if __name__ == '__main__':
    unittest.main()
