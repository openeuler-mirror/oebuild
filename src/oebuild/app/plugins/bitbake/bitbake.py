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
import argparse
import textwrap

from oebuild.command import OebuildCommand
from oebuild.configure import Configure
from oebuild.parse_compile import ParseCompile, CheckCompileError
from oebuild.parse_env import ParseEnv
import oebuild.util as oebuild_util
from oebuild.app.plugins.bitbake.in_container import InContainer
from oebuild.app.plugins.bitbake.in_host import InHost
from oebuild.parse_template import BUILD_IN_HOST
from oebuild.m_log import logger
from docker.errors import DockerException

class Bitbake(OebuildCommand):
    '''
    Bitbake instructions can enter the build interactive environment
    and then directly run bitbake-related instructions,or run bitbake
    command directly, for example: `oebuild bitbake busybox`
    '''
    def __init__(self):
        self.compile_conf_dir = os.path.join(os.getcwd(), 'compile.yaml')
        self.configure = Configure()

        super().__init__(
            'bitbake',
            'execute bitbake command',
            textwrap.dedent('''
            The bitbake command performs the build operation, and for the build environment, 
            there are two types, one is to build in docker and the other is to build in the 
            host. There are also two construction methods, one is to build directly, and the 
            other is to call up the build environment to be operated freely by the user
            ''')
        )

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [command]
''')

        parser_adder.add_argument(
            'command', nargs='?', default=None,
            help='''The name of the directory that will be initialized''')

        return parser

    def do_run(self, args: argparse.ArgumentParser, unknown = None):
        '''
        The BitBake execution logic is:
        the first step is to prepare the code that initializes
        the environment dependency,
        the second step to build the configuration file to the object,
        the third step to handle the container needed for compilation,
        and the fourth step to enter the build environment
        '''
        if '-h' in unknown or '--help' in unknown:
            self.print_help_msg()
            return

        command = self._get_command(unknow=unknown)

        if not self.check_support_bitbake():
            logger.error("please do it in compile workspace which contain compile.yaml")
            return

        if not os.path.exists('.env'):
            os.mknod('.env')

        try:
            parse_compile = ParseCompile(self.compile_conf_dir)
        except CheckCompileError as c_e:
            logger.error(str(c_e))
            return

        # if has manifest.yaml, init layer repo with it
        yocto_dir = os.path.join(self.configure.source_dir(), "yocto-meta-openeuler")
        manifest_path = os.path.join(yocto_dir, ".oebuild/manifest.yaml")
        parse_compile.check_with_version(self.configure.source_dir(), manifest_path=manifest_path)
        parse_env = ParseEnv(env_dir='.env')

        if parse_compile.build_in == BUILD_IN_HOST:
            in_host = InHost(self.configure)
            in_host.exec(parse_compile=parse_compile, command=command)
            return
        try:
            oebuild_util.check_docker()
        except DockerException as d_e:
            logger.error(str(d_e))
            return
        in_container = InContainer(self.configure)
        in_container.exec(parse_env=parse_env,
                          parse_compile=parse_compile,
                          command=command)

    def check_support_bitbake(self,):
        '''
        The execution of the bitbake instruction mainly relies
        on compile.yaml, which is initialized by parsing the file
        '''
        return os.path.exists(os.path.join(os.getcwd(), 'compile.yaml'))

    def _get_command(self, unknow: list):
        if len(unknow) == 0:
            return None

        return 'bitbake ' + ' '.join(unknow)
