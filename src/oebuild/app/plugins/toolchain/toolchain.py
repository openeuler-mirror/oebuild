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

import textwrap
import argparse
import sys
import os
import subprocess

from docker.models.containers import ExecResult

from oebuild.command import OebuildCommand
from oebuild.m_log import logger, set_log_to_file
import oebuild.util as oebuild_util
import oebuild.const as oebuild_const
from oebuild.parse_param import ParseToolchainParam
from oebuild.parse_env import ParseEnv
from oebuild.bashrc import Bashrc
from oebuild.docker_proxy import DockerProxy
from oebuild.configure import Configure


class Toolchain(OebuildCommand):
    '''
    The toolchain provides the ability to build a cross-compilation chain.
    '''

    help_msg = 'build openEuler cross-toolchain'
    description = textwrap.dedent('''\
            The toolchain provides similar functionality to bitbake, allowing
            for the construction of an openEuler cross-toolchain.
            ''')

    def __init__(self):
        self._toolchain_yaml_path = os.path.join(os.getcwd(), 'toolchain.yaml')
        self.bashrc = Bashrc()
        self.client = DockerProxy()
        self.container_id = None

        super().__init__('toolchain', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''

  %(prog)s [auto | <target>]

''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        if '-h' in unknown or '--help' in unknown:
            self.print_help_msg()
            sys.exit(0)

        set_log_to_file()

        if not self._check_support_toolchain():
            logger.error(
                "Please do it in compile workspace which contain toolchain.yaml")
            sys.exit(-1)

        toolchain_dict = oebuild_util.read_yaml(self._toolchain_yaml_path)
        toolchain_obj = ParseToolchainParam().parse_to_obj(toolchain_param_dict=toolchain_dict)

        if not os.path.exists('.env'):
            os.mknod('.env')
        parse_env = ParseEnv(env_dir='.env')

        self._prepare_build_env()

        self.container_id = oebuild_util.deal_env_container(
            env=parse_env, docker_param=toolchain_obj.docker_param)
        self.bashrc.set_container(
            container=self.client.get_container(container_id=self.container_id))
        self.client.check_change_ugid(
            container=self.client.get_container(container_id=self.container_id),
            container_user=oebuild_const.CONTAINER_USER)

        self._set_environment_param()

        if unknown is None or len(unknown) == 0:
            content = self.bashrc.get_bashrc_content()
            for b_s in oebuild_const.TOOLCHAIN_BASH_BANNER.split('\n'):
                b_s = f"echo {b_s}"
                content = self.bashrc.add_bashrc(content=content, line=b_s)
            self.bashrc.update_bashrc(content=content)
            # 调起容器环境
            build_dir = os.path.join(oebuild_const.CONTAINER_BUILD, os.path.basename(os.getcwd()))
            docker_exec_list = [
                "docker",
                "exec",
                "-it",
                "-u",
                oebuild_const.CONTAINER_USER,
                "-w",
                build_dir,
                self.container_id,
                "bash"
            ]
            os.system(" ".join(docker_exec_list))
        elif unknown[0] == "auto":
            self.auto_build(config_list=toolchain_obj.config_list)
        else:
            cross_tools_dir = os.path.join(
                Configure().source_yocto_dir(), ".oebuild/cross-tools/configs")
            config_list = os.listdir(cross_tools_dir)
            config_name: str = unknown[0]
            if not config_name.startswith("config_"):
                config_name = f"config_{config_name}"
            if config_name not in config_list:
                logger.error("please enter valid toolchain name")
                print("the valid toolchain list:")
                for config in config_list:
                    if config.startswith("config_"):
                        print(config)
                print("you can run oebuild toolchain aarch64 or oebuild toolchain config_aarch64")
            self._build_toolchain(config_name=config_name)
        self.bashrc.restore_bashrc()

    def auto_build(self, config_list):
        '''
        is for auto build toolchains
        '''
        for config in config_list:
            self._build_toolchain(config_name=config)

    def _set_environment_param(self):
        content = self.bashrc.get_bashrc_content()
        open_source_cmd = 'export OPENSOURCE_DIR="$PWD/open_source"'
        content = self.bashrc.add_bashrc(content=content, line=open_source_cmd)
        x_tools_cmd = 'export X_TOOLS_DIR="$PWD/x-tools"'
        content = self.bashrc.add_bashrc(content=content, line=x_tools_cmd)
        self.bashrc.update_bashrc(content=content)

    def _build_toolchain(self, config_name):
        '''
        build toolchain with config
        '''
        content = self.bashrc.get_bashrc_content()
        src_config_dir = os.path.join(
            oebuild_const.CONTAINER_SRC,
            "yocto-meta-openeuler",
            ".oebuild",
            "cross-tools",
            "configs")
        content = self.bashrc.add_bashrc(content=content, line="./cross-tools/prepare.sh ./")
        content = self.bashrc.add_bashrc(
            content=content,
            line=f"cp {src_config_dir}/{config_name} .config && ct-ng build")
        self.bashrc.update_bashrc(content=content)
        res: ExecResult = self.client.container_exec_command(
            container=self.client.get_container(self.container_id),
            command="bash .bashrc",
            user=oebuild_const.CONTAINER_USER,
            params={
                "work_space": f"/home/{oebuild_const.CONTAINER_USER}",
                "demux": True
            })
        exit_code = 0
        for line in res.output:
            if line[1] is not None:
                logger.error(line[1].decode().strip('\n'))
                exit_code = 1
            else:
                logger.info(line[0].decode().strip('\n'))
        if exit_code != 0:
            sys.exit(exit_code)

    def _check_support_toolchain(self):
        return os.path.exists(self._toolchain_yaml_path)

    def _prepare_build_env(self):
        # create cross-tools symblic
        src_cross_dir = os.path.join(
            oebuild_const.CONTAINER_SRC,
            "yocto-meta-openeuler",
            ".oebuild",
            "cross-tools")
        subprocess.run(f'ln -sf {src_cross_dir} cross-tools', shell=True, check=False)
        # create config.xml symblic
        cross_tools_dir = os.path.join(
            Configure().source_yocto_dir(), ".oebuild/cross-tools/configs")
        config_dir_list = os.listdir(cross_tools_dir)
        for config_path in config_dir_list:
            src_config_path = os.path.join(src_cross_dir, f"configs/{config_path}")
            subprocess.run(f'ln -sf {src_config_path} {config_path}', shell=True, check=False)
