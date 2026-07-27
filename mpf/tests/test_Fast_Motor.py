# mpf.tests.test_Fast_Motor (DC motors)

from mpf.tests.test_Fast import TestFastBase
from mpf.tests.MpfTestCase import test_config

class TestFastMotor(TestFastBase):
    """Tests the FAST DC Motor config on EXP."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serial_connections_to_mock = ['exp']

    def get_config_file(self):
        return 'motors.yaml'

    def create_expected_commands(self):
        self.serial_connections['exp'].expected_commands = {
            # set all lights off on 0051
            'RA@D00:000000': '',
            'ER@D00:0,0,00,20': 'ER:P',
            'ER@D00:1,0,20,20': 'ER:P',
            'ER@D00:2,0,40,20': 'ER:P',
            'ER@D00:3,0,60,20': 'ER:P',

            # 'MF@D00:00,5DC,FF': '',  # forward pulse
            # 'MR@D00:00,9C4,BF': '',  # reverse pulse
            # 'ML@D00:00,DAC,7F': '',  # forward limit
            # 'MH@D00:00,1194,3F': '', # reverse limit
            'MC@D00:00': '',         # stop
        }

    def test_motor_commands(self):
        fast_motor = self.machine.dc_motors['test_fast_motor'].hw_motor

        # fast_motor.pulse(duration_secs=1.5, power=1)
        # fast_motor.reverse_pulse(duration_secs=2.5, power=0.75)
        # fast_motor.pulse_limit(duration_secs=3.5, power=0.5)
        # fast_motor.reverse_pulse_limit(duration_secs=4.5, power=0.25)
        # fast_motor.stop()

        self.assertEqual(0, len(self.serial_connections['exp'].expected_commands))
