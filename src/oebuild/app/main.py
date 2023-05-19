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
import argparse
import pathlib
import shutil
import textwrap
from io import StringIO
from collections import OrderedDict
import getpass

import colorama

import oebuild.util as oebuild_util
from oebuild.version import __version__
from oebuild.command import ExtCommand, extension_commands
from oebuild.m_log import logger

APP = "app"

class OebuildApp:
    '''
    The execution body of the oebuild tool, and all oebuild
    commands are resolved and executed by this body
    '''
    def __init__(self):
        self.base_oebuild_dir = oebuild_util.get_base_oebuild()
        self.oebuild_parser = None
        self.subparser_gen = None
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
            command_ext[app['name']] = ExtCommand(
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
            subparser = subparser_gen.add_parser(command_name, add_help=False)
            self.subparsers[command_name] = subparser

        # Save the instance state.
        self.oebuild_parser = oebuild_parser
        self.subparser_gen = subparser_gen

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

    def _run_extension(self, name, unknown):
        # Check a program invariant.
        self.cmd =self.command_spec[name].factory()

        parser = self.subparsers[name]
        args = self.cmd.add_parser(parser)

        self.cmd.run(args, unknown)


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
        self.oebuild_parser.print_help(top_level=True)


class OebuildHelpAction(argparse.Action):
    '''
    set argparse help is true
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        # Just mark that help was requested.
        namespace.help = True


class OebuildArgumentParser(argparse.ArgumentParser):
    '''
    The argparse module is infuriatingly coy about its parser and
    help formatting APIs, marking almost everything you need to
    customize help output an "implementation detail". Even accessing
    the parser's description and epilog attributes as we do here is
    technically breaking the rules.

    Even though the implementation details have been pretty stable
    since the module was first introduced in Python 3.2, let's avoid
    possible headaches by overriding some "proper" argparse APIs
    here instead of monkey-patching the module or breaking
    abstraction barriers. This is duplicative but more future-proof.
    '''

    def __init__(self, *args, **kwargs):
        # The super constructor calls add_argument(), so this has to
        # come first as our override of that method relies on it.
        self.oebuild_optionals = []
        self.oebuild_app = kwargs.pop('oebuild_app', None)
        super(OebuildArgumentParser, self).__init__(*args, **kwargs)

    def print_help(self, file=None, top_level=False):
        print(self.format_help(top_level=top_level), end='',
              file=file or sys.stdout)

    def format_help(self, top_level=False):
        # When top_level is True, we override the parent method to
        # produce more readable output, which separates commands into
        # logical groups. In order to print optionals, we rely on the
        # data available in our add_argument() override below.
        #
        # If top_level is False, it's because we're being called from
        # one of the subcommand parsers, and we delegate to super.

        if not top_level:
            return super(OebuildArgumentParser, self).format_help()

        # Format the help to be at most 75 columns wide, the maximum
        # generally recommended by typographers for readability.
        #
        # If the terminal width (COLUMNS) is less than 75, use width
        # (COLUMNS - 2) instead, unless that is less than 30 columns
        # wide, which we treat as a hard minimum.
        width = min(75, max(shutil.get_terminal_size().columns - 2, 30))

        with StringIO() as sio:

            def append(*strings):
                for s_t in strings:
                    print(s_t, file=sio)

            append(self.format_usage(),
                   self.description,
                   '')

            append('optional arguments:')
            for w_o in self.oebuild_optionals:
                self._format_oebuild_optional(append, w_o, width)

            append('')
            for _,command in self.oebuild_app.command_spec.items():
                self._format_command(append, command, width)

            if self.epilog:
                append(self.epilog)

            return sio.getvalue()

    def _format_oebuild_optional(self, append, w_o, width):
        metavar = w_o['metavar']
        options = w_o['options']
        help_msg = w_o.get('help')

        # Join the various options together as a comma-separated list,
        # with the metavar if there is one. That's our "thing".
        if metavar is not None:
            opt_str = '  ' + ', '.join(f'{o} {metavar}' for o in options)
        else:
            opt_str = '  ' + ', '.join(options)

        # Delegate to the generic formatter.
        self._format_thing_and_help(append, opt_str, help_msg, width)

    def _format_command(self, append, command, width):
        thing = f'  {command.name}:'
        self._format_thing_and_help(append, thing, command.help, width)

    def _format_extension_spec(self, append, spec, width):
        self._format_thing_and_help(append, '  ' + spec.name + ':',
                                   spec.help, width)

    def _format_thing_and_help(self, append, thing, help_msg, width):
        # Format help for some "thing" (arbitrary text) and its
        # corresponding help text an argparse-like way.
        help_offset = min(max(10, width - 20), 24)
        help_indent = ' ' * help_offset

        thinglen = len(thing)

        if help_msg is None:
            # If there's no help string, just print the thing.
            append(thing)
        else:
            # Reflow the lines in help to the desired with, using
            # the help_offset as an initial indent.
            help_msg = ' '.join(help_msg.split())
            help_lines = textwrap.wrap(help_msg, width=width,
                                       initial_indent=help_indent,
                                       subsequent_indent=help_indent)

            if thinglen > help_offset - 1:
                # If the "thing" (plus room for a space) is longer
                # than the initial help offset, print it on its own
                # line, followed by the help on subsequent lines.
                append(thing)
                append(*help_lines)
            else:
                # The "thing" is short enough that we can start
                # printing help on the same line without overflowing
                # the help offset, so combine the "thing" with the
                # first line of help.
                help_lines[0] = thing + help_lines[0][thinglen:]
                append(*help_lines)

    def add_argument(self, *args, **kwargs):
        # Track information we want for formatting help.  The argparse
        # module calls kwargs.pop(), so can't call super first without
        # losing data.
        optional = {'options': [], 'metavar': kwargs.get('metavar', None)}
        need_metavar = (optional['metavar'] is None and
                        kwargs.get('action') in (None, 'store'))
        for arg in args:
            if not arg.startswith('-'):
                break
            optional['options'].append(arg)
            # If no metavar was given, the last option name is
            # used. By convention, long options go last, so this
            # matches the default argparse behavior.
            if need_metavar:
                optional['metavar'] = arg.lstrip('-').translate(
                    {ord('-'): '_'}).upper()
        optional['help'] = kwargs.get('help')
        self.oebuild_optionals.append(optional)

        # Let argparse handle the actual argument.
        super().add_argument(*args, **kwargs)

    def error(self, message):
        # if (self.oebuild_app and
        #         self.oebuild_app.mle and
        #         isinstance(self.oebuild_app.mle,
        #                    ManifestVersionError) and
        #         self.oebuild_app.cmd):
        #     self.oebuild_app.cmd.die(mve_msg(self.west_app.mle))
        super().error(message=message)

def check_user():
    '''
    check execute user must in normal user
    '''
    if getpass.getuser() == "root":
        log.err("can not use oebuild in root")
        return False
    return True

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
