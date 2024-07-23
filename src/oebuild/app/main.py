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
from shutil import rmtree

import oebuild.util as oebuild_util
import oebuild.const as oebuild_const
from oebuild.m_log import logger
from oebuild.parse_param import ParseCompileParam
from oebuild.configure import Configure
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
            prog='oebuild',
            description='''The openEuler Embedded meta-tool. you can directly run
oebuild <path_build.yaml> in oebuild workspace to perform the build, for example:

oebuild <path_compile.yaml>
            ''',
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
        self.compile_param = None
        self.workdir = None
        self.build_dir = None

    def _check_yaml(self,):
        if not os.path.exists(self.build_yaml_path.absolute()):
            logger.error("%s is not exists!", self.build_yaml_path)
            sys.exit(-1)
        data = oebuild_util.read_yaml(yaml_path=self.build_yaml_path)
        compile_param = ParseCompileParam().parse_to_obj(compile_param_dict=data)
        self.compile_param = compile_param

    def run(self):
        '''
        Execute oebuild commands in order.
        '''
        if not Configure().is_oebuild_dir():
            logger.error('Your current directory is not oebuild workspace')
            sys.exit(-1)
        self.workdir = Configure().oebuild_topdir()

        self._check_yaml()
        if "compile.yaml" in os.listdir():
            self.build_dir = os.path.basename(os.getcwd())
        else:
            build_name = self.build_yaml_path.name.replace(".yaml", "").replace(".yml", "")
            self.build_dir = os.path.basename(build_name)

        self.generate()

        self.bitbake()

    def generate(self):
        '''
        xxx
        '''
        # judge if exist src/yocto-meta-openeuler, one-click function need yocto-meta-openeuler
        if not os.path.exists(Configure().source_yocto_dir()):
            logger.error("""
please clone yocto-meta-openeuler in src directory, you can exec as follows steps:

    oebuild update yocto
or
    cd src
    git clone <remote-yocto>

""")
            sys.exit(-1)

        os.makedirs(Configure().build_dir(), exist_ok=True)
        os.chdir(Configure().build_dir())
        self._init_build_dir()
        if self.compile_param.build_in == oebuild_const.BUILD_IN_DOCKER:
            if self.compile_param.docker_param is None:
                logger.error("param is error, build in docker need docker_param")
                sys.exit(-1)
            # check src and compile_dir if exists
            src_volumn_flag = False
            compile_volumn_flag = False
            for volumn in self.compile_param.docker_param.volumns:
                volumn_split = volumn.split(":")
                if oebuild_const.CONTAINER_SRC == volumn_split[1].strip(" "):
                    src_volumn_flag = True
                if volumn_split[1].strip(" ").startswith(oebuild_const.CONTAINER_BUILD):
                    compile_volumn_flag = True
            if not src_volumn_flag:
                self.compile_param.docker_param.volumns.append(
                    f"{self.workdir}/src:{oebuild_const.CONTAINER_SRC}"
                )
            if not compile_volumn_flag:
                volumn_dir = os.path.join(oebuild_const.CONTAINER_BUILD,
                                          os.path.basename(self.build_dir))
                self.compile_param.docker_param.volumns.append(
                    f"{os.path.abspath(self.build_dir)}:{volumn_dir}"
                )
        compile_param_dict = ParseCompileParam().parse_to_dict(compile_param=self.compile_param)
        compile_yaml_path = os.path.join(self.build_dir, "compile.yaml")
        oebuild_util.write_yaml(yaml_path=compile_yaml_path, data=compile_param_dict)

    def _init_build_dir(self):
        # check compile if exists, if exists, exit with -1
        if os.path.exists(self.build_dir):
            build_dir = self.build_dir
            logger.warning("the build directory %s already exists", build_dir)
            while True:
                in_res = input(f"""
    do you want to overwrite it({os.path.basename(build_dir)})? the overwrite action
    will replace the compile.yaml or toolchain.yaml to new and delete conf directory,
    enter Y for yes, N for no, C for create:""")
                if in_res not in ["Y", "y", "yes", "N", "n", "no", "C", "c", "create"]:
                    print("""
    wrong input""")
                    continue
                if in_res in ['N', 'n', 'no']:
                    sys.exit(0)
                if in_res in ['C', 'c', 'create']:
                    in_res = input("""
    please enter now build name, we will create it under build directory:""")
                    build_dir = os.path.join(Configure().build_dir(), in_res)
                    if os.path.exists(build_dir):
                        continue
                break
            self.build_dir = build_dir
            if os.path.exists(os.path.join(self.build_dir, "conf")):
                rmtree(os.path.join(self.build_dir, "conf"))
            elif os.path.exists(self.build_dir):
                rmtree(self.build_dir)
        os.makedirs(self.build_dir, exist_ok=True)

    def bitbake(self):
        '''
        xxx
        '''
        os.chdir(os.path.abspath(self.build_dir))
        if self.compile_param.bitbake_cmds is None:
            print("================================================\n\n"
                  "please enter follow directory for next steps!!!\n\n"
                  f"{os.path.abspath(self.build_dir)}\n\n"
                  "================================================\n")
            return
        for bitbake_cmd in self.compile_param.bitbake_cmds:
            bitbake_cmd: str = bitbake_cmd.strip(" ")
            argv = [
                'bitbake',
                bitbake_cmd.lstrip("bitbake")
            ]
            self.app.run(argv or sys.argv[1:])
        logger.info("""
======================================================================
Please enter the building directory according to the command prompt below:

    cd %s
""", os.path.dirname(os.path.abspath(self.build_dir)))


def main(argv=None):
    '''
    oebuild main entrypoint
    '''
    if not check_user():
        return

    # the auto compiletion will be disabled, when get more good idea and enable it
    # AutoCompletion().run()
    if (len(sys.argv) > 1) and 'yaml' in sys.argv[1]:
        build = QuickBuild(build_yaml_path=sys.argv[1])
        build.run()
    else:
        app = OebuildApp()
        app.run(argv or sys.argv[1:])


if __name__ == "__main__":
    main()
