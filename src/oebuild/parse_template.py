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
import logging
import sys
from dataclasses import dataclass
from typing import Optional
import pathlib
import os

from ruamel.yaml.scalarstring import LiteralScalarString

import oebuild.util as oebuild_util
import oebuild.const as oebuild_const
from oebuild.struct import RepoParam


@dataclass
class Template:
    '''
    basic template for paltform and feature
    '''
    repos: Optional[list]

    layers: Optional[list]

    local_conf: Optional[LiteralScalarString]


@dataclass
class PlatformTemplate(Template):
    '''
    the object will be parsed by platform config
    '''
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

    def __init__(self, yocto_dir: str):
        self.yocto_dir = yocto_dir
        self.build_in = None
        self.platform_template = None
        self.feature_template = []
        self.platform = None

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
            repo_list = None
            if 'repos' in data:
                repo_list = oebuild_util.trans_dict_key_to_list(
                    self.parse_oebuild_repo(data['repos']))

            layers = None if 'layers' not in data else data['layers']
            local_conf = None if 'local_conf' not in data else data['local_conf']

            config_type = data['type']
            config_name = os.path.basename(config_dir)

            if config_type == oebuild_const.PLATFORM:
                if self.platform is None:
                    self.platform = os.path.splitext(config_name)[0].strip("\n")
                else:
                    logging.error("Only one platform is allowed")
                    sys.exit(-1)
                self.platform_template = PlatformTemplate(
                    machine=data['machine'],
                    toolchain_type=data['toolchain_type'],
                    repos=repo_list,
                    local_conf=None if local_conf is None else LiteralScalarString(local_conf),
                    layers=None if layers is None else layers)
                return

            if self.platform_template is None:
                raise PlatformNotAdd('please add platform template first')

            if self.platform is None:
                logging.error("Platform not specified")
                sys.exit(-1)

            support_arch = []
            if 'support' in data:
                support_arch = data['support'].split('|')
                if self.platform not in support_arch:
                    raise FeatureNotSupport(f'your arch is {self.platform},'
                                            ' the feature is not supported,'
                                            'please check your application '
                                            'support archs')

            self.feature_template.append(FeatureTemplate(
                feature_name=LiteralScalarString(os.path.splitext(config_name)[0]),
                repos=repo_list,
                support=support_arch,
                local_conf=None if local_conf is None else LiteralScalarString(local_conf),
                layers=None if layers is None else layers
            ))

        except Exception as e_p:
            raise e_p

    def get_default_generate_compile_conf_param(self,):
        '''
        return default generate_compile_conf param
        '''
        return {
            "nativesdk_dir": None,
            "toolchain_dir": None,
            "build_in": oebuild_const.BUILD_IN_DOCKER,
            "sstate_mirrors": None,
            "tmp_dir": None,
            "datetime": None,
            "is_disable_fetch": False,
            "docker_image": None,
            "src_dir": None,
            "compile_dir": None
        }

    def generate_compile_conf(self, param):
        '''
        param obj:
            nativesdk_dir=None,
            toolchain_dir=None,
            llvm_toolchain_dir=None
            build_in: str = oebuild_const.BUILD_IN_DOCKER,
            sstate_mirrors=None,
            tmp_dir=None,
            datetime=None,
            no_fetch=False,
            no_layer=False,
            docker_image: str = None,
            src_dir: str = None,
            compile_dir: str = None
        '''
        # first param common yaml
        if self.platform_template is None:
            raise PlatformNotAdd('please set platform template first')
        common_yaml_path = os.path.join(self.yocto_dir, '.oebuild', 'common.yaml')
        repos, layers, local_conf = parse_repos_layers_local_obj(common_yaml_path)

        if self.platform_template.repos is not None:
            repos.extend(oebuild_util.trans_dict_key_to_list(self.platform_template.repos))

        if self.platform_template.layers is not None:
            layers.extend(self.platform_template.layers)

        if self.platform_template.local_conf is not None:
            local_conf = LiteralScalarString(self.platform_template.local_conf + local_conf)

        for feature in self.feature_template:
            feature: FeatureTemplate = feature
            if feature.repos is not None:
                repos.extend(oebuild_util.trans_dict_key_to_list(feature.repos))
            if feature.layers is not None:
                layers.extend(feature.layers)

            if feature.local_conf is not None:
                local_conf = LiteralScalarString(feature.local_conf + '\n' + local_conf)

        if param['datetime'] is not None:
            datetime_str = LiteralScalarString(f'DATETIME = "{param["datetime"]}"')
            local_conf = LiteralScalarString(local_conf + '\n' + datetime_str)

        if param['no_fetch']:
            disable_fetch_str = LiteralScalarString('OPENEULER_FETCH = "disable"')
            local_conf = LiteralScalarString(local_conf + '\n' + disable_fetch_str)

        compile_conf = {}
        compile_conf['build_in'] = param['build_in']
        compile_conf['machine'] = self.platform_template.machine
        compile_conf['toolchain_type'] = self.platform_template.toolchain_type
        compile_conf = self._deal_non_essential_compile_conf_param(param, compile_conf)
        compile_conf['no_layer'] = param['no_layer']
        compile_conf['repos'] = repos
        compile_conf['local_conf'] = local_conf
        compile_conf['layers'] = layers

        if param['build_in'] == oebuild_const.BUILD_IN_HOST:
            return compile_conf

        compile_conf['docker_param'] = get_docker_param_dict(
            docker_image=param['docker_image'],
            dir_list={
                "src_dir": param['src_dir'],
                "compile_dir": param['compile_dir'],
                "toolchain_dir": param['toolchain_dir'],
                "llvm_toolchain_dir": param['llvm_toolchain_dir'],
                "sstate_mirrors": param['sstate_mirrors']
            }
        )

        return compile_conf

    def _deal_non_essential_compile_conf_param(self, param, compile_conf):
        if param['nativesdk_dir'] is not None:
            compile_conf['nativesdk_dir'] = param['nativesdk_dir']
        if param['toolchain_dir'] is not None:
            compile_conf['toolchain_dir'] = param['toolchain_dir']
        if param['llvm_toolchain_dir'] is not None:
            compile_conf['llvm_toolchain_dir'] = param['llvm_toolchain_dir']
        if param['sstate_mirrors'] is not None:
            compile_conf['sstate_mirrors'] = param['sstate_mirrors']
        if param['tmp_dir'] is not None:
            compile_conf['tmp_dir'] = param['tmp_dir']
        return compile_conf

    @staticmethod
    def parse_oebuild_repo(repos):
        '''
        parse repo json object to OebuildRepo
        '''
        repo_cict = {}
        print(repos)
        for name, repo in repos.items():
            repo_cict[name] = RepoParam(
                remote_url=repo['url'],
                version=repo['refspec'])

        return repo_cict


