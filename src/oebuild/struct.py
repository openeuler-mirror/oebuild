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
from typing import Optional
from ruamel.yaml.scalarstring import LiteralScalarString


@dataclass
class RepoParam:
    '''
    object repo is to record template repo info, repo struct is:
    repo_name:
        url: str
        refspec: str
    object repo transfer string to struct to use it next easily
    '''
    remote_url: str
    version: str


@dataclass
class OebuildEnv:
    '''
    xxx
    '''
    workdir: str
    openeuler_layer: RepoParam
    build_list: Optional[list]


@dataclass
class DockerParam:
    '''
    DockerParam defines the various parameters required for container startup
    '''
    # point out the docker image
    image: str
    # point out the parameter for create container
    parameters: str
    # point out the volumns for create container
    volumns: list[str]
    # point out the command for create container
    command: str


@dataclass
class CompileLocalParam:
    '''
    xxx
    '''
    sstate_mirrors: Optional[str]
    sstate_dir: Optional[str]
    tmp_dir: Optional[str]


@dataclass
class CompileParamComm:
    '''
    xxx
    '''
    build_in: str
    machine: str
    toolchain_type: str
    repos: Optional[list]
    layers: Optional[list]
    local_conf: Optional[LiteralScalarString]
    docker_param: DockerParam


@dataclass
class CompileParamHost:
    '''
    xxx
    '''
    toolchain_dir: Optional[str]
    nativesdk_dir: Optional[str]


@dataclass
class CompileParam(CompileParamComm, CompileLocalParam, CompileParamHost):
    '''
    Compile is the parsed object of compile.yaml and is used to manipulate the build file
    '''


@dataclass
class ToolchainParam:
    '''
    xxx
    '''
    config_list: Optional[list]
    docker_param: DockerParam
