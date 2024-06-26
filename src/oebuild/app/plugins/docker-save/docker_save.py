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
import sys
import textwrap
import os

from docker.errors import APIError

from oebuild.command import OebuildCommand
from oebuild.configure import Configure
from oebuild.m_log import logger
from oebuild.parse_env import ParseEnv
from oebuild.docker_proxy import DockerProxy


class DockerSave(OebuildCommand):
    '''
    This class is designed to rapidly generate a customized container image, aiming
    to address scenarios where the compilation environment has been specially tailored
    but reuse of the container environment is required.
    '''

    help_msg = 'help to save a docker image'
    description = textwrap.dedent('''
            This is designed to rapidly generate a customized container image, aiming
            to address scenarios where the compilation environment has been specially tailored
            but reuse of the container environment is required.
            ''')

    def __init__(self):
        self.configure = Configure()
        self.client = DockerProxy()
        super().__init__('docker-save', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''
  %(prog)s [docker-image]
''')

        # Secondary command
        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        # perpare parse help command
        if '-h' in unknown:
            unknown[0] = '-h'
            self.pre_parse_help(args, unknown)
            sys.exit(1)
        docker_image = unknown[0]
        docker_image_split = docker_image.split(":")
        if len(docker_image_split) != 2:
            logger.error("the docker image format is repository:tag,"
                         "should be set like openeuler:latest")
            sys.exit(-1)

        if not self.configure.is_oebuild_dir():
            logger.error('Your current directory had not finished init')
            sys.exit(-1)

        if ".env" not in os.listdir():
            # the command must run based on .env file
            logger.error("dcommand need .env to get container id"
                         "so you must run it in compile directory")
            sys.exit(-1)
        env_obj = ParseEnv(env_dir=".env")
        if not self.client.is_container_exists(env_obj.container.short_id):
            logger.error("the container id: %s is not exist in .env")
            sys.exit(-1)

        container = self.client.get_container(env_obj.container.short_id)
        logger.info("the docker image %s is generatting ...", docker_image)
        try:
            container.commit(docker_image_split[0], docker_image_split[1])
        except APIError:
            logger.error("save %s failed")
            sys.exit(-1)
        logger.info("the new docker image %s is generated", docker_image)
