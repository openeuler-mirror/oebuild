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

from typing import Dict

from oebuild.struct import RepoParam, DockerParam, CompileParam, ToolchainParam, OebuildEnv
import oebuild.util as oebuild_util
import oebuild.const as oebuild_const


class ParseOebuildEnvParam:
    '''
    OebuildEnv:
        workdir: str
        openeuler_layer: RepoParam
        build_list: Optional[list]
    '''
    @staticmethod
    def parse_to_obj(oebuild_env_param_dict) -> OebuildEnv:
        '''
        parse dict to OebuildEnv
        '''
        return OebuildEnv(
            workdir=oebuild_env_param_dict['workdir'],
            openeuler_layer=(None if 'openeuler_layer' not in oebuild_env_param_dict else
                             ParseRepoParam.parse_to_obj(
                                 oebuild_env_param_dict['openeuler_layer'])),
            build_list=(None if 'build_list' not in oebuild_env_param_dict else
                        oebuild_env_param_dict['build_list'])
        )

    @staticmethod
    def parse_to_dict(oebuild_env_obj: OebuildEnv):
        '''
        parse OebuildEnv to dict
        '''
        return {
            "workdir": oebuild_env_obj.workdir,
            "openeuler_layer": oebuild_env_obj.openeuler_layer,
            "build_list": oebuild_env_obj.build_list
        }


class ParseRepoParam:
    '''
    RepoParam:
        remote_url: str
        version: str
    '''
    @staticmethod
    def parse_to_obj(repo_param_dict: Dict[str, str]) -> RepoParam:
        '''
        parse dict to RepoParam
        '''
        return RepoParam(
            remote_url=repo_param_dict['remote_url'],
            version=repo_param_dict['version']
        )

    @staticmethod
    def parse_to_dict(repo_param_obj: RepoParam) -> Dict[str, str]:
        '''
        parse RepoParam to dict
        '''
        return {
            "remote_url": repo_param_obj.remote_url,
            "version": repo_param_obj.version
        }


class ParseDockerParam:
    '''
    class DockerParam:
        image: str
        parameters: str
        volumns: list
        command: str
    '''
    @staticmethod
    def parse_to_obj(docker_param_dict: Dict) -> DockerParam:
        '''
        parse dict to DockerParam
        '''
        return DockerParam(
            image=docker_param_dict['image'],
            parameters=docker_param_dict['parameters'],
            volumns=docker_param_dict['volumns'],
            command=docker_param_dict['command']
        )

    @staticmethod
    def parse_to_dict(docker_param_obj: DockerParam):
        '''
        parse dict to DockerParam
        '''
        return {
            'image': docker_param_obj.image,
            'parameters': docker_param_obj.parameters,
            'volumns': docker_param_obj.volumns,
            'command': docker_param_obj.command
        }


