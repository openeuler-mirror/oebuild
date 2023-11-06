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
from typing import Dict, Optional, Union
import pathlib
from dataclasses import dataclass

import oebuild.util as oebuild_util

PathType = Union[str, os.PathLike]

YOCTO_META_OPENEULER = "yocto_meta_openeuler"
YOCTO_POKY = "yocto-poky"
CONFIG = "config"
COMPILE_YAML = "compile.yaml.sample"

class OebuildNotFound(RuntimeError):
    '''Neither the current directory nor any parent has a oebuild workspace.'''


@dataclass
class ConfigContainer:
    '''
    container object in config
    '''
    # repo_url is for container's repo url
    repo_url: str

    # tag_mag is for branch to container tag map
    tag_map: Dict

@dataclass
class ConfigBasicRepo:
    '''
    basic repo object in config
    '''
    # path is for repo's path that will downloaded
    path: str

    # remote url is for repo's remote url
    remote_url: str

    # branch is for repo's branch
    branch: str

@dataclass
class Config:
    '''
    config object container docker and basic_repo
    '''
    docker: ConfigContainer

    basic_repo: dict

class Configure:
    '''
    Configure object is to contain some generally param or function about oebuild
    '''

    @staticmethod
    def oebuild_topdir(start: Optional[PathType] = None,
                fall_back: bool = True):
        '''
        Like oebuild_dir(), but returns the path to the parent directory of the .oebuild/
        directory instead, where project repositories are stored
        '''
        cur_dir = pathlib.Path(start or os.getcwd())

        while True:
            if (cur_dir / '.oebuild').is_dir():
                return os.fspath(cur_dir)

            parent_dir = cur_dir.parent
            if cur_dir == parent_dir:
                # At the root. Should we fall back?
                if fall_back:
                    return Configure.oebuild_topdir(fall_back=False)

                raise OebuildNotFound('Could not find a oebuild workspace '
                                'in this or any parent directory')
            cur_dir = parent_dir

    @staticmethod
    def oebuild_dir(start: Optional[PathType] = None):
        '''Returns the absolute path of the workspace's .oebuild directory.

        Starts the search from the start directory, and goes to its
        parents. If the start directory is not specified, the current
        directory is used.

        Raises OebuildNotFound if no .oebuild directory is found.
        '''
        return os.path.join(Configure.oebuild_topdir(start), '.oebuild')

    @staticmethod
    def is_oebuild_dir():
        '''
        Determine whether OEBuild is initialized
        '''
        try:
            Configure.oebuild_topdir()
            return True
        except OebuildNotFound:
            return False

    @staticmethod
    def source_dir():
        '''
        returns src directory base on topdir, the openEuler Embedded meta layers
        will be in here when you run oebuild update
        '''
        return os.path.join(Configure.oebuild_topdir(), 'src')

    @staticmethod
    def source_yocto_dir():
        '''
        return src/yocto-meta-openeuler path
        '''
        config = Configure.parse_oebuild_config()
        basic_config = config.basic_repo
        yocto_config:ConfigBasicRepo = basic_config[YOCTO_META_OPENEULER]
        yocto_dir = yocto_config.path
        return os.path.join(Configure.source_dir(), yocto_dir)

    @staticmethod
    def source_poky_dir():
        '''
        return src/yocto-poky path
        '''
        return os.path.join(Configure.source_dir(), YOCTO_POKY)

    @staticmethod
    def yocto_bak_dir():
        '''
        returns yocto_bak directory base on topdir, the openEuler Embedded meta layers
        will be in here when you run oebuild update
        '''
        return os.path.join(Configure.oebuild_topdir(), 'yocto_bak')

    @staticmethod
    def build_dir():
        '''
        returns build absolute path which the build result will be in
        '''
        return os.path.join(Configure.oebuild_topdir(), 'build')

    @staticmethod
    def env_dir():
        '''
        returns env path
        '''
        return os.path.join(Configure.build_dir(), '.env')

    @staticmethod
    def parse_oebuild_config():
        '''
        just parse oebuild config and return a json object,
        the file path is {WORKSPACE}.oebuild/config
        '''

        config = oebuild_util.read_yaml(yaml_dir = pathlib.Path(Configure.oebuild_dir(), CONFIG))

        tag_map = {}
        for key, value in config['docker']['tag_map'].items():
            tag_map[key] = value
        docker_config = ConfigContainer(repo_url=config['docker']['repo_url'], tag_map=tag_map)

        basic_config = {}
        for key, repo in config['basic_repo'].items():
            basic_config[key] = ConfigBasicRepo(path=repo['path'],
                                                remote_url=repo['remote_url'],
                                                branch=repo['branch'])

        config = Config(docker=docker_config, basic_repo=basic_config)

        return config

    @staticmethod
    def update_oebuild_config(config: Config):
        '''
        update {WORKSPACE}/.oebuild/config
        '''
        data = {}

        docker_config = config.docker
        data['docker'] = {}
        data['docker']['repo_url'] = docker_config.repo_url
        tag_map = {}
        for key, value in docker_config.tag_map.items():
            tag_map[key] = value
        data['docker']['tag_map'] = tag_map

        basic_config = config.basic_repo
        data['basic_repo'] = {}
        for key, repo in basic_config.items():
            repo:ConfigBasicRepo = repo
            data['basic_repo'][key] = {'path': repo.path,
                                       'remote_url': repo.remote_url,
                                       'branch': repo.branch}

        try:
            oebuild_util.write_yaml(yaml_dir = pathlib.Path(Configure.oebuild_dir(), CONFIG),
                                    data=data)
            return True
        except TypeError:
            return False
