"""
Demo plugin for oebuild command system.
Provides example implementation of OebuildCommand.
"""

import argparse
import logging
import textwrap

from oebuild.command import OebuildCommand
from oebuild.configure import Configure

logger = logging.getLogger()


class Demo(OebuildCommand):
    """
    Demo command class for testing and demonstration purposes.
    """

    def __init__(self):
        self.configure = Configure()
        super().__init__(
            name='demo',
            help_msg='this is your help message',
            description=textwrap.dedent("""\
            this is your description message
"""),
        )

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(
            parser_adder,
            usage="""

  %(prog)s [-m URL] [--mr REVISION] [--mf FILE] [directory]
  %(prog)s -l [--mf FILE] directory
""",
        )

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        """Execute the demo command."""
        args = args.parse_args(unknown)
        # Demo command implementation would go here
