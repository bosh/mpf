import asyncio
import inspect

from unittest.mock import patch, AsyncMock, MagicMock

from mpf.core.utility_functions import Util
from mpf.tests.MpfTestCase import MpfTestCase


class TestDeviceManager(MpfTestCase):

    def test_control_events_arguments(self):
        for device_type in self.machine.config['mpf']['device_modules'].values():

            device_cls = Util.string_to_class(device_type)

            config_spec = self.machine.config_validator.config_spec[device_cls.config_section]

            for k in config_spec:
                if not k.endswith('_events') or k == "control_events" or config_spec[k] == "ignore":
                    continue
                method_name = k[:-7]
                method = getattr(device_cls, "event_{}".format(method_name), None)
                self.assertIsNotNone(method, "Method {}.event_{} is missing for {}".format(device_type, method_name, k))

                sig = inspect.signature(method)

                self.assertTrue(sig.parameters['self'],
                    "Method {}.{} is missing self. Actual signature: {}".format(
                    device_type, method_name, sig))

                self.assertTrue('kwargs' in sig.parameters,
                    "Method {}.{} is missing **kwargs. Actual signature: {}".format(
                    device_type, method_name, sig))

                self.assertEqual(sig.parameters['kwargs'].kind, inspect._VAR_KEYWORD,
                    "Method {}.{} kwargs param is missing '**'".format(
                    device_type, method_name))

                self.assertTrue(hasattr(method, "relative_priority"),
                                "Method {}.{} is missing a relative_priority. Did you apply the event_handler "
                                "decorator?".format(device_type, method_name))

    def test_initialize_devices_re_raises_first_exception(self):
        """Test that initialize_devices re-raises exceptions from failed device initialization."""
        async def test_exception_handling():
            failing_task = asyncio.create_task(self._failing_coro())
            slow_task = asyncio.create_task(self._slow_coro())

            fs = [failing_task, slow_task]
            done, pending = await asyncio.wait(fs, return_when=asyncio.FIRST_EXCEPTION)

            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is not None:
                    for pending_task in pending:
                        pending_task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    raise exc

        with self.assertRaises(RuntimeError):
            self.loop.run_until_complete(test_exception_handling())

    def test_initialize_devices_completes_when_all_succeed(self):
        """Test that initialize_devices completes normally when all devices succeed."""
        async def test_success_handling():
            success1 = asyncio.create_task(self._success_coro())
            success2 = asyncio.create_task(self._success_coro())

            fs = [success1, success2]
            done, pending = await asyncio.wait(fs, return_when=asyncio.FIRST_EXCEPTION)

            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc is not None:
                    for pending_task in pending:
                        pending_task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    raise exc

            return "success"

        result = self.loop.run_until_complete(test_success_handling())
        self.assertEqual(result, "success")

    async def _failing_coro(self):
        """Async coroutine that fails."""
        raise RuntimeError("Device initialization failed")

    async def _slow_coro(self):
        """Async coroutine that takes time."""
        await asyncio.sleep(10)
        return "done"

    async def _success_coro(self):
        """Async coroutine that succeeds."""
        await asyncio.sleep(0)
        return "success"
