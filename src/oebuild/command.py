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
import importlib.util
from collections import OrderedDict
import os
from dataclasses import dataclass
import sys
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
        self.parser = None

    def run(self, args: argparse.Namespace, unknown: List[str]):
        '''
        The executing body, each inherited class will
        register the executor with the executor body for execution
        '''
        self.do_run(args=args, unknown=unknown)

    def add_parser(self, parser_adder):
        '''
        Registers a parser for this command, and returns it.
        The parser object is stored in a ``parser`` attribute.
        :param parser_adder: The return value of a call to
            ``argparse.ArgumentParser.add_subparsers()``
        '''
        parser = self.do_add_parser(parser_adder)

        if parser is None:
            raise ValueError('do_add_parser did not return a value')

        self.parser = parser
        return self.parser

    @abstractmethod
    def do_add_parser(self, parser_adder):
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

    def print_help(self, args: argparse.Namespace):
        '''
        print help message
        '''
        args = args.parse_args(['-h'])

    def _parser(self, parser, **kwargs):
        # return a "standard" parser.

        kwargs['help'] = self.help_msg
        kwargs['description'] = self.description
        kwargs['formatter_class'] = argparse.RawDescriptionHelpFormatter

        parser.__dict__.update(kwargs)

        return parser


class CommandError(RuntimeError):
    '''
    Indicates that a command failed.
    '''
    def __init__(self, returncode=1):
        super().__init__()
        self.returncode = returncode


class CommandContextError(CommandError):
    '''Indicates that a context-dependent command could not be run.'''


class ExtensionCommandError(CommandError):
    '''Exception class indicating an extension command was badly
    defined and could not be created.'''


    def __init__(self, **kwargs):
        self.hint = kwargs.pop('hint', None)
        super(ExtensionCommandError, self).__init__(**kwargs)

@dataclass
class _CmdFactory:

    py_file: str
    name: str
    attr: str

    def __call__(self):
        # Append the python file's directory to sys.path. This lets
        # its code import helper modules in a natural way.
        py_dir = os.path.dirname(self.py_file)
        sys.path.append(py_dir)

        # Load the module containing the command. Convert only
        # expected exceptions to ExtensionCommandError.
        try:
            mod = _commands_module_from_file(self.py_file, self.attr)
        except ImportError as i_e:
            raise ExtensionCommandError(
                hint=f'could not import {self.py_file}') from i_e

        # Get the attribute which provides the OebuildCommand subclass.
        try:
            cls = getattr(mod, self.attr)
        except AttributeError as a_e:
            raise ExtensionCommandError(
                hint=f'no attribute {self.attr} in {self.py_file}') from a_e

        # Create the command instance and return it.
        try:
            return cls()
        except Exception as e_p:
            raise ExtensionCommandError(
                hint='command constructor threw an exception') from e_p


@dataclass
class OebuildExtCommandSpec:
    '''
    An object which allows instantiating a oebuild extension.
    '''

    # Command name, as known to the user
    name: str

    description: str

    help: str

    # This returns a OebuildCommand instance when called.
    # It may do some additional steps (like importing the definition of
    # the command) before constructing it, however.
    factory: _CmdFactory


@dataclass
class ExtCommand:
    '''
    record extern command basic info, it's useful when app initialize
    '''
    name: str

    class_name: str

    path: str


def extension_commands(pre_dir, commandlist:OrderedDict):
    '''
    Get descriptions of available extension commands.
    The return value is an ordered map from project paths to lists of
    OebuildExtCommandSpec objects, for projects which define extension
    commands. The map's iteration order matches the manifest.projects
    order.
    '''
    specs = OrderedDict()
    for key, value in commandlist.items():
        specs[key] = _ext_specs(pre_dir, value)

    return specs


def _ext_specs(pre_dir, command_ext: ExtCommand):

    py_file = os.path.join(os.path.dirname(__file__), pre_dir, command_ext.path)

    factory = _CmdFactory(py_file=py_file, name=command_ext.name, attr=command_ext.class_name)

    return OebuildExtCommandSpec(
        name=command_ext.name,
        description=factory().description,
        help=factory().help_msg,
        factory=factory)


def _commands_module_from_file(file, mod_name):
    '''
    Python magic for importing a module containing oebuild extension
    commands. To avoid polluting the sys.modules key space, we put
    these modules in an (otherwise unpopulated) oebuild.commands.ext
    package.
    '''
    spec = importlib.util.spec_from_file_location(mod_name, file)
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    return mod
