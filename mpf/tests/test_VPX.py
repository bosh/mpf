import asyncio
from typing import Tuple

from mpf.core.bcp.bcp_socket_client import decode_command_string, encode_command_string

from mpf.tests.loop import MockServer, MockQueueSocket

from mpf.tests.MpfTestCase import MpfTestCase


class TestVPX(MpfTestCase):

    def __init__(self, methodName):
        super().__init__(methodName)
        # remove config patch which disables bcp
        del self.machine_config_patches['bcp']
        self.machine_config_patches['bcp'] = dict()
        self.machine_config_patches['bcp']['connections'] = []
        self.client = None

    def get_config_file(self):
        return 'config.yaml'

    def get_machine_path(self):
        return 'tests/machine_files/vpx/'

    def get_use_bcp(self):
        return True

    def get_platform(self):
        return False

    def _mock_loop(self):
        self.mock_server = MockServer(self.clock.loop)
        self.clock.mock_server("127.0.0.1", 5051, self.mock_server)

    def _early_machine_init(self, machine):
        org_init = machine._run_init_phases
        async def _init_hook():
            machine.events.add_async_handler("init_phase_4", self._send_init)
            await org_init()
        machine._run_init_phases = _init_hook

    async def _send_init(self, **kwargs):
        self.client = MockQueueSocket(self.loop)
        await self.mock_server.add_client(self.client)
        # check hello
        cmd, args = await self._get_and_decode(self.client)
        self.assertEqual("hello", cmd)

        self._encode_and_send("start")

    @staticmethod
    async def _get_and_decode(client) -> Tuple[str, dict]:
        data = await client.send_queue.get()
        return decode_command_string(data[0:-1].decode())

    def read_vpx_response_from_bcp(self):
        cmd, args = self.loop.run_until_complete(self._get_and_decode(self.client))
        self.assertEqual(cmd, "vpcom_bridge_response")
        self.assertNotIn("error", args, "Error: {}".format(args.get("error")))
        return args.get("result")

    def _encode_and_send(self, cmd, **kwargs):
        self.client.recv_queue.append((encode_command_string("vpcom_bridge", subcommand=cmd, **kwargs) + '\n').encode())

    def test_vpx(self):
        self.advance_time_and_run()
        self.client.send_queue = asyncio.Queue()

        self._encode_and_send("changed_lamps")
        self._encode_and_send("changed_solenoids")

        self.read_vpx_response_from_bcp()
        self.read_vpx_response_from_bcp()

        self.machine.lights["test_light1"].on()
        self.advance_time_and_run(.1)
        self._encode_and_send("changed_lamps")
        result = self.read_vpx_response_from_bcp()
        self.assertEqual(result, [['0', True]])

        self.machine.coils["c_test"].pulse()
        self.advance_time_and_run(.001)

        self._encode_and_send("changed_solenoids")
        result = self.read_vpx_response_from_bcp()
        self.assertEqual(result, [['2', True]])
        self.advance_time_and_run(.1)
        self._encode_and_send("changed_solenoids")
        result = self.read_vpx_response_from_bcp()
        self.assertEqual(result, [['2', False]])

        self.machine.coils["c_test"].enable()
        self.advance_time_and_run(.001)

        self._encode_and_send("changed_solenoids")
        result = self.read_vpx_response_from_bcp()
        self.assertEqual(result, [['2', True]])

        self.machine.coils["c_test"].disable()
        self.advance_time_and_run(.001)

        self._encode_and_send("changed_solenoids")
        result = self.read_vpx_response_from_bcp()
        self.assertEqual(result, [['2', False]])

        self.machine.flippers["f_test"].enable()
        self.advance_time_and_run(.001)
        self._encode_and_send("get_hardwarerules")
        result = self.read_vpx_response_from_bcp()
        self.assertEqual(result, [['3', '1', True]])

        self.machine.autofire_coils["ac_slingshot_test"].enable()
        self.advance_time_and_run(.001)
        self._encode_and_send("get_hardwarerules")
        result = self.read_vpx_response_from_bcp()
        self.assertCountEqual(result, [['3', '1', True], ['0', '0', False]])

        self.machine.flippers["f_test"].disable()
        self.advance_time_and_run(.001)
        self._encode_and_send("get_hardwarerules")
        result = self.read_vpx_response_from_bcp()
        self.assertEqual(result, [['0', '0', False]])

        self.assertSwitchState("s_test", False)
        self._encode_and_send("set_switch", number=6, value=1)
        self.advance_time_and_run(.1)
        self.read_vpx_response_from_bcp()
        self.assertSwitchState("s_test", True)
        self._encode_and_send("set_switch", number=6, value=0)
        self.advance_time_and_run(.1)
        self.read_vpx_response_from_bcp()
        self.assertSwitchState("s_test", False)

    def test_vpx_reset_clears_switches_and_resets_machine(self):
        """vpx_reset wipes platform switch mirror, drives machine.reset(),
        and replies with result=ok."""
        self.advance_time_and_run()
        self.client.send_queue = asyncio.Queue()

        platform = self.machine.hardware_platforms['virtual_pinball']

        # Pre-condition: set two switches active via the platform handler the
        # plugin uses (so switch_controller stays consistent).
        platform.vpx_set_switch("0", True)   # s_sling
        platform.vpx_set_switch("3", True)   # s_flipper
        self.advance_time_and_run(.1)
        self.assertTrue(platform._switches["0"].state)
        self.assertTrue(platform._switches["3"].state)
        self.assertSwitchState("s_sling", True)

        # Track that machine_reset_phase_3 fires (proxy for machine.reset() running).
        reset_fired = []
        self.machine.events.add_handler(
            "machine_reset_phase_3", lambda **kwargs: reset_fired.append(True))

        # Action.
        self._encode_and_send("reset")
        self.advance_time_and_run(.5)

        # Reply check: result=ok, no error.
        result = self.read_vpx_response_from_bcp()
        self.assertIsNotNone(result)

        # Switch mirror cleared.
        self.assertFalse(platform._switches["0"].state)
        self.assertFalse(platform._switches["3"].state)
        self.assertSwitchState("s_sling", False)
        self.assertSwitchState("s_flipper", False)

        # machine.reset() ran.
        self.assertTrue(reset_fired, "machine_reset_phase_3 was not posted")

    def test_vpx_reset_ends_active_game(self):
        """vpx_reset ends a game in progress (returns to attract mode)."""
        self.advance_time_and_run()
        self.client.send_queue = asyncio.Queue()

        # Skip if the fixture can't actually run a game (no game mode, or no
        # playfield source device for ball delivery). In-progress-game-ends
        # behavior is covered by MPF's existing machine.reset() suite.
        if 'game' not in self.machine.modes:
            self.skipTest("VPX test fixture has no game mode")
        if not any(getattr(pf, 'config', {}).get('default_source_device')
                   for pf in self.machine.playfields):
            self.skipTest("VPX test fixture has no playfield source device; "
                          "cannot start a game in this fixture")

        # Start a game by posting the game_start event.
        self.machine.events.post('game_start')
        self.advance_time_and_run(1)
        self.assertIsNotNone(
            self.machine.game,
            "Setup precondition failed: game did not start")

        # Reset.
        self._encode_and_send("reset")
        self.advance_time_and_run(.5)
        self.read_vpx_response_from_bcp()

        # Game ended; machine is back in attract.
        self.assertIsNone(
            self.machine.game,
            "vpx_reset did not end the active game")
