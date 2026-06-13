# mpf.tests.test_Fast_Led
"""Unit tests for FAST LED fade/brightness math."""
import unittest
from unittest.mock import MagicMock

from mpf.platforms.fast.fast_led import FASTLEDChannel


class _FakeLed:
    """Minimal stand-in for FASTRGBLED for unit-testing a single channel."""

    def __init__(self, hardware_fade_ms=0):
        self.number = '880'
        self.hardware_fade_ms = hardware_fade_ms
        self.dirty = False
        self.log = MagicMock()


class TestFastLed(unittest.TestCase):

    def _channel(self, hardware_fade_ms=0):
        return FASTLEDChannel(_FakeLed(hardware_fade_ms), 0)

    def test_fade_interpolates_to_three_places(self):
        # Half-way through a 0 -> 1 fade the brightness is 0.5.
        ch = self._channel()
        start = 1000.0
        ch.set_fade(start_brightness=0.0, start_time=start,
                    target_brightness=1.0, target_time=start + 1.0)

        brightness, _, _ = ch.get_fade_and_brightness(start + 0.5)

        self.assertAlmostEqual(brightness, 0.5, places=3)

    def test_fade_up_when_current_time_precedes_start_time(self):
        # When current_time reads as before the fade's start_time, a fade up
        # must not calculate a brightness below 0.
        ch = self._channel()
        now = 1000.0
        ch.set_fade(start_brightness=0.0, start_time=now + 0.01,
                    target_brightness=1.0, target_time=now + 0.5)

        brightness, _, _ = ch.get_fade_and_brightness(now)

        self.assertGreaterEqual(brightness, 0.0)
        self.assertLessEqual(brightness, 1.0)

    def test_fade_down_when_current_time_precedes_start_time(self):
        # The same out-of-order read while fading down must not calculate a
        # brightness above 1, which would format to a 3-char hex channel and
        # crash the downstream binascii unpacking.
        ch = self._channel()
        now = 1000.0
        ch.set_fade(start_brightness=1.0, start_time=now + 0.01,
                    target_brightness=0.0, target_time=now + 0.5)

        brightness, _, _ = ch.get_fade_and_brightness(now)

        self.assertGreaterEqual(brightness, 0.0)
        self.assertLessEqual(brightness, 1.0)
        self.assertEqual(2, len(f'{int(brightness * 255):02X}'))
