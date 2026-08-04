"""Platform interface for dc motors."""
from typing import List

import abc


class MotorPlatformInterface(metaclass=abc.ABCMeta):

    """Interface for dc motors in hardware platforms.

    MotorPlatformInterface is an abstract base class that should be overridden for all
    dc motor interface classes on supported platforms.  This class ensures the proper required
    methods are implemented to support dc motor operations in MPF.
    """

    __slots__ = []  # type: List[str]

    @abc.abstractmethod
    def pulse(self, duration_secs, power):
        """Enable the dc motor for specified duration and power level."""
        raise NotImplementedError

    @abc.abstractmethod
    def reverse_pulse(self, duration_secs, power):
        """Enable the dc motor for specified duration and power level in reverse."""
        raise NotImplementedError

    @abc.abstractmethod
    def pulse_limit(self, duration_secs, power):
        """Enable the dc motor at power level for duration or until limit hit."""
        raise NotImplementedError

    @abc.abstractmethod
    def reverse_pulse_limit(self, duration_secs, power):
        """Enable the dc motor at power level in reverse for duration or until limit (home) hit."""
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self):
        """Stop this dc motor.

        This should stop the output and end motion.
        """
        raise NotImplementedError
