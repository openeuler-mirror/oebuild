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
from dataclasses import dataclass
import pathlib
from typing import Optional

import oebuild.util as oebuild_util
from oebuild.ogit import OGit
from oebuild.parse_template import PlatformTemplate, ParseTemplate, BUILD_IN_DOCKER

@dataclass
class Compile(PlatformTemplate):
    '''
    Compile is the parsed object of compile.yaml and is used to manipulate the build file
    '''
    toolchain_dir: Optional[str]

    nativesdk_dir: Optional[str]

    not_use_repos: bool

    build_in: str

    sstate_cache: Optional[str]

    sstate_dir: Optional[str]

    tmp_dir: Optional[str]

    docker_image: Optional[str]

class BaseParseCompileError(ValueError):
    '''
    parse compile basic error
    '''

class CheckCompileError(BaseParseCompileError):
    '''
    compile.yaml parse check faild error
    '''

class ParseCompile:
    '''
    This class is used to parse compile.yaml and
    download the relevant code repository
    '''
    def __init__(self, compile_conf_dir):
        '''
        The initialization operation is used to parse the compile.yaml
        file and perform a series of checks before parsing
        '''
        if not os.path.exists(compile_conf_dir):
            raise ValueError('compile.yaml is not exists')

        compile_conf_dir = pathlib.Path(compile_conf_dir)
        data = oebuild_util.read_yaml(compile_conf_dir)

        try:
            self.check_compile_conf(data=data)
        except Exception as e_p:
            raise e_p

        default_image = "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container:latest"
        self.compile = Compile(
            build_in=BUILD_IN_DOCKER if 'build_in' not in data else data['build_in'],
            platform=data['platform'],
            machine=data['machine'],
            toolchain_type=data['toolchain_type'],
            toolchain_dir=None if 'toolchain_dir' not in data else data['toolchain_dir'],
            nativesdk_dir=None if 'nativesdk_dir' not in data else data['nativesdk_dir'],
            sstate_cache=None if 'sstate_cache' not in data else data['sstate_cache'],
            sstate_dir=None if 'sstate_dir' not in data else data['sstate_dir'],
            tmp_dir=None if 'tmp_dir' not in data else data['tmp_dir'],
            not_use_repos=False if 'not_use_repos' not in data else data['not_use_repos'],
            repos=None if "repos" not in data else ParseTemplate.parse_oebuild_repo(data['repos']),
            local_conf=None if "local_conf" not in data else data['local_conf'],
            layers=None if "layers" not in data else data['layers'],
            docker_image=default_image if "docker_image" not in data else data['docker_image']
        )

    @property
    def build_in(self):
        '''
        return attr of buildin
        '''
        return self.compile.build_in

    @property
    def platform(self):
        '''
        return attr of platform
        '''
        return self.compile.platform

    @property
    def machine(self):
        '''
        return attr of machine
        '''
        return self.compile.machine

    @property
    def toolchain_type(self):
        '''
        return attr of toolchain_type
        '''
        return self.compile.toolchain_type

    @property
    def toolchain_dir(self):
        '''
        return attr of toolchain_dir
        '''
        return self.compile.toolchain_dir

    @property
    def nativesdk_dir(self):
        '''
        return attr of nativesdk_dir
        '''
        return self.compile.nativesdk_dir

    @property
    def local_conf(self):
        '''
        return attr of local_conf path
        '''
        return self.compile.local_conf

    @property
    def layers(self):
        '''
        return attr of layers
        '''
        return self.compile.layers

    @property
    def not_use_repos(self):
        '''
        return attr of not_use_repos
        '''
        return self.compile.not_use_repos

    @property
    def sstate_cache(self):
        '''
        return attr of sstate_cache
        '''
        return self.compile.sstate_cache

    @property
    def sstate_dir(self):
        '''
        return attr of sstate_cache
        '''
        return self.compile.sstate_dir

    @property
    def tmp_dir(self):
        '''
        return attr of tmp_dir
        '''
        return self.compile.tmp_dir

    @property
    def repos(self):
        '''
        return attr of repos
        '''
        return self.compile.repos
    
    @property
    def docker_image(self):
        '''
        return attr of docker_tag
        '''
        return self.compile.docker_image

    def check_with_version(self, base_dir, manifest_path):
        '''
        Download the repos set in compile.yaml based on the given base path
        '''
        manifest = None
        if os.path.exists(manifest_path):
            manifest = oebuild_util.read_yaml(pathlib.Path(manifest_path))['manifest_list']
        if not self.compile.not_use_repos:
            repos = self.compile.repos
            if repos is None:
                return
            for repo_local, repo in repos.items():
                repo_dir = os.path.join(base_dir, repo.path)
                if not os.path.exists(repo_dir):
                    repo_git = OGit(repo_dir=repo_dir, remote_url=repo.url, branch=repo.refspec)
                    repo_git.clone_or_pull_repo()
                if manifest is None:
                    continue
                if repo_local in manifest:
                    repo_git = OGit(repo_dir=repo_dir, remote_url=repo.url, branch=repo.refspec)
                    repo_item = manifest[repo_local]
                    repo_git.check_out_version(version=repo_item['version'])

    @staticmethod
    def check_compile_conf(data):
        '''
        Check whether the compile.yaml content is compliant
        '''

        keys = {
            "platform": "the key platform is None",
            "machine": "the key machine is None",
            "toolchain_type": "the key toolchain_type is None"
            }

        for key, value in keys.items():
            if key not in data:
                raise CheckCompileError(value)

        if "toolchain_dir" in data and data['toolchain_dir'] is not None:
            if not os.path.exists(data['toolchain_dir']):
                raise CheckCompileError(f"the toolchain_dir {data['toolchain_dir']} is not exist")

        if "repos" in data:
            for _, repo in data['repos'].items():
                required_keys = {
                    "url": "the key url is None", 
                    "path": "the key path is None", 
                    "refspec": "the key refspec is None"}
                for key, value in required_keys.items():
                    if key not in repo:
                        raise CheckCompileError(value)
                    