"""FAST Expansion Board Serial Communicator."""
# mpf/platforms/fast/communicators/exp.py
from pprint import pformat

from functools import partial

from mpf.platforms.fast.fast_defines import EXPANSION_BOARD_FEATURES
from mpf.platforms.fast.fast_exp_board import FastExpansionBoard
from mpf.platforms.fast.communicators.base import FastSerialCommunicator

from mpf.core.utility_functions import Util

MYPY = False
if MYPY:   # pragma: no cover
    from mpf.core.machine import MachineController  # pylint: disable-msg=cyclic-import,unused-import


class FastExpCommunicator(FastSerialCommunicator):

    """Handles the serial communication for the FAST EXP bus."""

    IGNORED_MESSAGES = ['XX:F']

    __slots__ = ["exp_boards_by_address", "active_board", "_device_processors"]

    def __init__(self, platform, processor, config):
        """Initialize the EXP communicator."""
        super().__init__(platform, processor, config)

        self.exp_boards_by_address = dict()  # keys = board addresses, values = FastExpansionBoard objects
        self._device_processors = dict()
        self.active_board = None

        self.message_processors['BR:'] = self._process_br

    async def init(self):
        """Query the expansion boards."""
        await self.query_exp_boards()

    def start_tasks(self):
        """Start listening for commands and schedule watchdog."""
        for board in self.exp_boards_by_address.values():
            self.tasks.append(self.platform.machine.clock.schedule_interval(
                              board.update_leds, 1 / board.config['led_hz']))

    def stopping(self):
        """Stop listening to the board and clear it."""
        for board in self.exp_boards_by_address.values():
            board.communicator.send_and_forget(f'BR@{board.address}:')

    async def soft_reset(self):
        """Trigger a soft reset for the board and all breakouts."""
        for board in self.exp_boards_by_address.values():
            await board.soft_reset()

    async def query_exp_boards(self):
        """Query the EXP bus for connected boards."""
        boards = self.config['boards']

        #PRINT NUMBER OF BOARDS IN CONFIG
        self.log.info("EXP: %d boards found in config", len(boards))

        for board_name, board_config in boards.items():

            # Keep a copy of the raw fields for logging
            model_raw = board_config.get('model')
            addr_cfg = board_config.get('address')

            # FP-eXp-0071-2 -> FP-EXP-0071
            board_config['model'] = ('-').join(board_config['model'].split('-')[:3]).upper()

            if board_config['address']:  # need to do it this way since valid config will have 'address' = None
                board_address = board_config['address']
                self.log.info("Use config board address: %s", board_address)
            else:
                board_address = EXPANSION_BOARD_FEATURES[board_config['model']]['default_address']
                self.log.info("Use default board address: %s", board_address)


            self.log.info('EXP CURRENT BOARD -> board_name=%s board_address=%s model=%s',
                      board_name, board_address, board_config['model'])


            # Got an ID for a board that's already registered. This shouldn't happen?
            if board_address in self.exp_boards_by_address:
                raise AssertionError(f'Expansion Board at address {board_address} is already registered')

            board_obj = FastExpansionBoard(board_name, self, board_address, board_config)
            
            self.log.info("exp_boards_by_address: registering board_obj with EXP communicator")
            self.exp_boards_by_address[board_address] = board_obj  # registers with this EXP communicator
            
            self.log.info("register_expansion_board: registering board_obj with the platform")
            self.platform.register_expansion_board(board_obj)  # registers with the platform
            
            self.log.info("setting active_board slot to %s", board_address)
            self.active_board = board_address

            self.log.info("send_and_wait_for_response_processed for ID@%s",board_address)
            await self.send_and_wait_for_response_processed(f'ID@{board_address}:', 'ID:',timeout=5)
          

            self.log.info("loop through breakout_boards")
            for breakout_board in board_obj.breakouts.values():
                self.log.info("set active_board to address: %s", breakout_board.address)
                self.active_board = breakout_board.address

                self.log.info("send_and_wait_for_response_processed for ID@%s",breakout_board.address)
                await self.send_and_wait_for_response_processed(f'ID@{breakout_board.address}:', 'ID:',timeout=5)

            self.log.info("awaiting board_obj reset")
            await board_obj.reset()

            # After registering & resetting all boards:
            self.log.info("self.exp_boards_by_address now has %d verified board(s).", len(self.exp_boards_by_address))
            self.log_board_index()


    # def _process_id(self, msg: str):
    #     # self.exp_boards_by_address[self.active_board[:2]].verify_hardware(msg, self.active_board)
    #     self.active_board = None
    #     self.done_processing_msg_response()

    def _process_id(self, msg: str):
        # 1) ARRIVAL: release anyone waiting for the 'ID:' arrival
        if not self.done_waiting.is_set():
            self.done_waiting.set()

        # 2) Do the real work (verify, etc.)
        try:
            # If you still want verification, put it back:
            self.exp_boards_by_address[self.active_board[:2]].verify_hardware(msg, self.active_board)
            pass
        finally:
            # 3) PROCESSING DONE: release the send gate for the next message
            self.active_board = None
            self.done_processing_msg_response()   # this MUST call no_response_waiting.set() under the hood


    # def _process_br(self, msg):
    #     del msg
    #     self.active_board = None
    #     self.done_processing_msg_response()

    def _process_br(self, msg):
        del msg
        # ARRIVAL
        if not self.done_waiting.is_set():
            self.done_waiting.set()
        # PROCESSING DONE
        self.active_board = None
        self.done_processing_msg_response()


    def set_led_fade_rate(self, board_address: str, rate: int) -> None:
        """Sets the hardware LED fade rate for an EXP board.

        Parameters
        ----------
            board_address (str): 2 hex character board address
            rate (int): Fade rate, in milliseconds, between 0 and 8191

        Raises
        ------
            ValueError: If the fade rate is out of bounds
        """
        if not 0 <= rate <= 8191:
            raise ValueError(f"FAST LED fade rate of {rate}ms is out of bounds. Must be between 0 and 8191ms")

        self.platform.debug_log("%s - Setting LED fade rate to %sms", self, rate)
        self.send_and_forget(f'RF@{board_address}:{Util.int_to_hex_string(rate, True)}')

    def register_processor(self, message_prefix, board_address, device_id, callback):
        """Register an exp board processor to handle messages."""
        if message_prefix not in self.message_processors:
            self.message_processors[message_prefix] = partial(self._process_device_msg, message_prefix)
            self._device_processors[message_prefix] = dict()
        if board_address not in self._device_processors[message_prefix]:
            self._device_processors[message_prefix][board_address] = dict()
        self._device_processors[message_prefix][board_address][device_id] = callback

    def _process_device_msg(self, message_prefix, message):
        # Commands like MS: currently don't include the EXP board in the response,
        # so there's no way to know which board needs to be informed. Inform them
        # all? If multiple boards are running concurrently, it'll get ugly.
        device_id = message.split(",")[0]
        for board_callback in self._device_processors[message_prefix].values():
            board_callback[device_id](message)

    def log_board_index(self) -> None:
        """Log a readable map of EXP boards by hex address."""
        # sort by hex value so 48, 84, B4, etc. are in numeric order
        items = sorted(self.exp_boards_by_address.items(), key=lambda kv: int(kv[0], 16))
        mapping = {
            addr: {
                "name": b.name,
                "model": b.model,
                "breakouts": sorted(list(b.breakouts.keys())),  # e.g. ["0","1"]
            }
            for addr, b in items
        }
        self.log.info("EXP board index:\n%s", pformat(mapping))
