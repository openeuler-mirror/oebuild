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
import sys

from docker.models.containers import Container, ExecResult

from oebuild.parse_env import ParseEnv
from oebuild.docker_proxy import DockerProxy
from oebuild.configure import Configure
from oebuild.struct import CompileParam, DockerParam
from oebuild.m_log import logger
from oebuild.app.plugins.bitbake.base_build import BaseBuild
from oebuild.bashrc import Bashrc
import oebuild.util as oebuild_util
import oebuild.const as oebuild_const


class InContainer(BaseBuild):
    '''
    bitbake command execute in container
    '''

    def __init__(self, configure: Configure):
        self.configure = configure
        self.client = DockerProxy()
        self.container_id = None
        self.bashrc = None

    def exec(self, parse_env: ParseEnv, compile_param: CompileParam, command):
        '''
        execute bitbake command
        '''
        logger.info("Bitbake starting ...")

        # check docker image if exists
        docker_proxy = DockerProxy()
        docker_param = compile_param.docker_param
        if not docker_proxy.is_image_exists(docker_param.image):
            logger.error('''The docker image does not exists, please run fellow command:
    `oebuild update docker`''')
            sys.exit(-1)

        self.container_id = oebuild_util.deal_env_container(
            env=parse_env, docker_param=docker_param)
        self.bashrc = Bashrc()
        self.bashrc.set_container(container=self.client.get_container(self.container_id))
        self.exec_compile(compile_param=compile_param, command=command)

    def _trans_docker_param(self,
                            docker_image: str,
                            toolchain_dir: str = None,
                            sstate_mirrors: str = None) -> DockerParam:
        '''
        this function is to adapt the old compile.yaml
        '''
        parameters = oebuild_const.DEFAULT_CONTAINER_PARAMS
        volumns = []
        volumns.append("/dev/net/tun:/dev/net/tun")
        volumns.append(self.configure.source_dir() + ':' + oebuild_const.CONTAINER_SRC)
        volumns.append(os.getcwd() + ':' +
                       os.path.join(oebuild_const.CONTAINER_BUILD, os.path.basename(os.getcwd())))
        if toolchain_dir is not None:
            volumns.append(toolchain_dir + ":" + oebuild_const.NATIVE_GCC_DIR)
        if sstate_mirrors is not None:
            volumns.append(sstate_mirrors + ":" + oebuild_const.SSTATE_MIRRORS)

        docker_param = DockerParam(
            image=docker_image,
            parameters=parameters,
            volumns=volumns,
            command="bash"
        )
        return docker_param

    def exec_compile(self, compile_param: CompileParam, command: str = ""):
        '''
        execute compile task
        '''
        container: Container = self.client.get_container(self.container_id)  # type: ignore

        self.init_bash(container=container,
                       build_dir_name=os.path.basename(os.getcwd()))

        try:
            self.init_bitbake(container=container)
        except ValueError as v_e:
            logger.error(str(v_e))
            return

        # add bblayers, this action must before replace local_conf
        bblayers_dir = os.path.join(os.getcwd(), "conf", "bblayers.conf")
        self.add_bblayers(
            bblayers_dir=bblayers_dir,
            pre_dir=oebuild_const.CONTAINER_SRC,
            base_dir=self.configure.source_dir(),
            layers=compile_param.layers)

        # replace local_conf
        local_path = os.path.join(os.getcwd(), 'conf', 'local.conf')
        self.replace_local_conf(
            compile_param=compile_param,
            local_path=local_path)

        # add auto execute command for example: bitbake busybox
        if command is not None and command != "":
            content = self.bashrc.get_bashrc_content()
            new_content = self.bashrc.add_bashrc(content=content, line=command)
            self.bashrc.update_bashrc(content=new_content)
            res: ExecResult = self.client.container_exec_command(
                container=container,
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
            sys.exit(exit_code)
        else:
            content = self.bashrc.get_bashrc_content()
            for b_s in oebuild_const.BASH_BANNER.split('\n'):
                b_s = f"echo {b_s}"
                content = self.bashrc.add_bashrc(content=content, line=b_s)
            self.bashrc.update_bashrc(content=content)
            os.system(
                f"docker exec -it -u {oebuild_const.CONTAINER_USER} {container.short_id} bash")

        self.bashrc.restore_bashrc()

    def init_bitbake(self, container: Container):
        '''
        init_bitbake will start a container with pty and then check
        bblayers.conf and local.conf if exists in 10 seconds, otherwise
        raise init bitbake faild
        '''
        self.client.check_change_ugid(
            container=container,
            container_user=oebuild_const.CONTAINER_USER)
        self._install_sudo(container=container)

        res = self.client.container_exec_command(
            container=container,
            command=f"bash /home/{oebuild_const.CONTAINER_USER}/.bashrc",
            user=oebuild_const.CONTAINER_USER,
            params={
                "work_space": f"/home/{oebuild_const.CONTAINER_USER}",
                "stream": False
            })
        if res.exit_code != 0:
            raise ValueError(res.output.decode())
            # raise ValueError("bitbake init faild")

    def _install_sudo(self, container: Container):
        self._replace_yum_mirror(container=container)

        resp = self.client.container_exec_command(
            container=container,
            user='root',
            command="which sudo",
            params={
                "work_space": f"/home/{oebuild_const.CONTAINER_USER}",
                "stream": False
            })
        if resp.exit_code != 0:
            logger.info(
                "=========================install sudo===============================")
            self._install_software(container=container, software="sudo")

    def _replace_yum_mirror(self, container: Container):
        """
        replace the yum mirror in container

        Args:
            container (Container): 目标容器

        Returns:
            None
        """
        self.client.container_exec_command(
            container=container,
            user='root',
            command=r"""
sed -i 's/repo.openeuler.org/mirrors.huaweicloud.com\/openeuler/g' /etc/yum.repos.d/openEuler.repo
            """,
            params={
                "work_space": f"/home/{oebuild_const.CONTAINER_USER}",
                "stream": False
            })

    def _install_software(self, container: Container, software: str):
        resp = self.client.container_exec_command(
            container=container,
            user='root',
            command=f"yum install {software} -y",
            params={
                "work_space": f"/home/{oebuild_const.CONTAINER_USER}",
                "stream": True
            })
        for line in resp.output:
            logger.info(line.decode().strip('\n'))

    def init_bash(self, container: Container, build_dir_name):
        '''
        Bitbake will initialize the compilation environment by reading
        the user initialization script first, then making directional
        substitutions, and finally writing the initialization script
        '''
        # read container default user .bashrc content
        content = self.bashrc.get_bashrc_content()

        # get host proxy information and set in container
        host_proxy = oebuild_util.get_host_proxy(oebuild_const.PROXY_LIST)
        init_proxy_command = self._set_container_proxy(host_proxy=host_proxy)

        # get nativesdk environment path automatic for next step
        sdk_env_path = oebuild_util.get_nativesdk_environment(container=container)
        init_sdk_command = f'. {oebuild_const.NATIVESDK_DIR}/{sdk_env_path}'
        # get template dir for initialize yocto build environment
        template_dir = f"{oebuild_const.CONTAINER_SRC}/yocto-meta-openeuler/.oebuild"
        set_template = f'export TEMPLATECONF="{template_dir}"'

        init_oe_comand = f'. {oebuild_const.CONTAINER_SRC}/yocto-poky/oe-init-build-env \
            {oebuild_const.CONTAINER_BUILD}/{build_dir_name}'
        init_command = [init_proxy_command, init_sdk_command, set_template, init_oe_comand]
        new_content = self.bashrc.init_bashrc_content(content, init_command)

        self.bashrc.update_bashrc(content=new_content)

    def _set_container_proxy(self, host_proxy):
        init_proxy_command = ""
        for key, value in host_proxy.items():
            key_git = key.replace('_', '.')
            command = f'export {key}={value}; git config --global {key_git} {value};'
            init_proxy_command = f'{init_proxy_command} {command}'
        return init_proxy_command
