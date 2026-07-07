"""Test Light Numbering with previous."""
from mpf.tests.MpfTestCase import MpfTestCase, test_config


class TestLightNumbering(MpfTestCase):

    def get_config_file(self):
        return 'light_autonumber.yaml'

    def get_machine_path(self):
        return 'tests/machine_files/light/'

    def test_light_positions(self):
        led1 = self.machine.lights["first"]
        led2 = self.machine.lights["second"]
        led3 = self.machine.lights["third"]
        led4 = self.machine.lights["fourth"]

        self.assertEqual(led1.hw_drivers["green"][0].number,"led-0-0-0")
        self.assertEqual(led1.hw_drivers["red"][0].number,"led-0-0-0+1")
        self.assertEqual(led1.hw_drivers["blue"][0].number,"led-0-0-0+2")
        self.assertEqual(led1.hw_drivers["white"][0].number,"led-0-0-0+3")

        self.assertEqual(led2.hw_drivers["green"][0].number,"led-0-0-0+4")
        self.assertEqual(led2.hw_drivers["red"][0].number,"led-0-0-0+5")
        self.assertEqual(led2.hw_drivers["blue"][0].number,"led-0-0-0+6")
        self.assertEqual(led2.hw_drivers["white"][0].number,"led-0-0-0+7")

        self.assertEqual(led3.hw_drivers["green"][0].number,"led-0-0-0+8")
        self.assertEqual(led3.hw_drivers["red"][0].number,"led-0-0-0+9")
        self.assertEqual(led3.hw_drivers["blue"][0].number,"led-0-0-0+10")
        self.assertEqual(led3.hw_drivers["white"][0].number,"led-0-0-0+11")

        self.assertEqual(led4.hw_drivers["green"][0].number,"led-0-0-0+12")
        self.assertEqual(led4.hw_drivers["red"][0].number,"led-0-0-0+13")
        self.assertEqual(led4.hw_drivers["blue"][0].number,"led-0-0-0+14")
        self.assertEqual(led4.hw_drivers["white"][0].number,"led-0-0-0+15")
