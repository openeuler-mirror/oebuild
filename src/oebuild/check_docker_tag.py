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
import pathlib

from git import Repo

from oebuild.configure import Configure
import oebuild.util as oebuild_util

class CheckDockerTag:
    '''
    This class is used to synthesize the build environment
    parameters to obtain the docker image version that should
    be updated when building with OEBUILD, and these environment
    parameters are the docker_tag entered by the user, the env
    configuration file, the yocto branch name, etc. Judge down
    in turn, and finally return a suitable docker image version
    '''
    def __init__(self, docker_tag: str, configure: Configure):
        self.docker_tag = docker_tag
        self.configure = configure
        self.tag_list = []
        self._parse_docker_tag()

    def _parse_docker_tag(self,):
        oebuild_config = self.configure.parse_oebuild_config()
        docker_config = oebuild_config.docker
        tags = {}
        for tag in docker_config.tag_map.values():
            tags[tag] = True
        for key in tags:
            self.tag_list.append(key)

    def get_tags(self,):
        return self.tag_list

    def list_image_tag(self,):
        '''
        print compile docker image tag list
        '''
        oebuild_config = self.configure.parse_oebuild_config()
        docker_config = oebuild_config.docker
        log = f'''the openeuler embedded docker image repo url:
{docker_config.repo_url}
the openeuler embedded docker tag can be selected list:
'''
        for tag in self.tag_list:
            log += f"{tag}\n"
        print(log)

    def get_tag(self,) -> str:

        if self.docker_tag is not None and self.docker_tag != "":
            if self.docker_tag not in self.tag_list:
                return None
            else:
                return str(self.docker_tag)

        yocto_dir = self.configure.source_yocto_dir()
        env_path = os.path.join(yocto_dir,".oebuild/env.yaml")
        if os.path.exists(env_path):
            env_parse = oebuild_util.read_yaml(pathlib.Path(env_path))
            return str(env_parse['docker_tag'])

        yocto_repo = Repo.init(yocto_dir)
        oebuild_config = self.configure.parse_oebuild_config()
        docker_config = oebuild_config.docker
        if yocto_repo.active_branch.name in docker_config.tag_map:
            return str(docker_config.tag_map[yocto_repo.active_branch.name])

        return None
