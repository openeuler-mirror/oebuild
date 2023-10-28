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

from dataclasses import dataclass
from typing import Dict, Optional
import pathlib
import os

from ruamel.yaml.scalarstring import LiteralScalarString

import oebuild.util as oebuild_util

PLATFORM = 'platform'
BUILD_IN_DOCKER = "docker"
BUILD_IN_HOST = "host"

@dataclass
class OebuildRepo:
    '''
    object repo is to record template repo info, repo struct is:
    repo_name:
        url: str
        path: str
        refspec: str
    object repo transfer string to struct to use it next easily
    '''

    repo_name: str

    url: str

    path: str

    refspec: str

@dataclass
class Template:
    '''
    basic template for paltform and feature
    '''
    repos: Optional[Dict[str, 'OebuildRepo']]

    layers: Optional[list]

    local_conf: Optional[LiteralScalarString]

@dataclass
class PlatformTemplate(Template):
    '''
    the object will be parsed by platform config
    '''
    platform: LiteralScalarString

    machine: LiteralScalarString

    toolchain_type: LiteralScalarString

@dataclass
class FeatureTemplate(Template):
    '''
    the object will be parsed by feature config
    '''
    feature_name: LiteralScalarString

    support: list

class BaseParseTemplate(ValueError):
    '''
    basic error about parse_template
    '''

class ConfigPathNotExists(BaseParseTemplate):
    '''
    config path not exists
    '''

class PlatformNotAdd(BaseParseTemplate):
    '''
    platform not add first
    '''

class FeatureNotSupport(BaseParseTemplate):
    '''
    feature not support
    '''

class CommonNotFound(BaseParseTemplate):
    '''
    common param not found
    '''

