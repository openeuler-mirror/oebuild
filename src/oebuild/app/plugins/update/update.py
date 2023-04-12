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
import shutil

from docker.errors import DockerException

import oebuild.util as oebuild_util
from oebuild.command import OebuildCommand
from oebuild.configure import Configure, ConfigBasicRepo, YOCTO_META_OPENEULER
from oebuild.docker_proxy import DockerProxy
from oebuild.ogit import OGit

from oebuild.my_log import MyLog as log, INFO_COLOR

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
            Update the base environment required at build time, such as 
            updating the necessary docker images and yocto-meta-openeuler repositories
            ''')
        )

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''
  %(prog)s [-t docker_tag] [-l list] [-i ignore] [-e enable]
''')
        parser.add_argument('-t', dest = 'docker_tag',
            help='''specifying the -t parameter will update the corresponding docker image''')

        parser.add_argument('-l',dest = 'list',choices=['docker'],
            help='''specifying the -l parameter lists the specified modules''')

        parser.add_argument('-i', dest='ignore', choices=['docker', 'meta'], action='append',
            help='''
            specify the -i parameter to ignore the corresponding setting when updating, 
            when the -e parameter is used at the same time, the -i parameter no longer takes effect 
            '''
        )

        parser.add_argument('-e', dest='enable', choices=['docker', 'meta'], action='append',
            help='''
            specify the -e parameter to enable the corresponding setting when updating, 
            when the -e parameter is used at the same time, the -i parameter no longer takes effect
            '''
        )

        return parser

    def do_run(self, args: argparse.Namespace, unknown = None):
        '''
        update action rely on directory which has initd, so check it first
        '''
        args = args.parse_args(unknown)

        if not self.configure.is_oebuild_dir():
            log.err('your current directory had not finishd init')
            sys.exit(-1)

        if args.list is not None:
            if args.list == "docker":
                self.list_image_tag()
            return

        update_docker, update_meta = True, True
        if args.enable is not None:
            if "docker" not in args.enable:
                update_docker = False
            if "meta" not in args.enable:
                update_meta = False
        elif args.ignore is not None:
            if "docker" in args.ignore:
                update_docker = False
            if "meta" in args.ignore:
                update_meta = False

        if update_meta:
            self.get_basic_repo()

        if update_docker:
            try:
                oebuild_util.check_docker()
                self.docker_image_update(args.docker_tag)
            except DockerException as d_e:
                log.err(str(d_e))
                return

    def list_image_tag(self,):
        '''
        print compile docker image tag list
        '''
        oebuild_config = self.configure.parse_oebuild_config()
        docker_config = oebuild_config.docker
        log.info("the openeuler embedded docker image repo url:")
        log.info("    " + docker_config.repo_url)
        log.info("the openeuler embedded docker tag list:")
        for tag in docker_config.tag_map.values():
            log.info("    "+tag)

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
        yocto_config:ConfigBasicRepo = oebuild_config.basic_repo.get(YOCTO_META_OPENEULER)

        local_dir = os.path.join(self.configure.source_dir(), yocto_config.path)
        if os.path.exists(local_dir):
            remote_url, _ = OGit.get_repo_info(local_dir)
            if remote_url != yocto_config.remote_url:
                if not os.path.exists(self.configure.yocto_bak_dir()):
                    os.makedirs(self.configure.yocto_bak_dir())
                bak_dir = os.path.join(self.configure.yocto_bak_dir(),
                                       yocto_config.path + "_" + oebuild_util.get_time_stamp())
                log.warning(f"yocto-meta-openeuler remote is changed, \
                            bak yocto-meta-openeuler to {bak_dir}")
                shutil.move(local_dir, bak_dir)

        log.info(f"clone or pull {yocto_config.remote_url}:{yocto_config.branch} ...")
        yocto_repo = OGit(repo_dir=local_dir,
                          remote_url=yocto_config.remote_url,
                          branch=yocto_config.branch)
        yocto_repo.clone_or_pull_repo()
        log.info(f"clone or pull {yocto_config.remote_url}:{yocto_config.branch} finish")

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

        if docker_tag is not None and docker_tag not in docker_config.tag_map.values():
            warn_msg = "please select valid docker_tag follow list"
            log.warning(warn_msg)
            for tag in docker_config.tag_map.keys():
                log.warning(docker_config.tag_map.get(tag))
            return
        if docker_tag is None:
            basic_config = oebuild_config.basic_repo
            yocto_config: ConfigBasicRepo = basic_config.get(YOCTO_META_OPENEULER)
            if yocto_config.branch in docker_config.tag_map:
                docker_tag = docker_config.tag_map[yocto_config.branch]
            else:
                input_msg = "please select follow docker_tag:\n"
                key_list = []
                for index, key in enumerate(docker_config.tag_map):
                    input_msg += f"{index+1}, {docker_config.repo_url}:\
                        {docker_config.tag_map[key]}\n"
                    key_list.append(key)
                input_msg += "please enter index number(enter q will exit):"
                while True:
                    i = input(INFO_COLOR + input_msg)
                    if i == 'q':
                        sys.exit()

                    i = int(i)
                    if i <= 0 or i > len(key_list):
                        log.warning("enter wrong")
                        continue
                    docker_tag = docker_config.tag_map[key_list[i-1]]
                    break

        docker_image = docker_config.repo_url + ":" + docker_tag
        client = DockerProxy()
        log.info(f"pull {docker_image} ...")
        client.pull_image_with_progress(docker_image)
        log.info(f"finishd pull {docker_image} ...")
