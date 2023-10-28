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
import pathlib

from docker.errors import DockerException

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.configure import Configure
from oebuild.docker_proxy import DockerProxy
from oebuild.m_log import logger

class Clear(OebuildCommand):
    '''
    for some clear task
    '''

    def __init__(self):
        self.configure = Configure()
        self.client = None
        super().__init__(
            'clear',
            'clear someone which oebuild generate',
            textwrap.dedent('''\
            During the construction process using oebuild, a lot of temporary products
            will be generated, such as containers,so this command can remove unimportant
            products, such as containers
'''
        ))

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [docker]
''')

        parser.add_argument(
            'item', nargs='?', default=None,
            help='''The name of the directory that will be initialized''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown = None):
        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            return

        args = args.parse_args(unknown)

        if args.item == "docker":
            try:
                self.client = DockerProxy()
            except DockerException:
                logger.error("please install docker first!!!")
                return
            self.clear_docker()

    def clear_docker(self,):
        '''
        clear container
        '''
        # get all build directory and get .env from every build directory
        logger.info("clearing container, please waiting ...")
        env_list = []
        build_list = os.listdir(self.configure.build_dir())
        for build_dir in build_list:
            build_dir = os.path.join(self.configure.build_dir(), build_dir)
            if os.path.exists(os.path.join(build_dir,".env")):
                env_list.append(os.path.join(build_dir,".env"))

        # traversal every env file and get container_id, and then try to stop it and rm it
        for env in env_list:
            env_conf = oebuild_util.read_yaml(pathlib.Path(env))
            try:
                container_id = env_conf['container']['short_id']
                container = self.client.get_container(container_id=container_id)
                DockerProxy().stop_container(container=container)
                DockerProxy().delete_container(container=container)
                logger.info("delete container: %s successful",container.short_id)
            except:
                continue

        # get all container which name start with oebuild and delete it,
        # in case when user rm build directory then legacy container
        # containers = self.client.get_all_container()
        # for container in containers:
        #     container_name = str(container.attrs.get('Name')).lstrip("/")
        #     if container_name.startswith("oebuild_"):
        #         try:
        #             DockerProxy().stop_container(container=container)
        #             DockerProxy().delete_container(container=container)
        #             logger.info(f"delete container: {container.short_id} successful")
        #         except:
        #             continue

        logger.info("clear container finished")