def get_docker_param_dict(docker_image, dir_list):
    '''
    transfer docker param to dict
    dir_list:
    src_dir
    compile_dir
    toolchain_dir
    llvm_toolchain_dir
    sstate_mirrors
    '''
    parameters = oebuild_const.DEFAULT_CONTAINER_PARAMS
    volumns = []
    volumns.append("/dev/net/tun:/dev/net/tun")
    if dir_list['src_dir'] is not None:
        volumns.append(dir_list['src_dir'] + ':' + oebuild_const.CONTAINER_SRC)
    if dir_list['compile_dir'] is not None:
        volumns.append(dir_list['compile_dir'] + ":" + os.path.join(
            oebuild_const.CONTAINER_BUILD, os.path.basename(dir_list['compile_dir'])))
    if dir_list['toolchain_dir'] is not None:
        volumns.append(dir_list['toolchain_dir'] + ":" + oebuild_const.NATIVE_GCC_DIR)
    if dir_list['llvm_toolchain_dir'] is not None:
        volumns.append(dir_list['llvm_toolchain_dir'] + ":" + oebuild_const.NATIVE_LLVM_DIR)
    if dir_list['sstate_mirrors'] is not None:
        volumns.append(dir_list['sstate_mirrors'] + ":" + oebuild_const.SSTATE_MIRRORS)

    docker_param = {}
    docker_param['image'] = docker_image
    docker_param['parameters'] = parameters
    docker_param['volumns'] = volumns
    docker_param['command'] = "bash"

    return docker_param


def parse_repos_layers_local_obj(common_yaml_path):
    '''
    parse from yaml to repos, layers and local
    '''
    if not os.path.exists(common_yaml_path):
        logging.error('can not find .oebuild/common.yaml in yocto-meta-openeuler')
        sys.exit(-1)
    data = oebuild_util.read_yaml(common_yaml_path)

    repos = []
    if 'repos' in data:
        repos.extend(oebuild_util.trans_dict_key_to_list(data['repos']))
    layers = []
    if 'layers' in data:
        layers.extend(data['layers'])
    local_conf = LiteralScalarString('')
    if 'local_conf' in data:
        local_conf += LiteralScalarString(data['local_conf'])
    return repos, layers, local_conf
