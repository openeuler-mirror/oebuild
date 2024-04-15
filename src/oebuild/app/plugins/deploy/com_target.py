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
import re

from docker.models.containers import Container
from docker.errors import DockerException

from oebuild.docker_proxy import DockerProxy
from oebuild.configure import Configure
import oebuild.util as oebuild_util
from oebuild.parse_param import ParseCompileParam
from oebuild.m_log import logger
import oebuild.const as oebuild_const

TARGET_DIR_NAME = "target_dev"
TARGET_SCRIPT_NAME = "oebuild_dev"


class ComTarget:
    '''
    The class is used to deploy-target and undeploy-target, this is a main body, the deploy-target
    and undeploy-target is just a interface and finally go into ComTarget
    '''

    def __init__(self) -> None:
        self.configure = Configure()
        self.client: DockerProxy = None
        self.container_id = None
        self.work_dir = os.getcwd()
        self.old_bashrc = None

    def __del__(self):
        if self.client is not None:
            try:
                container = self.client.get_container(self.container_id)
                self.client.delete_container(container=container, is_force=True)
            except DockerException:
                print(f"""
the container {self.container_id} failed to be destroyed, please run

`docker rm {self.container_id}`

""")

    def exec(self, str_args: str, fun):
        '''
        the exec as a common function that will be invoked by deploy-target and undeploy-target,
        it means this is a entry runner.
        '''
        self.client = DockerProxy()

        if not self._check_compile_directory():
            logger.error("You must be worked in compile directory")
            sys.exit(-1)

        if not self._check_if_docker_compile():
            logger.error("The deploy function only be supported in working with docker build")
            sys.exit(-1)

        if not self._check_yocto_poky():
            logger.error('''
        Please make sure that yocto-poky source code be in src directory, or you can run:
        oebuild update layer''')
            sys.exit(-1)

        if not self._check_conf_directory():
            logger.error('You must work in a exist build directory, '
                         'that mean you built before or initialize '
                         'environment at least')
            sys.exit(-1)

        logger.info("Initializing environment, please wait ...")
        self.deal_env_container(oebuild_const.DEFAULT_DOCKER)
        container: Container = self.client.get_container(self.container_id)
        self._make_and_copy_lib(container=container)
        self.bak_bash(container=container)
        self.init_bash(container=container)
        content = self._get_bashrc_content(container=container)
        content = oebuild_util.add_bashrc(
            content=content,
            line=f"export PATH=$PATH:/home/openeuler/{TARGET_DIR_NAME}")
        content = oebuild_util.add_bashrc(
            content=content,
            line=(f"mv -f /home/{oebuild_const.CONTAINER_USER}/{self.old_bashrc} "
                  f"/home/{oebuild_const.CONTAINER_USER}/.bashrc")
            )
        content = oebuild_util.add_bashrc(
            content=content,
            line=f"{TARGET_SCRIPT_NAME} {fun} {str_args}")
        print(f"{TARGET_SCRIPT_NAME} {str_args}")
        content = oebuild_util.add_bashrc(
            content=content,
            line=f"rm -rf /home/openeuler/{TARGET_DIR_NAME} && exit")
        self.update_bashrc(container=container, content=content)
        os.system(f"docker exec -it -u {oebuild_const.CONTAINER_USER} {container.short_id}  bash")

    def _check_conf_directory(self,):
        # check if exists local.conf
        if not os.path.exists(os.path.join(self.work_dir, "conf/local.conf")):
            return False
        # check if exists bblayers.conf
        if not os.path.exists(os.path.join(self.work_dir, "conf/bblayers.conf")):
            return False
        return True

    def _check_if_docker_compile(self):
        '''
        the deploy feature should only be runed in docker build type
        '''
        compile_path = os.path.join(self.work_dir, "compile.yaml")
        compile_dict = oebuild_util.read_yaml(yaml_path=compile_path)
        parse_compile = ParseCompileParam.parse_to_obj(compile_param_dict=compile_dict)

        if parse_compile.build_in != oebuild_const.BUILD_IN_DOCKER:
            return False
        return True

    def _check_compile_directory(self,):
        '''
        The execution of the bitbake instruction mainly relies
        on compile.yaml, which is initialized by parsing the file
        '''
        return os.path.exists(os.path.join(self.work_dir, 'compile.yaml'))

    def _check_yocto_poky(self,):
        '''
        package deploy need poky lib, so we have a detect about yocto-poky
        '''
        return os.path.exists(self.configure.source_poky_dir())

    def _make_and_copy_lib(self, container: Container):
        # everytime, we should make sure that script is updated, so we make a rm action before copy
        container.exec_run(f"rm -rf /home/openeuler/{TARGET_DIR_NAME}")
        # copy package lib to docker
        curr_path = os.path.dirname(os.path.realpath(__file__))
        lib_path = os.path.join(curr_path, TARGET_DIR_NAME)
        self.client.copy_to_container(
            container=container,
            source_path=lib_path,
            to_path="/home/openeuler/")
        container.exec_run(f"chmod 755 /home/openeuler/{TARGET_DIR_NAME}/{TARGET_SCRIPT_NAME}")

    def deal_env_container(self, docker_image: str):
        '''
        This operation realizes the processing of the container,
        controls how the container is processed by parsing the env
        variable, if the container does not exist, or the original
        environment and the current environment that needs to be set
        are inconsistent, you need to create a new container, otherwise
        directly enable the sleeping container
        '''
        cwd_name = os.path.basename(self.work_dir)
        volumns = []
        volumns.append("/dev/net/tun:/dev/net/tun")
        volumns.append(self.configure.source_dir() + ':' + oebuild_const.CONTAINER_SRC)
        volumns.append(os.path.join(self.configure.build_dir(), cwd_name)
                       + ':' +
                       os.path.join(oebuild_const.CONTAINER_BUILD, cwd_name))

        parameters = oebuild_const.DEFAULT_CONTAINER_PARAMS
        container: Container = self.client.create_container(
            image=docker_image,
            parameters=parameters,
            volumes=volumns,
            command="bash")

        self.container_id = container.short_id
        container: Container = self.client.get_container(self.container_id)  # type: ignore
        if not self.client.is_container_running(container):
            self.client.start_container(container)

    def bak_bash(self, container: Container):
        '''
        before we alter .bashrc we should make a copy or named bak to another where, thus when we
        finished some thing we can restore it.
        '''
        old_bash = oebuild_util.generate_random_str(6)
        self.client.container_exec_command(
            container=container,
            command=(f"cp /home/{oebuild_const.CONTAINER_USER}/.bashrc "
                     f"/home/{oebuild_const.CONTAINER_USER}/{old_bash}"),
            user="root",
            params={'stream': False})
        self.old_bashrc = old_bash

    def init_bash(self, container: Container):
        '''
        Bitbake will initialize the compilation environment by reading
        the user initialization script first, then making directional
        substitutions, and finally writing the initialization script
        '''
        self._check_change_ugid(container=container)
        # read container default user .bashrc content
        content = self._get_bashrc_content(container=container)
        # get nativesdk environment path automatic for next step
        sdk_env_path = oebuild_util.get_nativesdk_environment(container=container)
        init_sdk_command = f'. {oebuild_const.NATIVESDK_DIR}/{sdk_env_path}'
        build_dir_name = os.path.basename(self.work_dir)
        init_oe_command = f'. {oebuild_const.CONTAINER_SRC}/yocto-poky/oe-init-build-env \
            {oebuild_const.CONTAINER_BUILD}/{build_dir_name}'
        init_command = [init_sdk_command, init_oe_command]
        new_content = oebuild_util.init_bashrc_content(content, init_command)
        self.update_bashrc(container=container, content=new_content)

    def _get_bashrc_content(self, container: Container):
        content = self.client.container_exec_command(
            container=container,
            command=f"cat /home/{oebuild_const.CONTAINER_USER}/.bashrc",
            user="root",
            params={'stream': False}).output

        return content.decode()

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
            cmd=(f"mv /home/{oebuild_const.CONTAINER_USER}/{tmp_file} "
                 f"/home/{oebuild_const.CONTAINER_USER}/.bashrc"),
            user="root"
        )
        os.remove(tmp_file)

    def _set_tmpfile_content(self, content: str):
        while True:
            tmp_file = oebuild_util.generate_random_str(6)
            if os.path.exists(tmp_file):
                continue
            with open(tmp_file, 'w', encoding="utf-8") as w_f:
                w_f.write(content)
            break
        return tmp_file

    def restore_bashrc(self, container: Container):
        '''
        Restoring .bashrc will strip out the command line
        content added during bitbake initialization
        '''
        old_content = self._get_bashrc_content(container=container)
        self.update_bashrc(container=container,
                           content=self._restore_bashrc_content(old_content=old_content))

    def _restore_bashrc_content(self, old_content):
        new_content = ''
        for line in old_content.split('\n'):
            line: str = line
            if line.endswith(oebuild_const.BASH_END_FLAG) or line.replace(" ", '') == '':
                continue
            new_content = new_content + line + '\n'
        return new_content

    def _check_change_ugid(self, container: Container):
        params = {
            'work_space': f"/home/{oebuild_const.CONTAINER_USER}",
            'stream': False}
        res = self.client.container_exec_command(
            container=container,
            user='root',
            command=f"id {oebuild_const.CONTAINER_USER}",
            params=params)
        if res.exit_code != 0:
            raise ValueError("check docker user id faild")

        res_cont: str = res.output.decode()

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
        params = {
            'work_space': f"/home/{oebuild_const.CONTAINER_USER}",
            'stream': False
        }
        self.client.container_exec_command(
            container=container,
            user='root',
            command=f"usermod -u {uid} {oebuild_const.CONTAINER_USER}",
            params=params)

    def _change_container_gid(self, container: Container, gid: int):
        params = {
            'work_space': f"/home/{oebuild_const.CONTAINER_USER}",
            'stream': False
        }
        self.client.container_exec_command(
            container=container,
            user='root',
            command=f"groupmod -g {gid} {oebuild_const.CONTAINER_USER}",
            params=params)
