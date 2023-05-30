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

import importlib.util
import os
from dataclasses import dataclass
import sys

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
class _ExtCommand:
    '''
    record extern command basic info, it's useful when app initialize
    '''
    name: str

    class_name: str

    path: str


def get_spec(pre_dir, command_ext: _ExtCommand):
    '''
    xxx
    '''

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
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    return mod
