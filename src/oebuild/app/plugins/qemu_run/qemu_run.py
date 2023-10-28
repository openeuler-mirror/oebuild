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

from docker.errors import DockerException

from docker.models.containers import Container
from oebuild.docker_proxy import DockerProxy

from oebuild.command import OebuildCommand
from oebuild.configure import Configure
from oebuild.m_log import logger

class QemuRun(OebuildCommand):
    '''
    The command for run executable file under qemu.
    '''
    def __init__(self):
        self.compile_conf_dir = os.path.join(os.getcwd(), 'compile.yaml')
        self.configure = Configure()
        self.client = None
        self.container_id = None

        super().__init__(
            'qemu_run',
            'Qemu_run for the code file',
            textwrap.dedent('''
            This command will run executable file under qemu for openEuler platform.
            ''')
        )

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [-d target_directory] [-p platform]
''')

        parser.add_argument('-d', dest='target_directory', nargs='?', default=None,
            help='''
            Target file path
            '''
        )

        parser.add_argument('-p', dest='platform', default="aarch64",
            help='''
            this param is for arch. All possible choices: arm, aarch64, riscv64, x86_64
            '''
        )

        parser.add_argument('-m', dest='mode', default="user",
            help='''
            this param is for the mode for running qemu. All possible choices: user, system
            '''
        )

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            return
        # Parse the command-line arguments
        args = args.parse_args(unknown)

        try:
            self.client = DockerProxy()
        except DockerException:
            logger.error("please install docker first!!!")
            return

        if(args.target_directory) is None:
            logger.error('Please specify directory of the target file')
        self._check_file(args)
        self._init_docker()
        self._qemu_user_run(args)
        logger.info("qemu-run finished ...")

        self.container.stop()
        self.container.remove()

    def _check_file(self, args):
        file_path = args.target_directory
        if not os.path.exists(file_path):
            raise ValueError(f"The file '{file_path}' does not exist, please check again")
        else:
            self._target_file_name = os.path.basename(file_path)    # hello.c

    def _init_docker(self):
        logger.info("Docker for qemu starting ...")
        default_image = "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container:latest"
        if not self.client.is_image_exists(default_image):
            logger.error(f'''the docker image does not exists, please run fellow command:
        `oebuild update docker`''')
        self.container:Container = self.client.container_run_simple(image=default_image, volumes=[])
        # exec_result = self.container.exec_run("/bin/bash -c 'source /opt/buildtools/nativesdk/environment-setup-x86_64-pokysdk-linux; which qemu-aarch64'")
        # logger.info(exec_result)

    def _qemu_user_run(self, args):
        _qemu_target_file = args.target_directory
        _platform = args.platform
        container_target_dir = "./"
        logger.info("Target file copying into the docker ...")
        self.client.copy_to_container(
            container=self.container, 
            source_path=_qemu_target_file, 
            to_path=container_target_dir)
        # ls_command = f"/bin/sh -c ls"
        # exec_result = self.container.exec_run(ls_command)
        qemu_user_run_command = f"/bin/sh -c 'source /opt/buildtools/nativesdk/environment-setup-x86_64-pokysdk-linux; qemu-{_platform} {container_target_dir}{self._target_file_name}'"
        exec_result = self.container.exec_run(qemu_user_run_command)

        # 提取output内容并记录
        output = exec_result.output.decode('utf-8')
        logger.info(f"ExecResult(exit_code={exec_result.exit_code})")
        logger.info(f'''Output:
        ===================
        {output}''')

        # output_lines = exec_result.output.decode('utf-8').split('\n')
        # for line in output_lines:
        #     if "OUTPUT" in line:
        #         logger.info(line)
        #     else:
        #         logger.debug(line)  # 将其他信息输出为调试信息
