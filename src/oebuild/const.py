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

# used for util.py
CONFIG_YAML = 'config.yaml'
PLUGINS_YAML = 'plugins.yaml'
UPGRADE_YAML = 'upgrade.yaml'
COMPILE_YAML = 'compile.yaml.sample'
BASH_END_FLAG = "  ###!!!###"
CONTAINER_USER = "openeuler"
CONTAINER_BUILD = '/home/openeuler/build'
CONTAINER_LLVM_LIB = '/home/openeuler/llvm-lib'
DEFAULT_DOCKER = "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container:latest"
DEFAULT_SDK_DOCKER = "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-sdk:latest"
CONTAINER_SRC = '/usr1/openeuler/src'
CONTAINER_USER = "openeuler"
NATIVESDK_DIR = "/opt/buildtools/nativesdk"
PROXY_LIST = ['http_proxy', 'https_proxy']

# used for local_conf
NATIVESDK_DIR_NAME = "OPENEULER_NATIVESDK_SYSROOT"
OPENEULER_SP_DIR = "OPENEULER_SP_DIR"
SSTATE_MIRRORS = "SSTATE_MIRRORS"
SSTATE_DIR = "SSTATE_DIR"
TMP_DIR = "TMPDIR"

NATIVE_GCC_DIR = '/usr1/openeuler/native_gcc'
NATIVE_LLVM_DIR = '/usr1/openeuler/native_llvm'
SSTATE_MIRRORS = '/usr1/openeuler/sstate-cache'

EXTERNAL_LLVM = "EXTERNAL_TOOLCHAIN_LLVM"
EXTERNAL_GCC = "EXTERNAL_TOOLCHAIN_GCC"
EXTERNAL = "EXTERNAL_TOOLCHAIN"

# used for bitbake/in_container.py
BASH_BANNER = '''
    Welcome to the openEuler Embedded build environment, where you
    can run [bitbake recipe] to build what you want, or you ran
    run [bitbake -h] for help
'''

# used for toolchain/toolchain.py
TOOLCHAIN_BASH_BANNER = '''
    Welcome to the openEuler Embedded build environment, where you
    can create openEuler Embedded cross-chains tools by follows:
    "./cross-tools/prepare.sh ./"
    "cp config_aarch64 .config && ct-ng build"
    "cp config_aarch64-musl .config && ct-ng build"
    "cp config_arm32 .config && ct-ng build"
    "cp config_x86_64 .config && ct-ng build"
    "cp config_riscv64 .config && ct-ng build"
'''

# used for configure.py
YOCTO_META_OPENEULER = "yocto_meta_openeuler"
YOCTO_POKY = "yocto-poky"
CONFIG = "config"
COMPILE_YAML = "compile.yaml.sample"

# used for parse_templete.py
PLATFORM = 'platform'
BUILD_IN_DOCKER = "docker"
BUILD_IN_HOST = "host"

DEFAULT_CONTAINER_PARAMS = "-itd --network host"

# used for toolchain type
GCC_TOOLCHAIN = "gcc"
LLVM_TOOLCHAIN = "llvm"
