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

class Compile(OebuildCommand):
    '''
    The command for cross-compile, configure runtime environment, run code and output results.
    '''
    def __init__(self):
        self.compile_conf_dir = os.path.join(os.getcwd(), 'compile.yaml')
        self.configure = Configure()
        self.client = None
        self.container_id = None
        self.dir_platform = None
        self.chain_platform = None

        super().__init__(
            'cross-compile',
            'Cross-compile for the code file',
            textwrap.dedent('''
            This command will perform cross-compile the c or cpp file for openEuler platform.
            ''')
        )

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [-d source_directory] [-p platform]
''')

        parser.add_argument('-d', dest='source_directory', nargs='?', default=None,
            help='''
            Source file path
            '''
        )

        parser.add_argument('-p', dest='platform', default="aarch64",
            help='''
            this param is for arch. All possible choices: arm, aarch64, riscv64, x86_64
            '''
        )

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):

        #logger.info(args)
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

        if(args.source_directory) is None:
            logger.error('Please specify directory of the source file')
        self.dir_platform, self.chain_platform = self._check_platform(args)
        self._check_file(args)
        self.cross_compile(cross_compile_dir_target_file = args.source_directory)

    def cross_compile(self, cross_compile_dir_target_file):
        '''
        for cross compile task
        '''
        logger.info("cross-compilation starting ...")

        default_image = "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container:latest"

        container_target_dir = "./"
        _final_dir_platform = self.dir_platform
        _final_chain_platform = self.chain_platform

        # parse_compile = ParseCompile(self.compile_conf_dir)
        if not self.client.is_image_exists(default_image):
            logger.error(f'''the docker image does not exists, please run fellow command:
        `oebuild update docker`''')
        container:Container = self.client.container_run_simple(image=default_image, volumes=[])

        logger.info("cross-compilation copying into the docker ...")
        self.client.copy_to_container(
            container=container, 
            source_path=cross_compile_dir_target_file, 
            to_path=container_target_dir)

        environment_var = {
            "PATH": f"/usr1/openeuler/gcc/openeuler_gcc_{_final_dir_platform}/bin:/usr1/openeuler/gcc:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        }

        # Compile inside the docker
        logger.info("cross-compilation gonna run inside the docker ...")
            
        compile_command = f"/bin/sh -c '{_final_chain_platform}-{self._tool_chain_type} -o {container_target_dir}{self._target_base_name} {container_target_dir}{self._target_file_name} -static'"
        exec_result = container.exec_run(compile_command, environment = environment_var)
        # logger.info(exec_result)

        logger.info("cross-compilation copying file from docker to host ...")
        # copy compiled file from container to host
        output_file = "./"  # output to ./
        self.client.copy_from_container(
            container=container, 
            from_path=f"{container_target_dir}{self._target_base_name}", 
            dst_path=output_file)

        logger.info("cross-compilation finished!")
        container.stop()
        container.remove()

    def _check_file(self, args):
        file_path = args.source_directory
        if not os.path.exists(file_path):
            raise ValueError(f"The file '{file_path}' does not exist, please check again")
        else:
            self._target_file_name = os.path.basename(file_path)    # hello.c
            self._target_base_name = os.path.splitext(self._target_file_name)[0]    # hello
            self._target_extension_name = self._target_file_name.split('.')[-1]    # c

            if self._target_extension_name == "c":
                self._tool_chain_type = "gcc"
            elif self._target_extension_name == "cpp":
                self._tool_chain_type = "g++"
            else:
                raise ValueError(f"The extension name of file '{self._target_extension_name}' is wrong, only c or cpp are supported")


    def _check_platform(self, args):
        if args.platform == "arm":
            _dir_platform = "arm32le"
            _chain_platform = "arm-openeuler-linux-gnueabi"
        elif args.platform == "aarch64":
            _dir_platform = "arm64le"
            _chain_platform = "aarch64-openeuler-linux-gnu"
        elif args.platform == "riscv64":
            _dir_platform = "riscv64"
            _chain_platform = "riscv64-openeuler-linux-gnu"
        elif args.platform == "x86_64":
            _dir_platform = "x86_64"
            _chain_platform = "x86_64-openeuler-linux-gnu"
        else:
            raise ValueError(f"such platform '{args.platform}' does not exist, please check again")
        return _dir_platform, _chain_platform
