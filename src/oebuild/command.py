'''
Copyright (c) 2023 openEuler Embedded
oebuild is licensed under Mulan PSL v2.
You can use this software according to the terms and conditions of the Mulan PSL v2.
You may obtain a copy of Mulan PSL v2 at:
         http://license.coscl.org.cn/MulanPSL2
THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
See the Mulan PSL v2 for more details.
'''

from abc import ABC, abstractmethod
import argparse
from typing import List
import colorama

INF_COLOR = colorama.Fore.LIGHTGREEN_EX

WRN_COLOR = colorama.Fore.LIGHTYELLOW_EX

ERR_COLOR = colorama.Fore.LIGHTRED_EX

class OebuildCommand(ABC):
    '''Abstract superclass for a oebuild command.'''

    def __init__(self, name, help_msg, description):
        self.name = name
        self.help_msg = help_msg
        self.description = description
        self.parser:argparse.ArgumentParser = None

    def run(self, args: argparse.ArgumentParser, unknown: List[str]):
        '''
        The executing body, each inherited class will
        register the executor with the executor body for execution
        '''
        self.do_run(args=args, unknown=unknown)

    def pre_parse_help(self, args: argparse.ArgumentParser, unknown: List[str]):
        '''
        Whether to parse the help command in advance, designed to adapt to some extended 
        scenarios that do not require command resolution, generally the function is placed 
        in the front of the do_run to execute, if it returns true, it means that it is a 
        help command, then there is no need to continue to execute, otherwise the specific 
        function content is executed
        '''
        pars = args.parse_args(unknown)
        if pars.help:
            self.print_help_msg()
            return True
        return False

    def add_parser(self, parser_adder: argparse.ArgumentParser):
        '''
        Registers a parser for this command, and returns it.
        The parser object is stored in a ``parser`` attribute.
        :param parser_adder: The return value of a call to
            ``argparse.ArgumentParser.add_subparsers()``
        '''
        self.parser:argparse.ArgumentParser = self.do_add_parser(parser_adder)

        if self.parser is None:
            raise ValueError('do_add_parser did not return a value')

        self.parser.add_argument('-h', '--help', dest="help", action="store_true",
            help='get help for oebuild or a command')

        return self.parser

    @abstractmethod
    def do_add_parser(self, parser_adder: argparse.ArgumentParser):
        '''
        The directive registers the interface, which the successor needs to implement
        '''

    @abstractmethod
    def do_run(self, args: argparse.Namespace, unknown: List[str]):
        '''
        Subclasses must implement; called to run the command.
        :param args: ``argparse.Namespace`` of parsed arguments
        :param unknown: If ``accepts_unknown_args`` is true, a
            sequence of un-parsed argument strings.
        '''

    def print_help_msg(self):
        '''
        print help message
        '''
        self.parser.print_help()

    def _parser(self, parser: argparse.ArgumentParser, **kwargs):
        # return a "standard" parser.

        kwargs['help'] = self.help_msg
        kwargs['description'] = self.description
        kwargs['formatter_class'] = argparse.RawDescriptionHelpFormatter

        parser.__dict__.update(kwargs)

        return parser
