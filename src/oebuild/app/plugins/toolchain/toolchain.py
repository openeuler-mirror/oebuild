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
        self.toolchain_dict = None
        self.toolchain_obj = None
        self.bashrc = None
        self.client = None
        self.container_id = None

        super().__init__('toolchain', self.help_msg, self.description)

    def __del__(self):
        if self.bashrc is not None:
            self.bashrc.restore_bashrc()

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''

  %(prog)s [auto | setlib | upenv | downsource | <target>]

''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        if '-h' in unknown or '--help' in unknown:
            self.print_help_msg()
            sys.exit(0)

        set_log_to_file()
        self._check_support_toolchain()
        self._set_init_params()

        if unknown is not None and len(unknown) >= 2 and unknown[0] == "setlib":
            self.toolchain_dict['llvm_lib'] = unknown[1]
            oebuild_util.write_yaml(self._toolchain_yaml_path, self.toolchain_dict)
            self.toolchain_obj.llvm_lib = unknown[1]
            return
        # if toolchain is llvm, the docker volume should be cover llvm_lib
        self._set_llvm_pre()

        if not os.path.exists('.env'):
            os.mknod('.env')
        parse_env = ParseEnv(env_dir='.env')

        self._check_env_and_upenv()

        self._deal_container(parse_env)
        self._set_environment_param()

        if unknown is None or len(unknown) == 0:
            content = self.bashrc.get_bashrc_content()
            for b_s in oebuild_const.TOOLCHAIN_BASH_BANNER.split('\n'):
                b_s = f"echo {b_s}"
                content = self.bashrc.add_bashrc(content=content, line=b_s)
            self.bashrc.update_bashrc(content=content)
            self.bashrc.clean_command_bash()
            # 调起容器环境
            build_dir = os.path.join(oebuild_const.CONTAINER_BUILD, os.path.basename(os.getcwd()))
            docker_exec_list = ["docker", "exec", "-it", "-u", oebuild_const.CONTAINER_USER,
                                "-w", build_dir, self.container_id, "bash"]
            os.system(" ".join(docker_exec_list))
        elif unknown[0] == "auto":
            if self.toolchain_obj.kind == oebuild_const.GCC_TOOLCHAIN:
                self.auto_build_gcc(config_list=self.toolchain_obj.gcc_configs)
            else:
                self.auto_build_llvm()
        elif unknown[0] == "upenv":
            self._run_upenv(kind=self.toolchain_obj.kind)
        elif unknown[0] == "downsource":
            self._run_downcode(kind=self.toolchain_obj.kind)
        else:
            if self.toolchain_obj.kind == oebuild_const.GCC_TOOLCHAIN:
                config_name = self._check_gcc_config(unknown[0])
                self._build_gcc(config_name=config_name)
            else:
                self._build_llvm()

    def _set_init_params(self,):
        self.toolchain_dict = oebuild_util.read_yaml(self._toolchain_yaml_path)
        self.toolchain_obj = ParseToolchainParam().parse_to_obj(
            toolchain_param_dict=self.toolchain_dict)
        self.bashrc = Bashrc()
        self.client = DockerProxy()

    def _check_gcc_config(self, config_name: str):
        config_list = os.listdir("configs")
        if not config_name.startswith("config_"):
            config_name = f"config_{config_name}"
        if config_name not in config_list:
            logger.error("please enter valid toolchain name")
            print("the valid toolchain list:")
            for config in config_list:
                if config.startswith("config_"):
                    print(config)
            print("""
you can run oebuild toolchain aarch64 or oebuild toolchain config_aarch64""")
            sys.exit(1)
        return config_name

    def _deal_container(self, parse_env):
        # check docker image openeuler-sdk if exists, if not down it
        if not self.client.is_image_exists(self.toolchain_obj.docker_param.image):
            print(f"the {self.toolchain_obj.docker_param.image} not exists, now pull it")
            self.client.pull_image_with_progress(self.toolchain_obj.docker_param.image)
        self.container_id = oebuild_util.deal_env_container(
            env=parse_env, docker_param=self.toolchain_obj.docker_param)
        self.bashrc.set_container(
            container=self.client.get_container(container_id=self.container_id))
        self.client.check_change_ugid(
            container=self.client.get_container(container_id=self.container_id),
            container_user=oebuild_const.CONTAINER_USER)

    def _set_llvm_pre(self):
        if self.toolchain_obj.kind != oebuild_const.LLVM_TOOLCHAIN:
            return
        if self.toolchain_obj.llvm_lib is None or self.toolchain_obj.llvm_lib == "":
            logger.error("""
compile llvm toolchain need aarch64 lib, please run:

    oebuild toolchain setlib xxx

pointed it first""")
            sys.exit(-1)
        self._add_llvmlib_to_volumn()

    def _add_llvmlib_to_volumn(self):
        # check if had mounted
        check_vol = False
        for volumn in self.toolchain_obj.docker_param.volumns:
            if volumn.endswith(self.toolchain_obj.llvm_lib):
                check_vol = True
        if not check_vol:
            self.toolchain_obj.docker_param.volumns.append(
                self.toolchain_obj.llvm_lib + ":" + oebuild_const.CONTAINER_LLVM_LIB
            )

    def auto_build_gcc(self, config_list):
        '''
        is for auto build gcc toolchains
        '''
        # if exists open_source, do nothing
        if not os.path.exists("open_source"):
            self._run_downcode(kind=oebuild_const.GCC_TOOLCHAIN)
        for config in config_list:
            self._build_gcc(config_name=config)

    def auto_build_llvm(self):
        '''
        if for auto build llvm toolchains
        '''
        self._run_downcode(kind=oebuild_const.LLVM_TOOLCHAIN)
        self._build_llvm()

    def _set_environment_param(self):
        kind = self.toolchain_obj.kind
        if kind == oebuild_const.LLVM_TOOLCHAIN:
            return
        content = self.bashrc.get_bashrc_content()
        build_dir = os.path.join(oebuild_const.CONTAINER_BUILD, os.path.basename(os.getcwd()))
        open_source_cmd = f'export CROSS_SOURCE="{build_dir}/open_source/."'
        content = self.bashrc.add_bashrc(content=content, line=open_source_cmd)
        mk_x_tools = f"mkdir -p {build_dir}/x-tools"
        content = self.bashrc.add_bashrc(content=content, line=mk_x_tools)
        ln_tools_cmd = f'cd ~ && rm -f x-tools && ln -fs {build_dir}/x-tools x-tools'
        content = self.bashrc.add_bashrc(content=content, line=ln_tools_cmd)
        content = self.bashrc.add_bashrc(content=content, line=f"cd {build_dir}")
        self.bashrc.update_bashrc(content=content)

    def _run_downcode(self, kind):
        build_dir = os.path.join(oebuild_const.CONTAINER_BUILD, os.path.basename(os.getcwd()))
        res: ExecResult = self.client.container_exec_command(
            container=self.client.get_container(self.container_id),
            command="./prepare.sh ./",
            user=oebuild_const.CONTAINER_USER,
            params={
                "work_space": build_dir
            })
        for line in res.output:
            logger.info(line.decode().strip('\n'))

        if kind == oebuild_const.GCC_TOOLCHAIN:
            res: ExecResult = self.client.container_exec_command(
                container=self.client.get_container(self.container_id),
                command="./update.sh",
                user=oebuild_const.CONTAINER_USER,
                params={
                    "work_space": build_dir
                })
            for line in res.output:
                logger.info(line.decode().strip('\n'))

    def _build_gcc(self, config_name: str):
        '''
        build gcc with config
        '''
        build_dir = os.path.join(oebuild_const.CONTAINER_BUILD, os.path.basename(os.getcwd()))
        container = self.client.get_container(self.container_id)
        self.client.container_exec_command(
            container=container,
            command=f"cp {config_name} .config",
            user=oebuild_const.CONTAINER_USER,
            params={
                "work_space": build_dir,
                "stream": False})
        content = self.bashrc.get_bashrc_content()
        content = self.bashrc.add_bashrc(content=content, line="ct-ng build")
        self.bashrc.update_bashrc(content=content)
        self.bashrc.clean_command_bash()
        res: ExecResult = self.client.container_exec_command(
            container=container,
            command=f"bash /home/{oebuild_const.CONTAINER_USER}/.bashrc",
            user=oebuild_const.CONTAINER_USER,
            params={"work_space": build_dir})
        for line in res.output:
            logger.info(line.decode().strip('\n'))

    def _build_llvm(self):
        '''
        build gcc with config
        '''
        build_dir = os.path.join(oebuild_const.CONTAINER_BUILD, os.path.basename(os.getcwd()))
        container = self.client.get_container(self.container_id)
        content = self.bashrc.get_bashrc_content()
        lib_gcc_dir = f'{oebuild_const.CONTAINER_LLVM_LIB}/lib64/gcc'
        lib_include_dir = f'{oebuild_const.CONTAINER_LLVM_LIB}/aarch64-openeuler-linux-gnu/include'
        lib_sysroot_dir = f'{oebuild_const.CONTAINER_LLVM_LIB}/aarch64-openeuler-linux-gnu/sysroot'
        init_cmd = f'''
cd ./open_source/llvm-project
./build.sh -e -o -s -i -b release -I clang-llvm-17.0.6
cd ./clang-llvm-17.0.6
mkdir lib64 aarch64-openeuler-linux-gnu
cp -rf {lib_gcc_dir} lib64/
cp -rf {lib_include_dir} aarch64-openeuler-linux-gnu/
cp -rf {lib_sysroot_dir} aarch64-openeuler-linux-gnu/
cd ./bin
ln -sf ld.lld aarch64-openeuler-linux-gnu-ld
'''
        content = self.bashrc.add_bashrc(content=content, line=init_cmd)
        self.bashrc.update_bashrc(content=content)
        self.bashrc.clean_command_bash()
        res: ExecResult = self.client.container_exec_command(
            container=container,
            command=f"bash /home/{oebuild_const.CONTAINER_USER}/.bashrc",
            user=oebuild_const.CONTAINER_USER,
            params={"work_space": build_dir})
        for line in res.output:
            logger.info(line.decode().strip('\n'))

    def _check_support_toolchain(self):
        if not os.path.exists(self._toolchain_yaml_path):
            logger.error(
                "Please do it in compile workspace which contain toolchain.yaml")
            sys.exit(-1)

    def _check_env_and_upenv(self):
        # we check env if prepared only detect the configs and patchs directory exists
        kind = self.toolchain_obj.kind
        if kind == oebuild_const.GCC_TOOLCHAIN:
            if not (os.path.exists("configs") and os.path.exists("patches")):
                self._run_upenv(kind=oebuild_const.GCC_TOOLCHAIN)
                return
        if not os.path.exists("configs"):
            self._run_upenv(kind=oebuild_const.LLVM_TOOLCHAIN)

    def _run_upenv(self, kind):
        if kind == oebuild_const.GCC_TOOLCHAIN:
            # cp all cross-tools files to build_dir
            logger.info("cp cross-tools data to ./")
            src_cross_dir = os.path.join(Configure().source_yocto_dir(), ".oebuild/cross-tools")
            subprocess.run(f'cp -ru  {src_cross_dir}/* ./', shell=True, check=False)
        else:
            # cp all llvm-toolchain files to build_dir
            logger.info("cp llvm-toolchain data to ./")
            src_llvm_dir = os.path.join(Configure().source_yocto_dir(), ".oebuild/llvm-toolchain")
            subprocess.run(f'cp -ru {src_llvm_dir}/* ./', shell=True, check=False)
