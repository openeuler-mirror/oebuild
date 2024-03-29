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

from oebuild.parse_compile import ParseCompile
import oebuild.util as oebuild_util
from oebuild.m_log import logger
import oebuild.const as oebuild_const


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


# pylint:disable=[R0914,R0911,R0912,R0915]
class LocalConf:
    '''
    LocalConf corresponds to the local.conf configuration
    file, which can be modified by specifying parameters
    '''

    def __init__(self, local_conf_dir: str):
        self.local_dir = local_conf_dir

    def update(self, parse_compile: ParseCompile, src_dir=None):
        '''
        update local.conf by ParseCompile
        '''
        local_dir = self.local_dir
        if not os.path.exists(local_dir):
            raise ValueError(f'{local_dir} not exists')

        if parse_compile.local_conf is None:
            return

        with open(local_dir, 'r', encoding='utf-8') as r_f:
            content = r_f.read()

        # replace machine
        content = match_and_replace(
            pre='MACHINE ',
            new_str=f'MACHINE = "{parse_compile.machine}"',
            content=content)

        if parse_compile.machine == 'sdk':
            build_dir = re.search('.*(?=build)', self.local_dir)
            if not build_dir:
                logger.error('build_dir is not exists !')
                sys.exit(-1)
            change_conf = (build_dir.group() +
                           '/src/yocto-meta-openeuler/.oebuild/nativesdk/local.conf')
            if not os.path.exists(change_conf):
                logger.error('local.conf is not exists !')
                sys.exit(-1)

            with open(change_conf, 'r', encoding='utf-8') as change_conf:
                change_lines = change_conf.readlines()
            for change_line in change_lines:
                pre = change_line.replace('#', '').strip() if '#' in change_line else change_line
                content = match_and_replace(
                    pre=pre,
                    new_str=change_line,
                    content=content)

        # replace toolchain
        if parse_compile.toolchain_dir is not None:
            if parse_compile.build_in == oebuild_const.BUILD_IN_DOCKER:
                replace_toolchain_str = f'''
{parse_compile.toolchain_type} = "{oebuild_const.NATIVE_GCC_DIR}"'''
            else:
                replace_toolchain_str = f'''
{parse_compile.toolchain_type} = "{parse_compile.toolchain_dir}"'''
            content = match_and_replace(
                pre=parse_compile.toolchain_type,
                new_str=replace_toolchain_str,
                content=content
            )

        # replace nativesdk OPENEULER_SP_DIR
        if parse_compile.build_in == oebuild_const.BUILD_IN_HOST:
            self.check_nativesdk_valid(parse_compile.nativesdk_dir)
            if parse_compile.nativesdk_dir is None:
                raise ValueError("please set nativesdk dir")
            nativesdk_sysroot = get_nativesdk_sysroot(parse_compile.nativesdk_dir)
            nativesdk_sys_dir = os.path.join(parse_compile.nativesdk_dir, nativesdk_sysroot)
            content = match_and_replace(
                pre=oebuild_const.NATIVESDK_DIR_NAME,
                new_str=f'{oebuild_const.NATIVESDK_DIR_NAME} = "{nativesdk_sys_dir}"',
                content=content
            )

            content = match_and_replace(
                pre=oebuild_const.OPENEULER_SP_DIR,
                new_str=f"{oebuild_const.OPENEULER_SP_DIR} = '{src_dir}'",
                content=content
            )

        # replace sstate_cache
        if parse_compile.sstate_cache is not None:
            if os.path.islink(parse_compile.sstate_cache):
                new_str = f"file://.* {parse_compile.sstate_cache}/PATH;downloadfilename=PATH"
            else:
                if parse_compile.build_in == oebuild_const.BUILD_IN_DOCKER:
                    new_str = f"file://.* file://{oebuild_const.SSTATE_CACHE}/PATH"
                else:
                    new_str = f"file://.* file://{parse_compile.sstate_cache}/PATH"
            content = match_and_replace(
                pre=oebuild_const.SSTATE_MIRRORS,
                new_str=f'{oebuild_const.SSTATE_MIRRORS} = "{new_str}"',
                content=content
            )

        # replace sstate_dir
        if parse_compile.sstate_dir is not None:
            content = match_and_replace(
                pre=oebuild_const.SSTATE_DIR,
                new_str=f'{oebuild_const.SSTATE_DIR} = "{parse_compile.sstate_dir}"',
                content=content
            )

        # replace tmpdir
        if parse_compile.tmp_dir is not None:
            content = match_and_replace(
                pre=oebuild_const.TMP_DIR,
                new_str=f'{oebuild_const.TMP_DIR} = "{parse_compile.tmp_dir}"',
                content=content
            )

        content = self.match_lib_param(content=content)

        user_content_flag = "#===========the content is user added=================="
        if user_content_flag not in content and parse_compile.local_conf != "":
            # check if exists remark sysmbol, if exists and replace it
            for line in parse_compile.local_conf.split('\n'):
                if line.startswith("#"):
                    r_line = line.lstrip("#").strip(" ")
                    content = content.replace(r_line, line)
            content += f"\n{user_content_flag}\n"
            content += parse_compile.local_conf

        if content is None:
            return
        with open(local_dir, 'w', encoding="utf-8") as r_f:
            r_f.write(content)

    def match_lib_param(self, content: str):
        '''
        add params LIBC, TCMODE-LIBC, crypt
        '''
        lib_param_list = {
            "LIBC": "glibc",
            "TCMODE-LIBC": "glibc-external",
            "crypt": "libxcrypt-external"}

        for key, value in lib_param_list.items():
            content = match_and_replace(
                pre=key,
                new_str=f'{key} = "{value}"',
                content=content)
        return content

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
