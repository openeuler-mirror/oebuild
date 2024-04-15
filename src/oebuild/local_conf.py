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
import re
import sys

import oebuild.util as oebuild_util
from oebuild.m_log import logger
import oebuild.const as oebuild_const
from oebuild.struct import CompileParam


class BaseLocalConf(ValueError):
    '''
    basic error about parse_template
    '''


class NativesdkNotExist(BaseLocalConf):
    '''
    nativesdk directory not exist
    '''


class NativesdkNotValid(BaseLocalConf):
    '''
    nativesdk directory not valid
    '''


def get_nativesdk_sysroot(nativesdk_dir=oebuild_const.NATIVESDK_DIR):
    '''
    return environment initialization shell, if nativesdk directory is not exists
    or can not find any initialization shell, raise error
    '''
    sysroot_dir = os.path.join(nativesdk_dir, "sysroots")
    if not os.path.isdir(nativesdk_dir):
        logger.error("the %s is not exists", nativesdk_dir)
        sys.exit(1)
    if not os.path.isdir(sysroot_dir):
        logger.error("the %s is not value", nativesdk_dir)
        sys.exit(1)
    # list items in nativesdk to find environment shell
    list_items = os.listdir(sysroot_dir)
    for item in list_items:
        ret = re.match("^(x86_64-)[a-zA-Z0-9]{1,}(-linux)$", item)
        if ret is not None:
            abs_path = os.path.join(sysroot_dir, item)
            if os.path.isdir(abs_path):
                return os.path.join("sysroots", item)
    logger.error("can not find any sysroots directory")
    sys.exit(1)


def match_and_add(new_str: str, content: str):
    '''
    math line in content when the new_str not exist and added
    '''
    for line in content.split('\n'):
        if new_str.strip() != line.strip():
            continue
        return content

    content = content + '\n'
    content = content + new_str
    content = content + '\n'
    return content


def match_and_replace(pre: str, new_str: str, content: str):
    '''
    math line in content when the new_str exist and replace
    '''
    for line in content.split('\n'):
        ret = re.match(f'^({pre})', line)
        if ret is None:
            continue
        return content.replace(line, new_str)

    content = content + '\n'
    content = content + new_str
    content = content + '\n'
    return content


class LocalConf:
    '''
    LocalConf corresponds to the local.conf configuration
    file, which can be modified by specifying parameters
    '''

    def __init__(self, local_conf_path: str):
        self.local_path = local_conf_path

    def update(self, compile_param: CompileParam, src_dir=None):
        '''
        update local.conf by ParseCompile
        '''
        if not os.path.exists(self.local_path):
            raise ValueError(f'{self.local_path} not exists')

        with open(self.local_path, 'r', encoding='utf-8') as r_f:
            content = r_f.read()

        pre_content = self._deal_other_local_param(compile_param=compile_param, src_dir=src_dir)

        compile_param.local_conf = f'{pre_content}\n{compile_param.local_conf}'
        self._add_content_to_local_conf(content=content, local_conf=compile_param.local_conf)

    def _deal_other_local_param(self, compile_param: CompileParam, src_dir):
        pre_content = ""
        # add MACHINE
        if compile_param.machine is not None:
            pre_content += f'MACHINE = "{compile_param.machine}"\n'

        # replace toolchain
        if compile_param.toolchain_dir is not None:
            if compile_param.build_in == oebuild_const.BUILD_IN_DOCKER:
                replace_toolchain_str = f'''
{compile_param.toolchain_type} = "{oebuild_const.NATIVE_GCC_DIR}"'''
            else:
                replace_toolchain_str = f'''
{compile_param.toolchain_type} = "{compile_param.toolchain_dir}"'''

            pre_content += replace_toolchain_str

        # replace nativesdk OPENEULER_SP_DIR
        if compile_param.build_in == oebuild_const.BUILD_IN_HOST:
            self.check_nativesdk_valid(compile_param.nativesdk_dir)
            if compile_param.nativesdk_dir is None:
                raise ValueError("please set nativesdk dir")
            nativesdk_sysroot = get_nativesdk_sysroot(compile_param.nativesdk_dir)
            nativesdk_sys_dir = os.path.join(compile_param.nativesdk_dir, nativesdk_sysroot)

            pre_content += f'{oebuild_const.NATIVESDK_DIR_NAME} = "{nativesdk_sys_dir}"\n'
            pre_content += f'{oebuild_const.OPENEULER_SP_DIR} = "{src_dir}"\n'

        # replace sstate_cache
        if compile_param.sstate_mirrors is not None:
            if os.path.islink(compile_param.sstate_mirrors):
                new_str = f"file://.* {compile_param.sstate_mirrors}/PATH;downloadfilename=PATH"
            else:
                if compile_param.build_in == oebuild_const.BUILD_IN_DOCKER:
                    new_str = f"file://.* file://{oebuild_const.SSTATE_MIRRORS}/PATH"
                else:
                    new_str = f"file://.* file://{compile_param.sstate_mirrors}/PATH"
            pre_content += f'{oebuild_const.SSTATE_MIRRORS} = "{new_str}"\n'

        # replace sstate_dir
        if compile_param.sstate_dir is not None:
            pre_content += f'{oebuild_const.SSTATE_DIR} = "{compile_param.sstate_dir}"\n'

        # replace tmpdir
        if compile_param.tmp_dir is not None:
            pre_content += f'{oebuild_const.TMP_DIR} = "{compile_param.tmp_dir}"\n'

        return pre_content

    def _add_content_to_local_conf(self, content, local_conf):
        user_content_flag = "#===========the content is user added=================="
        if user_content_flag not in content and local_conf != "":
            # check if exists remark sysmbol, if exists and replace it
            for line in local_conf.split('\n'):
                if line.startswith("#"):
                    r_line = line.lstrip("#").strip(" ")
                    content = content.replace(r_line, line)
            content += f"\n{user_content_flag}\n"
            content += local_conf

        with open(self.local_path, 'w', encoding="utf-8") as r_f:
            r_f.write(content)

    def check_nativesdk_valid(self, nativesdk_dir):
        '''
        Check whether the set nativesdk is valid, check whether
        the path exists, and then check whether the internal
        OECORE_NATIVE_SYSROOT variables are consistent with the set nativesdk
        '''
        if not os.path.exists(nativesdk_dir):
            raise NativesdkNotExist(f"nativesdk directory: {nativesdk_dir} not exist")

        nativesdk_environment_path = os.path.join(
            nativesdk_dir,
            oebuild_util.get_nativesdk_environment(nativesdk_dir))

        with open(nativesdk_environment_path, 'r', encoding='utf-8') as r_f:
            for line in r_f.readlines():
                line = line.strip('\n')
                if not line.startswith("export OECORE_NATIVE_SYSROOT="):
                    continue
                oecore_sysroot_dir = line.lstrip('export OECORE_NATIVE_SYSROOT=').strip('"')
                if not oecore_sysroot_dir.startswith(nativesdk_dir):
                    raise NativesdkNotValid(f"nativesdk directory: {nativesdk_dir} are not valid")
                return
