"""Command to show help information about mpf cli commands."""

import argparse

from mpf.commands import MpfCommandLineParser

SUBCOMMAND = True

class Command(MpfCommandLineParser):

    """Runs the mpf help command."""

    def __init__(self, args, path):
        """Parse args."""
        if (len(args) <= 1):
            print("mpf help\n\tusage: 'mpf help commandname'\n\texample: 'mpf help game'")
            return

        command_name = args.pop(1)
        super().__init__(args=args, path=path)

        machine_path, remaining_args = self.parse_args()
        self.machine_path = machine_path
        self.args = remaining_args

        parser.print_help()