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

from typing import Optional
from dataclasses import dataclass
import pathlib
import sys

import oebuild.util as oebuild_util
from oebuild.m_log import logger


@dataclass
class EnvContainer:
    '''
    the container object in env object
    '''
    short_id: Optional[str]


@dataclass
class Env:
    '''
    the env object
    '''
    container: Optional[EnvContainer]


class ParseEnv:
    '''
    This class is used to parse env.yaml and
    update env.yaml
    '''

    def __init__(self, env_dir):
        self.env_dir = pathlib.Path(env_dir) if isinstance(env_dir, str) else env_dir
        self.env: Env = Env(container=None)
        self._parse_env()

    @property
    def container(self):
        '''
        return container object
        '''
        return self.env.container

    def _parse_env(self):
        '''
        parse env.yaml to env object
        '''
        data = oebuild_util.read_yaml(self.env_dir)
        if data is None:
            return

        if "container" in data:
            env_container = data['container']
            try:
                self.env.container = EnvContainer(
                    short_id=env_container['short_id']
                )
            except KeyError:
                logger.error(".env parse error, please check it")
                sys.exit(-1)

    def set_env_container(self, env_container: EnvContainer):
        '''
        set ParseEnv's container object
        '''
        self.env.container = env_container

    def export_env(self):
        '''
        export env object to env.yaml
        '''
        data = {}
        if self.env.container is not None:
            container = self.env.container
            data['container'] = {
                'short_id': container.short_id
            }

        oebuild_util.write_yaml(pathlib.Path(self.env_dir), data=data)

    @staticmethod
    def check_env_container(env_container):
        '''
        Check that the env.yaml content is compliant
        '''
        if "remote" not in env_container:
            raise ValueError("the key remote is lack")

        if "branch" not in env_container:
            raise ValueError("the key branch is lack")

        if "short_id" not in env_container:
            raise ValueError("the key short_id is lack")

        if "volumns" not in env_container:
            raise ValueError("the key volumns is lack")
