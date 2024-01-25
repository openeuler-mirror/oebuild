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
DEFAULT_DOCKER = "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container:latest"
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
SSTATE_CACHE = '/usr1/openeuler/sstate-cache'

# used for bitbake/in_container.py
BASH_BANNER = '''
    Welcome to the openEuler Embedded build environment, 
    where you can run 'bitbake openeuler-image' to build 
    standard images 
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
