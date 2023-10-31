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

import argparse
import textwrap
import os
from shutil import copyfile

from docker.models.containers import Container
from oebuild.docker_proxy import DockerProxy
import oebuild.util as oebuild_util
from docker.errors import DockerException

from oebuild.command import OebuildCommand
from oebuild.m_log import logger, INFO_COLOR
from oebuild.parse_compile import ParseCompile,CheckCompileError
from oebuild.configure import Configure, ConfigBasicRepo, YOCTO_META_OPENEULER
from oebuild.parse_template import BaseParseTemplate, ParseTemplate, BUILD_IN_DOCKER, BUILD_IN_HOST
from oebuild.m_log import logger, INFO_COLOR
from oebuild.check_docker_tag import CheckDockerTag
from oebuild.app.plugins.deploy.deploy_in_container import InContainer
from oebuild.parse_env import ParseEnv

'''
The command for deploy specific platform, like qemu or other boards.
'''

class Deploy(OebuildCommand):

    def __init__(self):
        self.compile_conf_dir = os.path.join(os.getcwd(), 'compile.yaml')
        self.configure = Configure()
        self.client = DockerProxy()
        self.container_id = None

        super().__init__(
            'deploy',
            'Deploy for the platform',
            textwrap.dedent('''
            This command will deploy on target platform.
            ''')
        )

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [-p platform]
''')

        parser.add_argument('-p', dest='platform', default="aarch64",
            help='''
            this param is for arch. All possible choices: arm, aarch64, riscv64, x86_64
            '''
        )
        
        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        
        parse_compile = ParseCompile(self.compile_conf_dir)
        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            return
        args = args.parse_args(unknown)

        try:
            oebuild_util.check_docker()
        except DockerException as d_e:
            logger.error(str(d_e))
            return
        logger.info('Deploying QEMU......')
        _runqemu_command_backup = ( 
        "chmod a+x /etc/qemu-ifup"
        )
        parse_env = ParseEnv(env_dir='.env')
        in_container = InContainer(self.configure)
        
        timestamp_folder = self.get_timestamp_folder_name()
        if timestamp_folder:
            in_container.timestamp = timestamp_folder
        else:
            logger.error("No valid timestamp folder found in the output directory.")
        in_container.arch = args.platform
        # "chmod a+x /etc/qemu-ifup && "
        _runqemu_command=( 
        
        f"runqemu ./generated_conf.qemuboot.conf output/{in_container.timestamp}/openeuler-image-*-{in_container.arch}-{in_container.timestamp}.rootfs.cpio.gz qemuparams='-M virt-4.0 -cpu cortex-a57 ' nographic"
        )

        in_container.exec(parse_env=parse_env,
                          parse_compile=parse_compile,
                          command=_runqemu_command)
        
        logger.info("Deploy finished ...")

    def get_timestamp_folder_name(self):
        all_subdirectories = [d for d in os.listdir("./output/") if os.path.isdir(os.path.join("./output/", d))]

        if len(all_subdirectories) == 1 and all_subdirectories[0].isdigit():
            # logger.info(all_subdirectories[0])
            return all_subdirectories[0]
        else:
            return None





