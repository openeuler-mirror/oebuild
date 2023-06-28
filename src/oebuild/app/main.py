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

import sys
import pathlib
from collections import OrderedDict
import getpass

import colorama

import oebuild.util as oebuild_util
from oebuild.version import __version__
from oebuild.spec import get_spec,_ExtCommand
from oebuild.command import OebuildCommand
from oebuild.m_log import logger
from oebuild.oebuild_parser import OebuildArgumentParser,OebuildHelpAction

APP = "app"

class OebuildApp:
    '''
    The execution body of the oebuild tool, and all oebuild
    commands are resolved and executed by this body
    '''
    def __init__(self):
        self.base_oebuild_dir = oebuild_util.get_base_oebuild()
        self.oebuild_parser = None
        self.subparsers = {}
        self.cmd = None
        try:
            plugins_dir = pathlib.Path(self.base_oebuild_dir,'app/conf','plugins.yaml')
            self.command_ext = self.get_command_ext(oebuild_util.read_yaml(plugins_dir)['plugins'])
            self.command_spec = {}
        except Exception as e_p:
            raise e_p

    @staticmethod
    def get_command_ext(plugins:list):
        '''
        return command information object
        '''
        command_ext = OrderedDict()
        for app in plugins:
            command_ext[app['name']] = _ExtCommand(
                name=app['name'],
                class_name=app['class'],
                path=app['path'])
        return command_ext


    def _load_extension_specs(self, ):
        self.command_spec = extension_commands(APP, self.command_ext)


    def _setup_parsers(self):
        # Set up and install command-line argument parsers.

        oebuild_parser, subparser_gen = self.make_parsers()

        # Add sub-parsers for the command_ext commands.
        for command_name in self.command_ext:
            self.subparsers[command_name] = subparser_gen.add_parser(command_name, add_help=False)

        # Save the instance state.
        self.oebuild_parser = oebuild_parser

    def make_parsers(self,):
        '''
        Make a fresh instance of the top level argument parser
        and subparser generator, and return them in that order.
        The prog='oebuild' override avoids the absolute path of the
        main.py script showing up when West is run via the wrapper
        '''

        parser = OebuildArgumentParser(
            prog='oebuild', description='The openEuler Embedded meta-tool.',
            epilog='''Run "oebuild <command> -h" for help on each <command>.''',
            add_help=False, oebuild_app=self
        )

        parser.add_argument('-h', '--help', action=OebuildHelpAction, nargs=0,
                            help='get help for oebuild or a command')

        parser.add_argument('-v', '--version', action='version',
                            version=f'Oebuild version: v{__version__}',
                            help='print the program version and exit')

        subparser_gen = parser.add_subparsers(metavar='<command>',
                                              dest='command')

        return parser, subparser_gen


    def _check_command(self, args):
        if args.help or \
            args.command is None or \
            args.command not in self.command_ext or \
            args.command == 'help':
            self.help()
            return False

        return True


    def run_command(self, argv):
        '''
        Parse command line arguments and run the OebuildCommand.
        If we're running an extension, instantiate it from its
        spec and re-parse arguments before running.
        '''
        args, unknown = self.oebuild_parser.parse_known_args(args=argv)

        if not self._check_command(args=args):
            return

        # Finally, run the command.
        self._run_extension(args.command, unknown)

    def _run_extension(self, name:str, unknown):
        # Check a program invariant.
        spec = self.command_spec[name]
        cmd:OebuildCommand = oebuild_util.get_instance(spec.factory)

        parser = self.subparsers[name]

        args = cmd.add_parser(parser_adder=parser)

        cmd.run(args, unknown)

    def run(self, argv):
        '''
        the function will be exec first
        '''
        self._load_extension_specs()
        # Set up initial argument parsers. This requires knowing
        # self.extensions, so it can't happen before now.
        self._setup_parsers()

        # OK, we are all set. Run the command.
        self.run_command(argv)

    def help(self,):
        '''
        print help message
        '''
        self.oebuild_parser.print_help()

def check_user():
    '''
    check execute user must in normal user
    '''
    if getpass.getuser() == "root":
        logger.error("can not use oebuild in root")
        return False
    return True

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
        specs[key] = get_spec(pre_dir, value)

    return specs

def main(argv=None):
    '''
    oebuild main entrypoint
    '''
    if not check_user():
        return

    colorama.init()
    app = OebuildApp()
    app.run(argv or sys.argv[1:])

if __name__ == "__main__":
    main()