class ParseCompileParam:
    '''
    CompileParam:
        build_in: str
        machine: str
        toolchain_type: str
        repos: Optional[list]
        layers: Optional[list]
        local_conf: Optional[LiteralScalarString]
        docker_param: DockerParam

        sstate_mirrors: Optional[str]
        sstate_dir: Optional[str]
        tmp_dir: Optional[str]

        toolchain_dir: Optional[str]
        llvm_toolchain_dir: Optional[str]
        nativesdk_dir: Optional[str]

    '''
    @staticmethod
    def parse_to_obj(compile_param_dict) -> CompileParam:
        '''
        The initialization operation is used to parse the compile.yaml
        file and perform a series of checks before parsing
        '''
        docker_param: DockerParam = None
        if "docker_param" in compile_param_dict and compile_param_dict['docker_param'] is not None:
            docker_param = ParseDockerParam.parse_to_obj(
                docker_param_dict=compile_param_dict['docker_param']
            )

        # for old version
        repos = []
        if "repos" in compile_param_dict:
            repos = oebuild_util.trans_dict_key_to_list(compile_param_dict['repos'])

        def get_value_from_dict(key, dictobj, default_value=None):
            if key not in dictobj:
                return default_value
            return dictobj[key]

        return CompileParam(
            build_in=get_value_from_dict('build_in',
                                         compile_param_dict,
                                         oebuild_const.BUILD_IN_DOCKER),
            machine=get_value_from_dict('machine', compile_param_dict, None),
            toolchain_type=get_value_from_dict('toolchain_type', compile_param_dict, None),
            toolchain_dir=get_value_from_dict('toolchain_dir', compile_param_dict, None),
            llvm_toolchain_dir=get_value_from_dict('llvm_toolchain_dir', compile_param_dict, None),
            nativesdk_dir=get_value_from_dict('nativesdk_dir', compile_param_dict, None),
            sstate_mirrors=get_value_from_dict('sstate_mirrors', compile_param_dict, None),
            sstate_dir=get_value_from_dict('sstate_dir', compile_param_dict, None),
            tmp_dir=get_value_from_dict('tmp_dir', compile_param_dict, None),
            repos=None if len(repos) == 0 else repos,
            local_conf=get_value_from_dict('local_conf', compile_param_dict, None),
            layers=get_value_from_dict('layers', compile_param_dict, None),
            docker_param=docker_param,
            bitbake_cmds=get_value_from_dict('bitbake_cmds', compile_param_dict, None))

    @staticmethod
    def parse_to_dict(compile_param: CompileParam):
        '''
        parse CompileParam obj to dict
        '''
        compile_obj = {}
        compile_obj['build_in'] = compile_param.build_in
        compile_obj['machine'] = compile_param.machine
        compile_obj['toolchain_type'] = compile_param.toolchain_type
        if compile_param.toolchain_dir is not None:
            compile_obj['toolchain_dir'] = compile_param.toolchain_dir
        if compile_param.llvm_toolchain_dir is not None:
            compile_obj['llvm_toolchain_dir'] = compile_param.llvm_toolchain_dir
        if compile_param.nativesdk_dir is not None:
            compile_obj['nativesdk_dir'] = compile_param.nativesdk_dir
        if compile_param.sstate_mirrors is not None:
            compile_obj['sstate_mirrors'] = compile_param.sstate_mirrors
        if compile_param.tmp_dir is not None:
            compile_obj['tmp_dir'] = compile_param.tmp_dir
        if compile_param.repos is not None:
            compile_obj['repos'] = compile_param.repos
        if compile_param.local_conf is not None:
            compile_obj['local_conf'] = compile_param.local_conf
        if compile_param.layers is not None:
            compile_obj['layers'] = compile_param.layers
        if compile_param.build_in == oebuild_const.BUILD_IN_DOCKER:
            compile_obj['docker_param'] = ParseDockerParam().parse_to_dict(
                compile_param.docker_param)
        if compile_param.bitbake_cmds is not None:
            compile_obj['bitbake_cmds'] = compile_param.bitbake_cmds

        return compile_obj


class ParseToolchainParam:
    '''
    ToolchainParam:
        config_list: Optional[list]
        docker_param: DockerParam
    '''
    @staticmethod
    def parse_to_obj(toolchain_param_dict) -> ToolchainParam:
        '''
        parse dict to RepoParam
        '''
        return ToolchainParam(
            kind=toolchain_param_dict['kind'],
            gcc_configs=None if 'gcc_configs' not in toolchain_param_dict
            else toolchain_param_dict['gcc_configs'],
            llvm_lib=None if 'llvm_lib' not in toolchain_param_dict
            else toolchain_param_dict['llvm_lib'],
            docker_param=ParseDockerParam.parse_to_obj(toolchain_param_dict['docker_param'])
        )

    @staticmethod
    def parse_to_dict(toolchain_param_obj: ToolchainParam):
        '''
        parse ToolchainParam to dict
        '''
        res = {"kind": toolchain_param_obj.kind}
        if toolchain_param_obj.kind == oebuild_const.GCC_TOOLCHAIN:
            res['gcc_configs'] = toolchain_param_obj.gcc_configs
        else:
            res['llvm_lib'] = toolchain_param_obj.llvm_lib
        res['docker_param'] = ParseDockerParam.parse_to_dict(toolchain_param_obj.docker_param)
        return res
