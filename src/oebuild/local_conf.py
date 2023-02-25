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
            replace_toolchain_str = parse_compile.toolchain_type + ' = "'
            if parse_compile.build_in == BUILD_IN_DOCKER:
                replace_toolchain_str += NATIVE_GCC_DIR + '"'
            else:
                replace_toolchain_str += parse_compile.toolchain_dir
            replace_toolchain_str += '"'
            content = match_and_replace(
                pre=parse_compile.toolchain_type,
                new_str=replace_toolchain_str,
                content=content
            )

        # replace nativesdk OPENEULER_SP_DIR
        if parse_compile.build_in == BUILD_IN_HOST:
            self.check_nativesdk_valid(parse_compile.nativesdk_dir)
            nativesdk_sys_dir = os.path.join(parse_compile.nativesdk_dir, NATIVESDK_SYSROOT)
            content = match_and_replace(
                pre=NATIVESDK_DIR_NAME,
                new_str=NATIVESDK_DIR_NAME + ' = "' + nativesdk_sys_dir + '"',
                content=content
            )

            content = match_and_replace(
                pre=OPENEULER_SP_DIR,
                new_str=OPENEULER_SP_DIR + ' = "' + src_dir + '"',
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
                    new_str= SSTATE_MIRRORS + ' = "' + new_str + '"',
                    content=content
                )

        # replace tmpdir
        if parse_compile.tmp_dir is not None:
            content = match_and_replace(
                    pre=TMP_DIR,
                    new_str= TMP_DIR + ' = "' + parse_compile.tmp_dir + '"',
                    content=content
                )

        content = self.match_lib_param(content=content)

        content = self._match_lib(parse_compile=parse_compile, content=content)

        content = self.replace_param(parse_compile=parse_compile, content=content)

        with open(local_dir, 'w', encoding="utf-8") as r_f:
            r_f.write(content)

    def match_lib_param(self, content: str):
        '''
        add params LIBC, TCMODE-LIBC, crypt
        '''
        new_content = ''
        for line in content.split('\n'):
            ret = re.match('^(LIBC)', line.strip())
            if ret is not None:
                continue
            ret = re.match('^(TCMODE-LIBC)', line.strip())
            if ret is not None:
                continue
            ret = re.match('^(crypt)', line.strip())
            if ret is not None:
                continue
            new_content = new_content + line + '\n'
        return new_content

    def _match_lib(self, parse_compile: ParseCompile, content: str):
        if parse_compile.toolchain_dir is not None and 'musl' in parse_compile.toolchain_dir:
            content = content + 'LIBC = "musl"\n'
            content = content + 'TCMODE-LIBC = "musl"\n'
            content = content + 'crypt = "musl"\n'
            content.replace('aarch64-openeuler-linux-gnu', 'aarch64-openeuler-linux-musl')
        else:
            content = content + 'LIBC = "glibc"\n'
            content = content + 'TCMODE-LIBC = "glibc-external"\n'
            content = content + 'crypt = "libxcrypt-external"\n'
            content.replace('aarch64-openeuler-linux-musl', 'aarch64-openeuler-linux-gnu')
        return content

    def replace_param(self, parse_compile: ParseCompile, content:str):
        '''
        match and replace param by ParseCompile.local_conf
        '''
        for line in parse_compile.local_conf.split('\n'):
            ret = re.match(r'^([A-Z0-9_]+)(append)(\s)', line)
            if ret is not None:
                content = match_and_add(line, content)
                continue
            ret = re.match(r'^([A-Z0-9_]+)([a-z_/]+)(\s)', line)
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
            