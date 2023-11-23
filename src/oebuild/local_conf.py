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

from oebuild.parse_compile import ParseCompile
from oebuild.parse_template import BUILD_IN_DOCKER, BUILD_IN_HOST

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

NATIVESDK_DIR_NAME = "OPENEULER_NATIVESDK_SYSROOT"
NATIVESDK_SYSROOT = "sysroots/x86_64-pokysdk-linux"
OPENEULER_SP_DIR = "OPENEULER_SP_DIR"
NATIVESDK_ENVIRONMENT = "environment-setup-x86_64-pokysdk-linux"
SSTATE_MIRRORS = "SSTATE_MIRRORS"
SSTATE_DIR = "SSTATE_DIR"
TMP_DIR = "TMPDIR"

NATIVE_GCC_DIR = '/usr1/openeuler/native_gcc'
SSTATE_CACHE = '/usr1/openeuler/sstate-cache'

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

    def __init__(self, local_conf_dir: str):
        self.local_dir = local_conf_dir

    def update(self, parse_compile: ParseCompile, src_dir = None):
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

        # replace platform
        content = match_and_replace(
            pre="OPENEULER_PLATFORM ",
            new_str=f'OPENEULER_PLATFORM = "{parse_compile.platform}"',
            content=content
        )

        # replace toolchain
        if parse_compile.toolchain_dir is not None:
            if parse_compile.build_in == BUILD_IN_DOCKER:
                replace_toolchain_str = f'{parse_compile.toolchain_type} = "{NATIVE_GCC_DIR}"'
            else:
                replace_toolchain_str = f'{parse_compile.toolchain_type} = "{parse_compile.toolchain_dir}"'
            content = match_and_replace(
                pre=parse_compile.toolchain_type,
                new_str=replace_toolchain_str,
                content=content
            )

        # replace nativesdk OPENEULER_SP_DIR
        if parse_compile.build_in == BUILD_IN_HOST:
            self.check_nativesdk_valid(parse_compile.nativesdk_dir)
            if parse_compile.nativesdk_dir is None:
                raise ValueError("please set nativesdk dir")
            nativesdk_sys_dir = os.path.join(parse_compile.nativesdk_dir, NATIVESDK_SYSROOT)
            content = match_and_replace(
                pre=NATIVESDK_DIR_NAME,
                new_str=f'{NATIVESDK_DIR_NAME} = "{nativesdk_sys_dir}"',
                content=content
            )

            content = match_and_replace(
                pre=OPENEULER_SP_DIR,
                new_str= f"{OPENEULER_SP_DIR} = '{src_dir}'",
                content=content
            )

        # replace sstate_cache
        if parse_compile.sstate_cache is not None:
            if os.path.islink(parse_compile.sstate_cache):
                new_str= f"file://.* {parse_compile.sstate_cache}/PATH;downloadfilename=PATH"
            else:
                if parse_compile.build_in == BUILD_IN_DOCKER:
                    new_str= f"file://.* file://{SSTATE_CACHE}/PATH"
                else:
                    new_str= f"file://.* file://{parse_compile.sstate_cache}/PATH"
            content = match_and_replace(
                    pre=SSTATE_MIRRORS,
                    new_str = f'{SSTATE_MIRRORS} = "{new_str}"',
                    content=content
                )

        # replace sstate_dir
        if parse_compile.sstate_dir is not None:
            content = match_and_replace(
                    pre=SSTATE_DIR,
                    new_str = f'{SSTATE_DIR} = "{parse_compile.sstate_dir}"',
                    content=content
                )

        # replace tmpdir
        if parse_compile.tmp_dir is not None:
            content = match_and_replace(
                    pre=TMP_DIR,
                    new_str = f'{TMP_DIR} = "{parse_compile.tmp_dir}"',
                    content=content
                )

        content = self.match_lib_param(content=content)

        user_content_flag = "#===========the content is user added=================="
        if user_content_flag not in content and parse_compile.local_conf != "":
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
                pre = key,
                new_str = f'{key} = "{value}"',
                content = content)
        return content

    def replace_param(self, parse_compile: ParseCompile, content:str):
        '''
        match and replace param by ParseCompile.local_conf
        '''
        if parse_compile.local_conf is None:
            return
        for line in parse_compile.local_conf.split('\n'):
            ret = re.match(r'^([A-Z0-9_:]+)(append)(\s)', line)
            if ret is not None:
                content = match_and_add(line, content)
                continue
            ret = re.match(r'^(([A-Z0-9a-z_-]|[/])+)(\s)', line)
            if ret is not None:
                content = match_and_replace(ret.group(), line, content)
                continue
            ret = re.match(r'^(require)(\s)', line)
            if ret is not None:
                content = match_and_add(line, content)
                continue
        return content

    def check_nativesdk_valid(self, nativesdk_dir):
        '''
        Check whether the set nativesdk is valid, check whether
        the path exists, and then check whether the internal
        OECORE_NATIVE_SYSROOT variables are consistent with the set nativesdk
        '''
        if not os.path.exists(nativesdk_dir):
            raise NativesdkNotExist(f"nativesdk directory: {nativesdk_dir} not exist")

        nativesdk_environment_dir = os.path.join(nativesdk_dir, NATIVESDK_ENVIRONMENT)

        with open(nativesdk_environment_dir, 'r', encoding='utf-8') as r_f:
            for line in r_f.readlines():
                line = line.strip('\n')
                if not line.startswith("export OECORE_NATIVE_SYSROOT="):
                    continue
                oecore_sysroot_dir = line.lstrip('export OECORE_NATIVE_SYSROOT=').strip('"')
                if not oecore_sysroot_dir.startswith(nativesdk_dir):
                    raise NativesdkNotValid(f"nativesdk directory: {nativesdk_dir} are not valid")
                return
            