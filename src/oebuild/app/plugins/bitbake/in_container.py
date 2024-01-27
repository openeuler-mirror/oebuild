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
import re
import os
import sys

from docker.models.containers import Container, ExecResult

from oebuild.parse_env import ParseEnv, EnvContainer
from oebuild.docker_proxy import DockerProxy
from oebuild.configure import Configure
from oebuild.parse_compile import ParseCompile, DockerParam
from oebuild.m_log import logger
from oebuild.app.plugins.bitbake.base_build import BaseBuild
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

    def exec(self, parse_env: ParseEnv, parse_compile: ParseCompile, command):
        '''
        execute bitbake command
        '''
        logger.info("Bitbake starting ...")

        docker_param: DockerParam = None
        if parse_compile.docker_param is not None:
            docker_param = parse_compile.docker_param
        else:
            docker_param = self._trans_docker_param(
                docker_image=parse_compile.docker_image,
                toolchain_dir=parse_compile.toolchain_dir,
                sstate_cache=parse_compile.sstate_cache)

        # check docker image if exists
        docker_proxy = DockerProxy()
        if not docker_proxy.is_image_exists(docker_param.image):
            logger.error('''The docker image does not exists, please run fellow command:
    `oebuild update docker`''')
            return

        self.deal_env_container(env=parse_env, docker_param=docker_param)
        self.exec_compile(parse_compile=parse_compile, command=command)

    def _trans_docker_param(self,
                            docker_image: str,
                            toolchain_dir: str = None,
                            sstate_cache: str = None) -> DockerParam:
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
        if sstate_cache is not None:
            volumns.append(sstate_cache + ":" + oebuild_const.SSTATE_CACHE)

        docker_param = DockerParam(
            image=docker_image,
            parameters=parameters,
            volumns=volumns,
            command="bash"
        )
        return docker_param

    def deal_env_container(self, env: ParseEnv, docker_param: DockerParam):
        '''
        This operation realizes the processing of the container,
        controls how the container is processed by parsing the env
        variable, if the container does not exist, or the original
        environment and the current environment that needs to be set
        are inconsistent, you need to create a new container, otherwise
        directly enable the sleeping container
        '''
        if env.container is None \
                or env.container.short_id is None \
                or not self.client.is_container_exists(env.container.short_id):
            # judge which container
            container: Container = self.client.create_container(
                image=docker_param.image,
                parameters=docker_param.parameters,
                volumes=docker_param.volumns,
                command=docker_param.command)

            env_container = EnvContainer(container.short_id)
            env.set_env_container(env_container)
            env.export_env()

        self.container_id = env.container.short_id
        container: Container = self.client.get_container(self.container_id)  # type: ignore
        if not self.client.is_container_running(container):
            self.client.start_container(container)

    def exec_compile(self, parse_compile: ParseCompile, command: str = ""):
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
            layers=parse_compile.layers)

        # replace local_conf
        local_dir = os.path.join(os.getcwd(), 'conf', 'local.conf')
        self.replace_local_conf(
            parse_compile=parse_compile, local_dir=local_dir)

        # add auto execute command for example: bitbake busybox
        if command is not None and command != "":
            content = self._get_bashrc_content(container=container)
            new_content = self._add_bashrc(content=content, line=command)
            self.update_bashrc(container=container, content=new_content)
            res: ExecResult = self.client.container_exec_command(
                container=container,
                command="bash .bashrc",
                user=oebuild_const.CONTAINER_USER,
                work_space=f"/home/{oebuild_const.CONTAINER_USER}",
                demux=True)
            exit_code = 0
            for line in res.output:
                if line[1] is not None:
                    logger.error(line[1].decode().strip('\n'))
                    exit_code = 1
                else:
                    logger.info(line[0].decode().strip('\n'))
            sys.exit(exit_code)
        else:
            content = self._get_bashrc_content(container=container)
            for b_s in oebuild_const.BASH_BANNER.split('\n'):
                b_s = f"echo {b_s}"
                content = self._add_bashrc(content=content, line=b_s)
            self.update_bashrc(container=container, content=content)
            os.system(
                f"docker exec -it -u {oebuild_const.CONTAINER_USER} {container.short_id} bash")

        self.restore_bashrc(container=container)

    def init_bitbake(self, container: Container):
        '''
        init_bitbake will start a container with pty and then check
        bblayers.conf and local.conf if exists in 10 seconds, otherwise
        raise init bitbake faild
        '''
        self._check_change_ugid(container=container)
        self._install_sudo(container=container)

        res = self.client.container_exec_command(
            container=container,
            command=f"bash /home/{oebuild_const.CONTAINER_USER}/.bashrc",
            user=oebuild_const.CONTAINER_USER,
            work_space=f"/home/{oebuild_const.CONTAINER_USER}",
            stream=False)
        if res.exit_code != 0:
            raise ValueError(res.output.decode())
            # raise ValueError("bitbake init faild")

    def _check_change_ugid(self, container: Container):
        res = self.client.container_exec_command(
            container=container,
            user='root',
            command=f"id {oebuild_const.CONTAINER_USER}",
            work_space=f"/home/{oebuild_const.CONTAINER_USER}",
            stream=False)
        if res.exit_code != 0:
            raise ValueError("check docker user id faild")

        res_cont = res.output.decode()

        cuids = res_cont.split(' ')
        # get uid from container in default user
        pattern = re.compile(r'(?<=uid=)\d{1,}(?=\(' + oebuild_const.CONTAINER_USER + r'\))')
        match_uid = pattern.search(cuids[0])
        if match_uid:
            cuid = match_uid.group()
        else:
            raise ValueError(f"can not get container {oebuild_const.CONTAINER_USER} uid")
        # get gid from container in default user
        pattern = re.compile(r'(?<=gid=)\d{1,}(?=\(' + oebuild_const.CONTAINER_USER + r'\))')
        match_gid = pattern.search(cuids[1])
        if match_gid:
            cgid = match_gid.group()
        else:
            raise ValueError(f"can not get container {oebuild_const.CONTAINER_USER} gid")

        # judge host uid and gid are same with container uid and gid
        # if not same and change container uid and gid equal to host's uid and gid
        if os.getuid() != cuid:
            self._change_container_uid(container=container, uid=os.getuid())
        if os.getgid() != cgid:
            self._change_container_gid(container=container, gid=os.getgid())

    def _change_container_uid(self, container: Container, uid: int):
        self.client.container_exec_command(
            container=container,
            user='root',
            command=f"usermod -u {uid} {oebuild_const.CONTAINER_USER}",
            work_space=f"/home/{oebuild_const.CONTAINER_USER}",
            stream=False)

    def _change_container_gid(self, container: Container, gid: int):
        self.client.container_exec_command(
            container=container,
            user='root',
            command=f"groupmod -g {gid} {oebuild_const.CONTAINER_USER}",
            work_space=f"/home/{oebuild_const.CONTAINER_USER}",
            stream=False)

    def _install_sudo(self, container: Container):
        self._replace_yum_mirror(container=container)

        resp = self.client.container_exec_command(
            container=container,
            user='root',
            command="which sudo",
            work_space=f"/home/{oebuild_const.CONTAINER_USER}",
            stream=False
        )
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
            work_space=f"/home/{oebuild_const.CONTAINER_USER}",
            stream=False
        )

    def _install_software(self, container: Container, software: str):
        resp = self.client.container_exec_command(
            container=container,
            user='root',
            command=f"yum install {software} -y",
            work_space=f"/home/{oebuild_const.CONTAINER_USER}",
            stream=True
        )
        for line in resp.output:
            logger.info(line.decode().strip('\n'))

    def init_bash(self, container: Container, build_dir_name):
        '''
        Bitbake will initialize the compilation environment by reading
        the user initialization script first, then making directional
        substitutions, and finally writing the initialization script
        '''
        # read container default user .bashrc content
        content = self._get_bashrc_content(container=container)

        # get host proxy information and set in container
        init_proxy_command = ""
        host_proxy = oebuild_util.get_host_proxy(oebuild_const.PROXY_LIST)
        for key, value in host_proxy.items():
            key_git = key.replace('_', '.')
            command = f'export {key}={value}; git config --global {key_git} {value};'
            init_proxy_command = f'{init_proxy_command} {command}'

        # get nativesdk environment path automatic for next step
        sdk_env_path = oebuild_util.get_nativesdk_environment(container=container)
        init_sdk_command = f'. {oebuild_const.NATIVESDK_DIR}/{sdk_env_path}'
        # get template dir for initialize yocto build environment
        template_dir = f"{oebuild_const.CONTAINER_SRC}/yocto-meta-openeuler/.oebuild"
        set_template = f'export TEMPLATECONF="{template_dir}"'

        init_oe_comand = f'. {oebuild_const.CONTAINER_SRC}/yocto-poky/oe-init-build-env \
            {oebuild_const.CONTAINER_BUILD}/{build_dir_name}'
        init_command = [init_proxy_command, init_sdk_command, set_template, init_oe_comand]
        new_content = self._init_bashrc_content(content, init_command)

        self.update_bashrc(container=container, content=new_content)

    def update_bashrc(self, container: Container, content: str):
        '''
        update user initialization script by replace file, first create
        a file and writed content and copy it to container's .bashrc, finally
        remove it
        '''
        tmp_file = self._set_tmpfile_content(content)
        self.client.copy_to_container(
            container=container,
            source_path=tmp_file,
            to_path=f'/home/{oebuild_const.CONTAINER_USER}')
        container.exec_run(
            cmd=f'''
            mv /home/{oebuild_const.CONTAINER_USER}/{tmp_file} /home/{oebuild_const.CONTAINER_USER}/.bashrc
            ''',
            user="root"
        )
        os.remove(tmp_file)

    def restore_bashrc(self, container: Container):
        '''
        Restoring .bashrc will strip out the command line
        content added during bitbake initialization
        '''
        old_content = self._get_bashrc_content(container=container)
        self.update_bashrc(container=container,
                           content=self._restore_bashrc_content(old_content=old_content))

    def _get_bashrc_content(self, container: Container):
        res = self.client.container_exec_command(
            container=container,
            command=f"cat /home/{oebuild_const.CONTAINER_USER}/.bashrc",
            user="root",
            work_space=None,
            stream=False)

        if res.exit_code != 0:
            logger.error(res.output)
            sys.exit(1)

        return res.output.decode()
