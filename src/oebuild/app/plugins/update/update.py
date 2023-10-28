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
import os
import textwrap
import sys
import pathlib

from docker.errors import DockerException

import oebuild.util as oebuild_util
from oebuild.command import OebuildCommand
from oebuild.parse_template import OebuildRepo
from oebuild.parse_compile import ParseCompile
from oebuild.configure import Configure, ConfigBasicRepo, YOCTO_META_OPENEULER
from oebuild.docker_proxy import DockerProxy
from oebuild.ogit import OGit
from oebuild.check_docker_tag import CheckDockerTag

from oebuild.m_log import logger

class Update(OebuildCommand):
    '''
    The update command will prepare the basic environment
    related to the build, such as container images, build base repositories, etc
    '''
    def __init__(self):
        self.configure = Configure()

        super().__init__(
            'update',
            'Update the basic environment required for the build',
            textwrap.dedent('''
            The update command will involve three areas, namely the build container, 
            yocto-meta-openeuler and the corresponding layers, if there are no parameters 
            after the update, it will be updated in order yocto-meta-openeuler, build 
            container and layers, the update of these three places is related, the update 
            of the build container will be affected by three factors, first, execute the 
            tag parameter, The container image related to the tag is updated, the second 
            identifies the build container image bound to the main build repository, in 
            yocto-meta-openeuler/.oebuild/env.yaml, the third identifies the branch 
            information of the main build repository, and identifies the type of build image 
            through the branch information of the main build repository. The layer update must 
            rely on yocto-meta-openeuler, if the main build repository does not exist will first 
            download the main build repository (the relevant git information is in .oebuild/config), 
            the layers update execution logic is different in different directories, if not in 
            the build directory will be parsed yocto-meta-openeuler/.oebuild/ common.yaml to get 
            the information that needs to be updated, and if it is in the build directory, it will 
            parse compile.yaml to get the updated information
            ''')
        )

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''
  %(prog)s [yocto docker layer] [-tag]
''')
        parser.add_argument('-tag','--tag', dest='docker_tag',
            help='''
            with platform will list support archs, with feature will list support features
            '''
        )

        parser.add_argument(
            'item', nargs='?', default=None,
            help='''The name of the directory that will be initialized''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown = None):
        '''
        update action rely on directory which has initd, so check it first
        '''
        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            return

        args = args.parse_args(unknown)

        if not self.configure.is_oebuild_dir():
            logger.error('your current directory had not finishd init')
            sys.exit(-1)

        # if args.list is not None:
        #     if args.list == "docker":
        #         self.list_image_tag()
        #     return

        update_yocto, update_docker, update_layer = False, False, False
        if args.item is None:
            update_yocto, update_docker, update_layer = True, True, True
        elif args.item == "yocto":
            update_yocto = True
        elif args.item == "docker":
            update_docker = True
        elif args.item == "layer":
            update_layer = True
        else:
            logger.error('please run oebuild update [yocto docker layer]')
            sys.exit(-1)


        if update_yocto:
            self.get_basic_repo()

        if update_docker:
            try:
                oebuild_util.check_docker()
                # check yocto/oebuild/env.yaml，get container_tag and update docker image
                self.docker_image_update(args.docker_tag)
            except DockerException as d_e:
                logger.error(str(d_e))
                return

        if update_layer:
            self.get_layer_repo()

    def get_layer_repo(self,):
        '''
        download or update layers that will be needed
        '''
        # check the main layer if exists
        yocto_dir = os.path.join(self.configure.source_dir(), "yocto-meta-openeuler")
        if not os.path.exists(yocto_dir):
            # update main layer
            self.get_basic_repo()
        # get rely layers from yocto-meta-openeuler/.oebuild/common.yaml when not in build directory
        # or <build-directory>/compile.yaml where in build directory
        repos = None
        if os.path.exists(os.path.join(os.getcwd(), "compile.yaml")):
            parse_compile = ParseCompile(compile_conf_dir=os.path.join(os.getcwd(), "compile.yaml"))
            repos = parse_compile.repos
        else:
            common_path = pathlib.Path(os.path.join(yocto_dir, ".oebuild/common.yaml"))
            repos = oebuild_util.read_yaml(yaml_dir=common_path)['repos']

        if repos is None:
            return
        for _ , item in repos.items():
            if isinstance(item, OebuildRepo):
                local_dir = os.path.join(self.configure.source_dir(), item.path)
                key_repo = OGit(repo_dir = local_dir,
                                remote_url = item.url,
                                branch = item.refspec)
            else:
                local_dir = os.path.join(self.configure.source_dir(), item['path'])
                key_repo = OGit(repo_dir = local_dir,
                                remote_url = item['url'],
                                branch = item['refspec'])
            key_repo.clone_or_pull_repo()

    def get_basic_repo(self,):
        '''
        note: get_basic_repo is to download or update basic repo in config
        which set in keys basic_repo, the rule is that when the
        embedded/src/yocto-meta-openeuler exists, so check whether its
        remote is equal or not with config's setting, if equal and run git
        pull else mv yocto-meta-openeuler to embedded/bak/yocto-meta-openeuler
        and rename yocto-meta-openeuler with a random string suffix. if
        embedded/src/yocto-meta-openeuler not exists, so just clone from config setting.
        '''
        oebuild_config = self.configure.parse_oebuild_config()
        yocto_config:ConfigBasicRepo = oebuild_config.basic_repo[YOCTO_META_OPENEULER]

        local_dir = os.path.join(self.configure.source_dir(), yocto_config.path)
        yocto_repo = OGit(repo_dir=local_dir,
                          remote_url=yocto_config.remote_url,
                          branch=yocto_config.branch)
        yocto_repo.clone_or_pull_repo()

    def docker_image_update(self, docker_tag = None):
        '''
        The container update logic is to update the corresponding tag 
        container image if tag is specified, otherwise it is determined 
        according to the yocto-meta-openeuler version branch in config, 
        and if the version branch does not correspond to it, it will enter 
        interactive mode, which is selected by the user
        '''
        oebuild_config = self.configure.parse_oebuild_config()
        docker_config = oebuild_config.docker

        check_docker_tag = CheckDockerTag(docker_tag=docker_tag,configure=self.configure)
        if check_docker_tag.get_tag() is None or check_docker_tag.get_tag() == "":
            check_docker_tag.list_image_tag()
            return

        docker_image = docker_config.repo_url + ":" + check_docker_tag.get_tag()
        client = DockerProxy()
        logger.info("pull %s ...", docker_image)
        client.pull_image_with_progress(docker_image)
        logger.info("finishd pull %s ...", docker_image)
