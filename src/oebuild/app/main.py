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
import os
import sys
import pathlib
from collections import OrderedDict
import pwd

import oebuild.util as oebuild_util
import oebuild.const as oebuild_const
from oebuild.m_log import logger
from oebuild.struct import CompileParam
from oebuild.parse_param import ParseOebuildEnvParam, ParseCompileParam
from oebuild.auto_completion import AutoCompletion
from oebuild.version import __version__
from oebuild.spec import get_spec, _ExtCommand
from oebuild.command import OebuildCommand
from oebuild.oebuild_parser import OebuildArgumentParser, OebuildHelpAction

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
            plugins_dir = pathlib.Path(self.base_oebuild_dir, 'app/conf', 'plugins.yaml')
            oebuild_plugins_path = os.path.expanduser('~') + '/.local/oebuild_plugins/'
            append_plugins_dir = pathlib.Path(oebuild_plugins_path, 'append_plugins.yaml')
            self.command_ext = self.get_command_ext(oebuild_util.read_yaml(plugins_dir)['plugins'])
            if os.path.exists(append_plugins_dir) \
                    and oebuild_util.read_yaml(append_plugins_dir):
                self.command_ext = self.get_command_ext(
                    oebuild_util.read_yaml(append_plugins_dir)['plugins'],
                    self.command_ext)
            self.command_spec = {}
        except Exception as e_p:
            raise e_p

    @staticmethod
    def get_command_ext(plugins: list, command_ext=None):
        '''
        return command information object
        '''
        if command_ext is None:
            command_ext = OrderedDict()
        for app in plugins:
            if 'status' not in app or app['status'] == 'enable':
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

    def _run_extension(self, name: str, unknown):
        # Check a program invariant.
        spec = self.command_spec[name]
        cmd: OebuildCommand = oebuild_util.get_instance(spec.factory)

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
    if pwd.getpwuid(os.getuid())[0] == "root":
        logger.error("can not use oebuild in root")
        return False
    return True


def extension_commands(pre_dir, commandlist: OrderedDict):
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


class QuickBuild():
    '''
    The build command will quickly generate the compile.yaml
    '''

    def __init__(self, build_yaml_path):
        self.app = OebuildApp()
        self.build_yaml_path = pathlib.Path(build_yaml_path)
        self.oebuild_env = None
        self.build_data = None

    def _check_yaml(self,):
        if not os.path.exists(self.build_yaml_path.absolute()):
            logger.error("%s is not exists!", self.build_yaml_path)
            sys.exit(-1)
        data = oebuild_util.read_yaml(yaml_path=self.build_yaml_path)
        self.build_data = data
        if "oebuild_env" not in data:
            logger.error("%s is not valid", self.build_yaml_path.name)
            sys.exit(-1)
        self.oebuild_env = ParseOebuildEnvParam().parse_to_obj(data['oebuild_env'])

    def run(self):
        '''
        Execute oebuild commands in order.
        '''
        self._check_yaml()

        self.do_init()

        self.do_update_layer()

        self.do_build_list()

    def do_init(self, ):
        '''
        Execute oebuild command : oebuild init [directory] [-u yocto_remote_url] [-b branch]
        '''
        argv = [
            'init',
        ]
        try:
            data = oebuild_util.read_yaml(yaml_path=self.build_yaml_path)
            # get openeuler repo param
            if 'openeuler_layer' in data:
                argv.append("-u")
                argv.append(self.oebuild_env.openeuler_layer.remote_url)

                argv.append("-b")
                argv.append(self.oebuild_env.openeuler_layer.version)
            argv.append(self.oebuild_env.workdir)
        except Exception as e_p:
            raise e_p
        self.app.run(argv or sys.argv[1:])

    def do_update_layer(self, ):
        '''
        Execute oebuild command : oebuild update [yocto docker layer] [-tag]
        '''
        argv = [
            'update',
            'layer'
        ]
        os.chdir(self.oebuild_env.workdir)
        self.app.run(argv or sys.argv[1:])

    def do_build_list(self,):
        '''
        Build sequentially from the given compile parameter list.
        '''
        for build_name in self.oebuild_env.build_list:
            self._generate_and_bitbake(build_name=build_name)

    def _generate_and_bitbake(self, build_name):
        '''
        Execute oebuild command : oebuild generate
        '''
        if build_name not in self.build_data:
            logger.error("lack %s dict data in %s", build_name, self.build_yaml_path)
            sys.exit(-1)
        compile_param_dict = self.build_data[build_name]
        compile_param = ParseCompileParam().parse_to_obj(compile_param_dict=compile_param_dict)
        self._generate(compile_param=compile_param, build_name=build_name)
        compile_dir = os.path.join(self.oebuild_env.workdir, "build", build_name)
        self._bitbake(
            bitbake_cmds=compile_param.bitbake_cmds,
            compile_dir=compile_dir,
            build_in=compile_param.build_in)

    def _generate(self, compile_param: CompileParam, build_name):
        # check compile if exists, if exists, exit with -1
        compile_dir = os.path.join(self.oebuild_env.workdir, "build", build_name)
        if os.path.exists(compile_dir):
            logger.error("%s has exists", compile_dir)
            sys.exit(-1)

        if compile_param.build_in == oebuild_const.BUILD_IN_DOCKER:
            if compile_param.docker_param is None:
                logger.error("param is error, build in docker need docker_param")
                sys.exit(-1)
            # check src and compile_dir if exists
            src_volumn_flag = False
            compile_volumn_flag = False
            for volumn in compile_param.docker_param.volumns:
                volumn_split = volumn.split(":")
                if oebuild_const.CONTAINER_SRC == volumn_split[1].strip(" "):
                    src_volumn_flag = True
                if volumn_split[1].strip(" ").startswith(oebuild_const.CONTAINER_BUILD):
                    compile_volumn_flag = True
            if not src_volumn_flag:
                compile_param.docker_param.volumns.append(
                    f"{self.oebuild_env.workdir}/src:{oebuild_const.CONTAINER_SRC}"
                )
            if not compile_volumn_flag:
                compile_param.docker_param.volumns.append(
                    f"{compile_dir}:{oebuild_const.CONTAINER_BUILD}/{build_name}"
                )
        compile_param_dict = ParseCompileParam().parse_to_dict(compile_param=compile_param)
        os.makedirs(compile_dir)
        compile_yaml_path = os.path.join(compile_dir, "compile.yaml")
        oebuild_util.write_yaml(yaml_path=compile_yaml_path, data=compile_param_dict)

    def _bitbake(self, bitbake_cmds, compile_dir, build_in):
        os.chdir(compile_dir)
        if build_in == oebuild_const.BUILD_IN_DOCKER:
            self._update_docker()
        for bitbake_cmd in bitbake_cmds:
            bitbake_cmd: str = bitbake_cmd.strip(" ")
            argv = [
                'bitbake',
                bitbake_cmd.lstrip("bitbake")
            ]
            self.app.run(argv or sys.argv[1:])

    def _update_docker(self,):
        '''
        Execute oebuild command : oebuild update [yocto docker layer] [-tag]
        '''
        argv = [
            'update',
            'docker'
        ]
        self.app.run(argv or sys.argv[1:])


def main(argv=None):
    '''
    oebuild main entrypoint
    '''
    if not check_user():
        return

    AutoCompletion().run()
    if (len(sys.argv) > 1) and 'yaml' in sys.argv[1]:
        build = QuickBuild(build_yaml_path=sys.argv[1])
        build.run()
    else:
        app = OebuildApp()
        app.run(argv or sys.argv[1:])


if __name__ == "__main__":
    main()
