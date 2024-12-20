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
import sys

from docker.errors import DockerException

from oebuild.command import OebuildCommand
from oebuild.configure import Configure
from oebuild.struct import CompileParam
from oebuild.parse_param import ParseCompileParam
from oebuild.parse_env import ParseEnv
import oebuild.util as oebuild_util
from oebuild.app.plugins.bitbake.in_container import InContainer
from oebuild.app.plugins.bitbake.in_host import InHost
from oebuild.m_log import logger, set_log_to_file
import oebuild.const as oebuild_const


class Bitbake(OebuildCommand):
    '''
    Bitbake instructions can enter the build interactive environment
    and then directly run bitbake-related instructions,or run bitbake
    command directly, for example: `oebuild bitbake busybox`
    '''

    help_msg = 'execute bitbake command'
    description = textwrap.dedent('''
            The bitbake command performs the build operation, and for the build environment,
            there are two types, one is to build in docker and the other is to build in the
            host. There are also two construction methods, one is to build directly, and the
            other is to call up the build environment to be operated freely by the user
            ''')

    def __init__(self):
        self.compile_conf_dir = os.path.join(os.getcwd(), 'compile.yaml')
        self.configure = Configure()

        super().__init__('bitbake', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''

  %(prog)s [command] [--with-docker-image]
  --with-docker-image
        that is pointed which docker image will be started, and the
        docker_param->image will be modified from compile.yaml
        the command example like:
            oebuild bitbake --with-docker-image=demo:latest
''')

        parser_adder.add_argument(
            'command',
            nargs='?',
            default=None,
            help='''The name of the directory that will be initialized''')

        return parser

    def do_run(self, args: argparse.ArgumentParser, unknown=None):
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
            sys.exit(0)
        set_log_to_file()

        oe_params, unknown = self._get_oebuild_param(unknown)
        command = self._get_command(unknow=unknown)

        if not self.check_support_bitbake():
            logger.error(
                "Please do it in compile workspace which contain compile.yaml")
            sys.exit(-1)

        if not os.path.exists('.env'):
            os.mknod('.env')

        compile_param_dict = oebuild_util.read_yaml(self.compile_conf_dir)
        compile_param: CompileParam = ParseCompileParam.parse_to_obj(
            compile_param_dict)
        compile_param = self._deal_oe_params(oe_params, compile_param)

        # if has manifest.yaml, init layer repo with it
        yocto_dir = os.path.join(self.configure.source_dir(),
                                 "yocto-meta-openeuler")
        manifest_path = os.path.join(yocto_dir, ".oebuild/manifest.yaml")
        if compile_param.no_layer is None or compile_param.no_layer is not True:
            if compile_param.cache_src_dir is not None:
                oebuild_util.sync_repo_from_cache(
                    repo_list=compile_param.repos,
                    src_dir=self.configure.source_dir(),
                    cache_src_dir=compile_param.cache_src_dir)
            oebuild_util.download_repo_from_manifest(
                repo_list=compile_param.repos,
                src_dir=self.configure.source_dir(),
                manifest_path=manifest_path)
        parse_env = ParseEnv(env_dir='.env')

        if compile_param.build_in == oebuild_const.BUILD_IN_HOST:
            in_host = InHost(self.configure)
            in_host.exec(compile_param=compile_param, command=command)
            # note: Use return instead of sys.exit because the command should exit the
            # function rather than terminating the entire process when it is done executing.
            return

        try:
            oebuild_util.check_docker()
        except DockerException as d_e:
            logger.error(str(d_e))
            sys.exit(-1)

        in_container = InContainer(self.configure)
        in_container.exec(parse_env=parse_env,
                          compile_param=compile_param,
                          command=command)

    def check_support_bitbake(self, ):
        '''
        The execution of the bitbake instruction mainly relies
        on compile.yaml, which is initialized by parsing the file
        '''
        return os.path.exists(os.path.join(os.getcwd(), 'compile.yaml'))

    def _get_command(self, unknow: list):
        if len(unknow) == 0:
            return None

        return 'bitbake ' + ' '.join(unknow)

    def _get_oebuild_param(self, unknow: list):
        if len(unknow) == 0:
            return [], []
        oe_params = []
        new_unknow = []
        for item in unknow:
            if item.startswith("--with-docker-image"):
                oe_params.append(item)
            else:
                new_unknow.append(item)
        return oe_params, new_unknow

    def _deal_oe_params(self, oe_params, compile_param: CompileParam):
        is_modify = False
        for item in oe_params:
            if item.startswith("--with-docker-image"):
                item_split = item.split("=")
                if len(item_split) < 2:
                    logger.error("the format is --with-docker-image=xxx:yyy")
                    sys.exit(-1)
                if compile_param.build_in == oebuild_const.BUILD_IN_DOCKER:
                    compile_param.docker_param.image = item_split[1]
                    is_modify = True
        if is_modify:
            oebuild_util.write_yaml(self.compile_conf_dir,
                                    ParseCompileParam().parse_to_dict(compile_param))
        return compile_param
