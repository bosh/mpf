"""Command to start the MPF game engine."""

import argparse
import errno
import os
import signal
import socket
import sys
import datetime
import logging
from logging.handlers import QueueHandler, SysLogHandler
import time
import re
import zlib

from queue import Queue

from mpf.core.crash_reporter import report_crash
from mpf.core.machine import MachineController
from mpf.core.utility_functions import Util
from mpf.core.config_loader import YamlMultifileConfigLoader, ProductionConfigLoader
from mpf.commands.logging_formatters import JSONFormatter
from mpf.exceptions.config_file_error import ConfigFileError


class Command:

    """Runs the mpf game."""

    # pylint: disable-msg=too-many-locals,too-many-statements
    def __init__(self, mpf_path, machine_path, args):
        """Run mpf game."""
        del mpf_path
        self.machine = None
        self._sigint_count = 0

        parser = argparse.ArgumentParser(description='Starts the MPF game engine')

        parser.add_argument("-a",
                            action="store_true", dest="no_load_cache",
                            help="Forces the config to be loaded from files and not cache")

        parser.add_argument("-A",
                            action="store_false", dest="create_config_cache",
                            help="Does not create the cache config files")

        parser.add_argument("-b",
                            action="store_false", dest="bcp", default=True,
                            help="Runs MPF without making a connection attempt to a BCP Server")

        parser.add_argument("-c",
                            action="store", dest="configfile",
                            default="config.yaml", metavar='config_file',
                            help="The name of a config file to load. Default is "
                                 "config.yaml. Multiple files can be used via a comma-"
                                 "separated list (no spaces between)")

        parser.add_argument("-e",
                            action="store_false", dest="echo_args", default=True,
                            help="Stop logging the raw command line arguments on startup.")

        parser.add_argument("-f",
                            action="store_true", dest="force_assets_load",
                            default=False,
                            help="Load all assets upon startup.  Useful for "
                            "ensuring all assets are set up properly during development.")

        parser.add_argument("-pit", action="store", dest="platform_integration_test",
                            metavar='pit_file', default=False,
                            help="Runs a platform integration test")

        parser.add_argument("--json-logging",
                            action="store_true", dest="jsonlogging",
                            default=False,
                            help="Enables json logging to file. ")

        parser.add_argument("-l",
                            action="store", dest="logfile",
                            metavar='file_name',
                            default=os.path.join(
                                "logs",
                                datetime.datetime.now().strftime(
                                    "%Y-%m-%d-%H-%M-%S-mpf-" +
                                    socket.gethostname() + ".log")),
                            help="The name (and path) of the log file")

        parser.add_argument("-p",
                            action="store_true", dest="pause", default=False,
                            help="Pause the terminal window on exit. Useful "
                            "when launching in a separate window so you can "
                            "see any errors before the window closes.")

        parser.add_argument("-P",
                            action="store_true", dest="production", default=False,
                            help="Production mode. Will suppress errors, wait for hardware on start "
                                 "and try to exit when startup fails. Run this inside a loop.")

        parser.add_argument("-t",
                            action="store_false", dest='text_ui', default=True,
                            help="Use the ASCII test-based UI")

        parser.add_argument("-v",
                            action="store_const", dest="loglevel",
                            const=logging.DEBUG,
                            default=15,
                            help="Enables verbose logging to the log file")

        parser.add_argument("-V",
                            action="store_const", dest="consoleloglevel",
                            const=logging.DEBUG,
                            default=logging.INFO,
                            help="Enables verbose logging to the console. DO "
                                 "NOTE: you must also use -v for this to work.")

        parser.add_argument("-x",
                            action="store_const", dest="force_platform",
                            const='virtual',
                            help="Forces the virtual platform to be used for all devices")

        parser.add_argument("--vpx",
                            action="store_const", dest="force_platform",
                            const='virtual_pinball',
                            help="Forces the virtual_pinball platform to be used for all devices")

        parser.add_argument("--syslog_address",
                            action="store", dest="syslog_address",
                            help="Log to the specified syslog address. This can be a domain socket "
                                 "such as /dev/og on Linux or /var/run/syslog on Mac. Alternatively, "
                                 "you an specify host:port for remote logging over UDP.")

        parser.add_argument("-X",
                            action="store_const", dest="force_platform",
                            const='smart_virtual',
                            help="Forces the smart virtual platform to be used for all devices")

        parser.add_argument("--color",
                            action=argparse.BooleanOptionalAction, dest="color",
                            default=None,
                            help="Force or disable ANSI colorized console output.")

        self.args = parser.parse_args(args)
        self.args.configfile = Util.string_to_event_list(self.args.configfile)

        try:
            os.makedirs(os.path.join(machine_path, 'logs'))
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

        self.args.full_logfile_path = os.path.join(machine_path, self.args.logfile)

        try:
            os.remove(self.args.full_logfile_path)
        except OSError:
            pass

        if self.args.text_ui:
            console_log = logging.NullHandler()
            console_log.setLevel(logging.ERROR)
        else:
            console_log = logging.StreamHandler()
            if self.args.production:
                console_log.setLevel(logging.ERROR)
            else:
                console_log.setLevel(self.args.consoleloglevel)

        use_color = (
            not os.environ.get("NO_COLOR")
            and (
                bool(os.environ.get("FORCE_COLOR"))
                or (sys.stderr.isatty() and os.environ.get("TERM") != "dumb")
            )
        )
        if use_color:
            if sys.platform == "win32":
                os.system("")  # Enable ANSI VT100 escape processing in Windows consoles
            console_log.setFormatter(ColorFormatter(
                '%(asctime)s : %(levelname)s [%(name)s] %(message)s'))
        else:
            console_log.setFormatter(logging.Formatter(
                '%(asctime)s.%(msecs)03d : %(levelname)s [%(name)s] %(message)s', "%H:%M:%S"))

        console_log.addFilter(ConsoleCustomLevelFilter())

        # initialize async handler for console
        console_log_queue = Queue()
        console_queue_handler = QueueHandler(console_log_queue)
        self.console_queue_listener = logging.handlers.QueueListener(
            console_log_queue, console_log, respect_handler_level=True)
        self.console_queue_listener.start()

        # initialize file log
        file_log = logging.FileHandler(self.args.full_logfile_path)
        if self.args.jsonlogging:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter('%(asctime)s : %(levelname)s : %(name)s : %(message)s')
        file_log.setFormatter(formatter)
        file_log.addFilter(FileCustomLevelFilter())

        # initialize async handler for file log
        file_log_queue = Queue()
        file_queue_handler = QueueHandler(file_log_queue)
        self.file_queue_listener = logging.handlers.QueueListener(
            file_log_queue, file_log)
        self.file_queue_listener.start()

        # add loggers
        logger = logging.getLogger()
        logger.addHandler(console_queue_handler)
        logger.addHandler(file_queue_handler)
        logger.setLevel(self.args.loglevel)
        logger.info("Loading config.")

        if self.args.syslog_address:
            try:
                host, port = self.args.syslog_address.split(":")
            except ValueError:
                syslog_logger = SysLogHandler(self.args.syslog_address)
            else:
                syslog_logger = SysLogHandler((host, int(port)))

            logger.addHandler(syslog_logger)

        signal.signal(signal.SIGINT, self.sigint_handler)

        if self.args.echo_args:
            raw_cmd = " ".join(args) if args else "[None]"
            logger.info("Raw command line: %s", raw_cmd)

        if not self.args.production:
            config_loader = YamlMultifileConfigLoader(machine_path, self.args.configfile,
                                                      not self.args.no_load_cache, self.args.create_config_cache)
        else:
            config_loader = ProductionConfigLoader(machine_path)

        try:
            config = config_loader.load_mpf_config()
        except ConfigFileError as e:
            print("Error while parsing config: {}", e)
            report_crash(e, "config_parsing", {})
            self.exit()

        try:
            self.machine = MachineController(vars(self.args), config)
            self.machine.add_crash_handler(self.restore_logger)
            self.machine.run()
            logging.info("MPF run loop ended.")
            self.exit()

        # pylint: disable-msg=broad-except
        except Exception as e:
            self.exit(exception=e)

    def sigint_handler(self, signum=None, frame=None):
        """Handle SIGINT."""
        del signum, frame
        if self.machine:
            self.machine.error_log("SIGINT received")
        self._sigint_count += 1
        if self._sigint_count > 1:
            self.exit("Received second SIGINT. Will exit ungracefully!")
        elif self.machine:
            self.machine.stop("SIGINT or keyboard interrupt")
        else:
            self.exit("Shutdown because of SIGINT or keyboard interrupt.")

    def restore_logger(self):
        """Restore logger."""
        if self.args.text_ui:
            # Re-enable console logging
            logger = logging.getLogger()
            logger.addHandler(logging.StreamHandler())

    def exit(self, exception=None):
        """Handle MPF exit from either a clean shutdown or from a crash.

        Cleanly shuts down logging and restores the console window if the Text
        UI option is used.
        """
        if exception:
            logging.exception(exception)

        logging.shutdown()
        if self.console_queue_listener:
            self.console_queue_listener.stop()
            self.console_queue_listener = None
        if self.file_queue_listener:
            self.file_queue_listener.stop()
            self.file_queue_listener = None

        if self.args.pause:
            input('Press ENTER to continue...')     # nosec

        sys.exit()


