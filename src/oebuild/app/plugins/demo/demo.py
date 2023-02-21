import argparse
import textwrap
import logging

from oebuild.command import OebuildCommand
from oebuild.util import *
from oebuild.configure import Configure

logger = logging.getLogger()

class Demo(OebuildCommand):

    def __init__(self):
        self.configure = Configure()
        super().__init__(
            name='{}',
            help='this is your help mesasge',
            description=textwrap.dedent('''\
            this is your description message
'''
        ))

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [-m URL] [--mr REVISION] [--mf FILE] [directory]
  %(prog)s -l [--mf FILE] directory
''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown = None):
        args = args.parse_args(unknown)
        pass