class ParseTemplate:
    '''
    ParseTemplate is to add platform template and feature template and export compile.yaml finially
    '''
    def __init__(self, yocto_dir:str):
        self.yocto_dir = yocto_dir
        self.build_in = None
        self.platform_template = None
        self.feature_template = []

    def add_template(self, config_dir):
        '''
        this method is to add Template, note: the template has two type for board and application,
        and the deal is difference, when adding board template it will set board_template as the
        board_template unset, or replace as the board_template had setted. but feature_template
        will append to feature_template anywhere, the feature_template adding must after
        board_templiate, else throw exception
        '''
        if not isinstance(config_dir, pathlib.Path):
            config_dir = pathlib.Path(config_dir)
        if not os.path.exists(config_dir):
            raise ConfigPathNotExists(f'{config_dir} is not exists')

        try:
            data = oebuild_util.read_yaml(config_dir)
            repo_dict = None if 'repos' not in data else self.parse_oebuild_repo(data['repos'])

            layers = None if 'layers' not in data else data['layers']
            local_conf = None if 'local_conf' not in data else data['local_conf']

            config_type = data['type']
            config_name = os.path.basename(config_dir)
            if config_type == PLATFORM:
                self.platform_template = PlatformTemplate(
                    platform=LiteralScalarString(os.path.splitext(config_name)[0]),
                    machine=data['machine'],
                    toolchain_type=data['toolchain_type'],
                    repos=repo_dict,
                    local_conf=None if local_conf is None else LiteralScalarString(local_conf),
                    layers=None if layers is None else layers)
                return

            if self.platform_template is None:
                raise PlatformNotAdd('please add platform template first')

            support_arch = []
            if 'support' in data:
                support_arch = data['support'].split('|')
                if self.platform_template.platform not in support_arch:
                    raise FeatureNotSupport(f'your arch is {self.platform_template.platform}, \
                                            the feature is not supported, please check your \
                                            application support archs')

            self.feature_template.append(FeatureTemplate(
                feature_name=LiteralScalarString(os.path.splitext(config_name)[0]),
                repos=repo_dict,
                support=support_arch,
                local_conf=None if local_conf is None else LiteralScalarString(local_conf),
                layers=None if layers is None else layers
            ))

        except Exception as e_p:
            raise e_p

    def generate_template(self,
                          nativesdk_dir = None,
                          toolchain_dir = None,
                          build_in: str = BUILD_IN_DOCKER,
                          sstate_cache = None,
                          tmp_dir = None,
                          datetime = None,
                          is_disable_fetch = False,
                          docker_image = ""):
        '''
        first param common yaml
        '''
        common_yaml_dir = os.path.join(self.yocto_dir, '.oebuild', 'common.yaml')
        if not os.path.exists(common_yaml_dir):
            raise CommonNotFound('can not find .oebuild/common.yaml in yocto-meta-openeuler')

        if self.platform_template is None:
            raise PlatformNotAdd('please set platform template first')

        common_yaml_dir = pathlib.Path(common_yaml_dir)
        data = oebuild_util.read_yaml(common_yaml_dir)
        data['docker_image'] = docker_image

        repos = {}
        if 'repos' in data :
            repos.update(data['repos'])
        layers = []
        if 'layers' in data:
            layers.extend(data['layers'])
        local_conf = LiteralScalarString('')
        if 'local_conf' in data:
            local_conf += LiteralScalarString(data['local_conf'])

        if self.platform_template.repos is not None:
            for repo_name, oebuild_repo in self.platform_template.repos.items():
                if repo_name in repos:
                    continue
                repos[repo_name] = {
                    'url': oebuild_repo.url,
                    'path': oebuild_repo.path,
                    'refspec': oebuild_repo.refspec
                }

        if self.platform_template.layers is not None:
            self.platform_template.layers.extend(layers)
            layers = self.platform_template.layers

        if self.platform_template.local_conf is not None:
            local_conf = LiteralScalarString(self.platform_template.local_conf + local_conf )

        for feature in self.feature_template:
            feature:FeatureTemplate = feature
            if feature.repos is not None:
                for repo_name, oebuild_repo in feature.repos.items():
                    if repo_name in repos:
                        continue
                    repos[repo_name] = {
                        'url': oebuild_repo.url,
                        'path': oebuild_repo.path,
                        'refspec': oebuild_repo.refspec
                    }
            if feature.layers is not None:
                layers.extend(feature.layers)

            if feature.local_conf is not None:
                local_conf = LiteralScalarString(feature.local_conf + '\n' + local_conf)

        if datetime is not None:
            datetime_str = LiteralScalarString(f'DATETIME = "{datetime}"')
            local_conf = LiteralScalarString(local_conf + '\n' + datetime_str)

        if is_disable_fetch:
            disable_fetch_str = LiteralScalarString('OPENEULER_FETCH = "disable"')
            local_conf = LiteralScalarString(local_conf + '\n' + disable_fetch_str)

        compile_conf = {
            'build_in': build_in,
            'docker_image': docker_image,
            'platform': self.platform_template.platform,
            'machine': self.platform_template.machine,
            'toolchain_type': self.platform_template.toolchain_type}

        if nativesdk_dir is not None:
            compile_conf['nativesdk_dir'] = nativesdk_dir
        if toolchain_dir is not None:
            compile_conf['toolchain_dir'] = toolchain_dir
        if sstate_cache is not None:
            compile_conf['sstate_cache'] = sstate_cache
        if tmp_dir is not None:
            compile_conf['tmp_dir'] = tmp_dir

        compile_conf['repos'] = repos
        compile_conf['local_conf'] = local_conf
        compile_conf['layers'] = layers

        return compile_conf

    @staticmethod
    def parse_oebuild_repo(repos):
        '''
        parse repo json object to OebuildRepo
        '''
        repo_cict = {}
        for name, repo in repos.items():
            repo_cict[name] = OebuildRepo(
                repo_name=name,
                url=repo['url'],
                path=repo['path'],
                refspec=repo['refspec'])

        return repo_cict