class ConsoleCustomLevelFilter(logging.Filter):

    """Filters out custom levels meant strictly for files."""

    def filter(self, record):
        """Filters: 11 = DEBUG (File Only), 21 = INFO (File Only)."""
        if record.levelno in (11, 21):
            return False
        return True


class FileCustomLevelFilter(logging.Filter):

    """Filters out custom levels meant strictly for console."""

    def filter(self, record):
        """Filters: 12 = DEBUG (Console Only), 22 = INFO (Console Only)."""
        if record.levelno in (12, 22):
            return False
        return True


class ColorFormatter(logging.Formatter):

    """ANSI TrueColor formatter with gradient timestamps, family names, and alert levels."""

    RESET = "\033[0m"
    DIM = "\033[90m"
    EVENT_PREFIX_RE = re.compile(r"(?<=\]\s)Event:(?=\s)")
    ARGS_WRAPPER_RE = re.compile(r"(?<=\s)Args=\{([^\n]*)\}$")

    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan (covers 10 and 12)
        logging.WARNING: "\033[33m",    # Yellow (30)
        logging.ERROR: "\033[31m",      # Red (40)
        logging.CRITICAL: "\033[1;31m"  # Bold Red (50)
    }

    # Smooth 0-100 gradient stops (Cyan -> Violet -> Coral -> Gold -> Mint)
    GRADIENT_STOPS = (
        (0,   (80, 220, 255)),
        (25,  (170, 130, 255)),
        (50,  (255, 110, 160)),
        (75,  (255, 200, 90)),
        (100, (90, 240, 170)),
    )

    @classmethod
    def _sample_gradient(cls, step: int) -> str:
        """Sample a 0-100 step along GRADIENT_STOPS and return a 24-bit ANSI escape."""
        step = max(0, min(100, step))
        for i in range(len(cls.GRADIENT_STOPS) - 1):
            s0, c0 = cls.GRADIENT_STOPS[i]
            s1, c1 = cls.GRADIENT_STOPS[i + 1]
            if s0 <= step <= s1:
                t = (step - s0) / (s1 - s0)
                r = round(c0[0] + (c1[0] - c0[0]) * t)
                g = round(c0[1] + (c1[1] - c0[1]) * t)
                b = round(c0[2] + (c1[2] - c0[2]) * t)
                return f"\033[38;2;{r};{g};{b}m"
        r, g, b = cls.GRADIENT_STOPS[-1][1]
        return f"\033[38;2;{r};{g};{b}m"

    def formatTime(self, record, datefmt=None):
        """Format HH:MM:SS.mmm with 2-segment ping-pong (0->500->0) millisecond gradient."""
        ct = self.converter(record.created)
        hours = time.strftime("%H", ct)

        min_step = round((ct.tm_min / 59) * 100)
        sec_step = round((ct.tm_sec / 59) * 100)
        ms_val = int(record.msecs)

        if ms_val < 500:
            pos = ms_val / 499
        else:
            pos = (999 - ms_val) / 499
        ms_step = round(pos * 100)

        c_min = self._sample_gradient(min_step)
        c_sec = self._sample_gradient(sec_step)
        c_ms = self._sample_gradient(ms_step)
        blink_ms = "\033[5m" if ms_val % 111 == 0 else ""

        return (
            f"{hours}:"
            f"{c_min}{ct.tm_min:02d}{self.RESET}:"
            f"{c_sec}{ct.tm_sec:02d}{self.RESET}."
            f"{blink_ms}{c_ms}{ms_val:03d}{self.RESET}"
        )

    def format(self, record):
        """Colorize timestamps, family names, non-INFO levels, and mute boilerplate wrappers."""
        base_level = (record.levelno // 10) * 10
        color = self.LEVEL_COLORS.get(base_level)

        orig_levelname = record.levelname
        orig_name = record.name

        if color:
            record.levelname = f"{color}{orig_levelname}{self.RESET}"

        family, dot, device = orig_name.partition(".")
        family_bucket = zlib.crc32(family.encode("utf-8")) % 32
        family_step = round((family_bucket / 31) * 100)
        family_color = self._sample_gradient(family_step)
        if dot:
            record.name = f"{family_color}{family}{self.RESET}.{device}"
        else:
            record.name = f"{family_color}{family}{self.RESET}"

        try:
            formatted = super().format(record)
        finally:
            record.levelname = orig_levelname
            record.name = orig_name

        formatted = self.EVENT_PREFIX_RE.sub(f"{self.DIM}Event:{self.RESET}", formatted)
        formatted = self.ARGS_WRAPPER_RE.sub(
            rf"{self.DIM}Args={{{self.RESET}\1{self.DIM}}}{self.RESET}",
            formatted,
        )
        return formatted
