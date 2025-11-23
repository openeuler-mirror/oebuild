"""
Copyright (c) 2023 openEuler Embedded
oebuild is licensed under Mulan PSL v2.
You can use this software according to the terms and conditions of the Mulan PSL v2.
You may obtain a copy of Mulan PSL v2 at:
         http://license.coscl.org.cn/MulanPSL2
THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
See the Mulan PSL v2 for more details.
"""

import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time

from kconfiglib import Kconfig
from menuconfig import menuconfig

import oebuild.util as oebuild_util
from oebuild.app.plugins.generate.parses import parse_feature_files
from oebuild.m_log import logger

# ***
# THIS KCONFIG GENERATOR IS TOO WEAK.
# DO NOT USE THIS FILE IN NEO-GENERATE***
# ***


class KconfigGenerator:
    """
    Handles Kconfig file generation and menuconfig interaction.
    """

    def __init__(self, oebuild_kconfig_path, yocto_oebuild_dir):
        self.oebuild_kconfig_path = oebuild_kconfig_path
        self.yocto_oebuild_dir = yocto_oebuild_dir

    def create_kconfig(self):
        """Generate a temp Kconfig, launch menuconfig, and return the .config path."""
        write_data = ''

        target_list_data, gcc_toolchain_data, llvm_toolchain_data = (
            self._kconfig_add_target_list()
        )
        write_data += (
            target_list_data + gcc_toolchain_data + llvm_toolchain_data
        )

        # add auto-build config
        write_data += """
if NATIVESDK || GCC-TOOLCHAIN || LLVM-TOOLCHAIN
comment "Enable auto build for nativesdk/GCC/LLVM toolchain"
    config AUTO-BUILD
        bool "auto build"
        default n
endif
"""

        platform_data = self._kconfig_add_choice_platform()
        write_data += platform_data

        feature_data = self._kconfig_add_feature()
        write_data += feature_data

        common_data = self._kconfig_add_common_config()
        write_data += common_data

        if not os.path.exists(
            pathlib.Path(self.oebuild_kconfig_path).absolute()
        ):
            os.makedirs(pathlib.Path(self.oebuild_kconfig_path).absolute())
        kconfig_path = pathlib.Path(
            self.oebuild_kconfig_path, str(int(time.time()))
        )

        with open(kconfig_path, 'w', encoding='utf-8') as kconfig_file:
            kconfig_file.write(write_data)
        kconf = Kconfig(filename=str(kconfig_path))
        os.environ['MENUCONFIG_STYLE'] = 'aquatic selection=fg:white,bg:blue'
        with oebuild_util.suppress_print():
            menuconfig(kconf)
        subprocess.check_output(f'rm -rf {kconfig_path}', shell=True)
        config_path = pathlib.Path(os.getcwd(), '.config')
        return config_path

    def _kconfig_add_target_list(self):
        target_choice = textwrap.dedent("""
            comment "Select build target"
            choice
            prompt "Select build target"
                config IMAGE
                    bool 'OS'
""")
        gcc_toolchain_data = self._kconfig_add_gcc_toolchain()
        if gcc_toolchain_data != '':
            target_choice += (
                "config GCC-TOOLCHAIN \n       bool 'GCC TOOLCHAIN'\n\n"
            )
        llvm_toolchain_data = self._kconfig_add_llvm_toolchain()
        if llvm_toolchain_data != '':
            target_choice += (
                "config LLVM-TOOLCHAIN \n       bool 'LLVM TOOLCHAIN'\n\n"
            )
        nativesdk_check = self._kconfig_check_nativesdk()
        if nativesdk_check:
            target_choice += "config NATIVESDK \n       bool 'NATIVESDK'\n\n"
        target_choice += 'endchoice'
        return target_choice, gcc_toolchain_data, llvm_toolchain_data

    def _kconfig_add_choice_platform(self):
        """
            add platform to kconfig
        Args:
            yocto_oebuild_dir:

        Returns:

        """
        platform_path = pathlib.Path(self.yocto_oebuild_dir, 'platform')
        if platform_path.exists():
            platform_files = [
                f
                for f in platform_path.iterdir()
                if f.is_file() and f.suffix in ['.yml', '.yaml']
            ]
        else:
            logger.error('Platform directory not found.')
            sys.exit(-1)
        platform_start = textwrap.dedent("""
        if IMAGE
        comment "Select OS platform"
        choice
            prompt "Select platform"
            default PLATFORM_QEMU-AARCH64
        """)
        platform_end = """
        endchoice
        endif"""
        for platform in platform_files:
            platform_name = platform.stem.strip('\n')
            platform_info = (
                f'    config PLATFORM_{platform_name.upper()}\n'
                f'        bool "{platform_name}"\n\n'
            )
            platform_start += platform_info
        platform_data = platform_start + platform_end
        return platform_data

    def _kconfig_add_feature(self):
        """
            add feature to kconfig
        Args:
            yocto_oebuild_dir:

        Returns:

        """

        feature_start = """
        if IMAGE
        comment "Select OS features"
        """

        feature_triples = parse_feature_files(self.yocto_oebuild_dir)
        for ft_name, _, feature_data in feature_triples:
            support_str = ''
            if 'support' in feature_data:
                raw_supports = feature_data['support']
                validated_support_str = self.validate_and_format_platforms(
                    raw_supports
                )
                if validated_support_str:
                    support_str = validated_support_str
                else:
                    logger.warning(
                        'supported platform str of feat %s is invalid: %s',
                        ft_name,
                        raw_supports,
                    )

            feature_info = (
                f'\nconfig FEATURE_{ft_name.upper()}\n'
                f'    bool "{ft_name}" {support_str}\n\n'
            )
            feature_start += feature_info
        feature_start += 'endif'
        return feature_start

    def validate_and_format_platforms(self, raw_str: str):
        """
        strip delimeter and format to supported platforms conditions
        """

        platforms = re.split(r'[|,，\s]+', raw_str)
        platforms = [p.strip() for p in platforms if p.strip()]
        if not platforms:
            return ''
        platform_cond = [f'PLATFORM_{p.upper()}' for p in platforms]
        return 'if ' + '||'.join(platform_cond)

    def _kconfig_add_gcc_toolchain(self):
        """
            add toolchain to kconfig
        Args:
            yocto_oebuild_dir: yocto_oebuild_dir

        Returns:

        """
        toolchain_start = ''
        cross_dir = pathlib.Path(self.yocto_oebuild_dir, 'cross-tools')
        if cross_dir.exists():
            configs_dir = cross_dir / 'configs'
            if configs_dir.exists():
                toolchain_list = os.listdir(configs_dir)
                toolchain_start += """
            if GCC-TOOLCHAIN
            """
                for config in toolchain_list:
                    if not re.search('xml', config):
                        toolchain_info = (
                            f"""\nconfig GCC-TOOLCHAIN_{config.upper().lstrip('CONFIG_')}\n"""
                            f"""    bool "{config.upper().lstrip('CONFIG_')}"\n"""
                            """     depends on GCC-TOOLCHAIN\n"""
                        )
                        toolchain_start += toolchain_info
                toolchain_start += 'endif'
        return toolchain_start

    def _kconfig_add_llvm_toolchain(self):
        """
            add toolchain to kconfig
        Args:
            yocto_oebuild_dir: yocto_oebuild_dir

        Returns:

        """
        toolchain_start = ''
        llvm_dir = pathlib.Path(self.yocto_oebuild_dir, 'llvm-toolchain')
        if llvm_dir.exists():
            toolchain_start += """
                config LLVM-TOOLCHAIN-AARCH64-LIB
                    string "aarch64 lib dir"
                    default "None"
                    depends on LLVM-TOOLCHAIN
            """
        return toolchain_start

    def _kconfig_check_nativesdk(self):
        """
            add nativesdk to kconfig
        Args:
            yocto_oebuild_dir: yocto_oebuild_dir

        Returns:

        """
        nativesdk_dir = pathlib.Path(self.yocto_oebuild_dir, 'nativesdk')
        return nativesdk_dir.exists()

    def _kconfig_add_common_config(
        self,
    ):
        """
            Build shared/common Kconfig options.
        Returns:

        """
        toolchain_help = (
            'External GCC toolchain directory [your own toolchain]'
        )
        llvm_toolchain_help = (
            'External LLVM toolchain directory [your own toolchain]'
        )
        nativesdk_help = (
            'External nativesdk directory [used when building on host]'
        )
        common_str = textwrap.dedent("""
        comment "Common options"
                                     """)
        # choice build in platform
        common_str += """
        if IMAGE
            choice
                prompt "Select build environment"
                default BUILD_IN-DOCKER
                config BUILD_IN-DOCKER
                    bool "docker"
                config BUILD_IN-HOST
                    bool "host"
            endchoice
        endif
                       """
        # add no fetch
        common_str += """
        config COMMON_NO-FETCH
            bool "no_fetch (disable source fetching)"
            default n
            depends on IMAGE
                       """
        # add no layer
        common_str += """
        config COMMON_NO-LAYER
            bool "no_layer (skip layer repo update on env setup)"
            default n
            depends on IMAGE
                       """
        # add sstate_mirrors
        common_str += """
        config COMMON_SSTATE-MIRRORS
            string "SSTATE_MIRRORS value"
            default "None"
            depends on IMAGE
                       """
        # add sstate_dir
        common_str += """
        config COMMON_SSTATE-DIR
            string "SSTATE_DIR path"
            default "None"
            depends on IMAGE
                       """
        # add tmp_dir
        common_str += """
        config COMMON_TMP-DIR
            string "TMPDIR path"
            default "None"
            depends on IMAGE && BUILD_IN-HOST
                       """
        # add gcc toolchain dir
        common_str += f"""
        config COMMON_TOOLCHAIN-DIR
            string "toolchain_dir ({toolchain_help})"
            default "None"
            depends on IMAGE
                       """
        # add llvm toolchain dir
        common_str += f"""
        config COMMON_LLVM-TOOLCHAIN-DIR
            string "llvm_toolchain_dir ({llvm_toolchain_help})"
            default "None"
            depends on IMAGE
                       """
        # add nativesdk dir
        common_str += f"""
        config COMMON_NATIVESDK-DIR
            string "nativesdk_dir ({nativesdk_help})"
            default "None"
            depends on IMAGE && BUILD_IN-HOST
                       """
        # add timestamp
        common_str += """
        config COMMON_DATETIME
            string "datetime"
            default "None"
            depends on IMAGE
                       """
        # add cache_src_dir directory
        common_str += """
        config COMMON_CACHE_SRC_DIR
            string "cache_src_dir (src directory)"
            default "None"
            depends on IMAGE
                       """
        # add build directory
        common_str += """
        config COMMON_DIRECTORY
            string "directory (build directory name)"
            default "None"
                       """
        return common_str
