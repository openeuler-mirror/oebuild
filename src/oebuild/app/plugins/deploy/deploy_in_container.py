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
import subprocess

from docker.models.containers import Container

from oebuild.local_conf import NATIVE_GCC_DIR, SSTATE_CACHE
from oebuild.parse_env import ParseEnv, EnvContainer
from oebuild.docker_proxy import DockerProxy
from oebuild.configure import Configure
from oebuild.parse_compile import ParseCompile
from oebuild.m_log import logger
import oebuild.app.plugins.bitbake.const as bitbake_const
from oebuild.app.plugins.bitbake.base_build import BaseBuild

class InContainer(BaseBuild):
    '''
    bitbake command execute in container
    '''

    def __init__(self, configure: Configure):
        self.configure = configure
        self.client = DockerProxy()
        self.container_id = None
        self.arch = None
        self.timestamp = None


    def __del__(self):
        if self.container_id is None:
            return
        # try:
        #     container = self.client.get_container(self.container_id)
        #     self.client.stop_container(container=container)
        # except Exception as e_p:
        #     raise e_p

    def exec(self, parse_env: ParseEnv, parse_compile: ParseCompile, command):
        '''
        execute bitbake command
        '''
        logger.info("bitbake starting ...")
        # check docker image if exists
        docker_proxy = DockerProxy()
        if not docker_proxy.is_image_exists(parse_compile.docker_image):
            logger.error(f'''the docker image does not exists, please run fellow command:
    `oebuild update docker`''')
            return

        self.deal_env_container(
            env=parse_env,
            toolchain_dir=parse_compile.toolchain_dir,
            sstate_cache=parse_compile.sstate_cache,
            docker_image=parse_compile.docker_image)

        self.exec_compile(parse_compile=parse_compile, command=command)

    def deal_env_container(self,
                           env: ParseEnv,
                           toolchain_dir=None,
                           sstate_cache = None,
                           docker_image = ""):
        '''
        This operation realizes the processing of the container,
        controls how the container is processed by parsing the env
        variable, if the container does not exist, or the original
        environment and the current environment that needs to be set
        are inconsistent, you need to create a new container, otherwise
        directly enable the sleeping container
        '''
        cwd_name = os.path.basename(os.getcwd())
        volumns = []
        volumns.append(self.configure.source_dir() + ':' + bitbake_const.CONTAINER_SRC)
        volumns.append(os.path.join(self.configure.build_dir(), cwd_name)
            + ':' +
            os.path.join(bitbake_const.CONTAINER_BUILD, cwd_name))
        if toolchain_dir is not None:
            volumns.append(toolchain_dir + ":" + NATIVE_GCC_DIR)

        if sstate_cache is not None:
            volumns.append(sstate_cache + ":" + SSTATE_CACHE)

        try:
            env_container = EnvContainer(

                volumns=volumns,
                short_id=""
            )
            check_container = env.is_same_container(data=env_container)
        except Exception as e_p:
            raise e_p

        if not check_container \
                or env.container.short_id is None \
                or not self.client.is_container_exists(env.container.short_id):
            # judge which container
            config = self.configure.parse_oebuild_config()
            container_config = config.docker
            container:Container = self.client.container_run_simple(
                image=docker_image,
                volumes=volumns) # type: ignore

            env_container.short_id = container.short_id
            env.set_env_container(env_container)
            env.export_env()

        self.container_id = env.container.short_id
        container:Container = self.client.get_container(self.container_id) # type: ignore
        if not self.client.is_container_running(container):
            self.client.start_container(container)

    def exec_compile(self, parse_compile: ParseCompile, command: str = ""):
        '''
        execute compile task
        '''
        container:Container = self.client.get_container(self.container_id) # type: ignore

        self.init_bash(container=container,
                       build_dir=os.path.basename(os.getcwd()))

        try:
            self.init_bitbake(container=container)
        except ValueError as v_e:
            logger.error(str(v_e))
            return

        # add bblayers, this action must before replace local_conf
        bblayers_dir = os.path.join(os.getcwd(), "conf", "bblayers.conf")
        self.add_bblayers(
            bblayers_dir=bblayers_dir,
            pre_dir=bitbake_const.CONTAINER_SRC,
            base_dir=self.configure.source_dir(),
            layers=parse_compile.layers)

        # replace local_conf
        local_dir = os.path.join(os.getcwd(), 'conf', 'local.conf')
        self.replace_local_conf(
            parse_compile=parse_compile, local_dir=local_dir)

        self._copy_qemuboot_file(container,self.arch, self.timestamp)
        # self._copy_script_file(container)
        _work_space = f"/home/{bitbake_const.CONTAINER_USER}"

        content = self._get_bashrc_content(container=container)
        for b_s in bitbake_const.BASH_BANNER.split('\n'):
            b_s = f"echo {b_s}{bitbake_const.BASH_END_FLAG}"
            content = self._add_bashrc(content=content, line=b_s)

        content = self._add_bashrc(content=content, line=command)
        self.update_bashrc(container=container, content=content)
      
        docker_cmd = f'docker exec --privileged -it -u {bitbake_const.CONTAINER_USER} {container.short_id} bash'
        os_tty_result = os.system(docker_cmd) 

        print(f"docker_cmd returned: {docker_cmd}")
        print(f"os.system() returned: {os_tty_result}")

        try:
            os.remove("generated_conf.qemuboot.conf")
            print(f"Conf file deleted")
        except FileNotFoundError:
            print(f"Conf file does not exist")
            
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
            command=f"bash /home/{bitbake_const.CONTAINER_USER}/.bashrc",
            user=bitbake_const.CONTAINER_USER,
            work_space=f"/home/{bitbake_const.CONTAINER_USER}",
            stream=False)
        if res.exit_code != 0:
            raise ValueError(res.output.decode())
            # raise ValueError("bitbake init faild")

    def _check_change_ugid(self, container: Container):
        res = self.client.container_exec_command(
            container=container,
            user='root',
            command=f"id {bitbake_const.CONTAINER_USER}",
            work_space=f"/home/{bitbake_const.CONTAINER_USER}",
            stream=False)
        if res.exit_code != 0:
            raise ValueError("check docker user id faild")

        res_cont = res.output.decode()

        cuids = res_cont.split(' ')
        # get uid from container in default user
        pattern = re.compile(r'(?<=uid=)\d{1,}(?=\(' + bitbake_const.CONTAINER_USER + r'\))')
        match_uid = pattern.search(cuids[0])
        if match_uid:
            cuid = match_uid.group()
        else:
            raise ValueError(f"can not get container {bitbake_const.CONTAINER_USER} uid")
        # get gid from container in default user
        pattern = re.compile(r'(?<=gid=)\d{1,}(?=\(' + bitbake_const.CONTAINER_USER + r'\))')
        match_gid = pattern.search(cuids[1])
        if match_gid:
            cgid = match_gid.group()
        else:
            raise ValueError(f"can not get container {bitbake_const.CONTAINER_USER} gid")

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
            command=f"usermod -u {uid} {bitbake_const.CONTAINER_USER}",
            work_space=f"/home/{bitbake_const.CONTAINER_USER}",
            stream=False)

    def _change_container_gid(self, container: Container, gid: int):
        self.client.container_exec_command(
            container=container,
            user='root',
            command=f"groupmod -g {gid} {bitbake_const.CONTAINER_USER}",
            work_space=f"/home/{bitbake_const.CONTAINER_USER}",
            stream=False)

    def _install_sudo(self, container: Container):
        self._replace_yum_mirror(container=container)

        resp = self.client.container_exec_command(
            container=container,
            user='root',
            command="which sudo",
            work_space=f"/home/{bitbake_const.CONTAINER_USER}",
            stream=False
        )
        if resp.exit_code != 0:
            logger.info(
                "=========================install sudo===============================")
            self._install_software(container=container, software="sudo")

    def _replace_yum_mirror(self, container: Container):
        self.client.container_exec_command(
            container=container,
            user='root',
            command=r"sed -i 's/repo.openeuler.org/mirrors.huaweicloud.com\/openeuler/g' /etc/yum.repos.d/openEuler.repo",
            work_space=f"/home/{bitbake_const.CONTAINER_USER}",
            stream=False
        )

    def _install_software(self, container: Container, software: str):
        resp = self.client.container_exec_command(
            container=container,
            user='root',
            command=f"yum install {software} -y",
            work_space=f"/home/{bitbake_const.CONTAINER_USER}",
            stream=True
        )
        for line in resp.output:
            logger.info(line.decode().strip('\n'))

    def init_bash(self, container: Container, build_dir):
        '''
        Bitbake will initialize the compilation environment by reading
        the user initialization script first, then making directional
        substitutions, and finally writing the initialization script
        '''
        # read container default user .bashrc content
        content = self._get_bashrc_content(container=container)

        init_sdk_command = '. /opt/buildtools/nativesdk/environment-setup-x86_64-pokysdk-linux'
        set_template = f'export TEMPLATECONF="{bitbake_const.CONTAINER_SRC}/yocto-meta-openeuler/.oebuild"'
        init_oe_comand = f'. {bitbake_const.CONTAINER_SRC}/yocto-poky/oe-init-build-env \
            {bitbake_const.CONTAINER_BUILD}/{build_dir}'
        init_command = [init_sdk_command, set_template, init_oe_comand]
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
            to_path=f'/home/{bitbake_const.CONTAINER_USER}')
        container.exec_run(
            cmd=f"mv /home/{bitbake_const.CONTAINER_USER}/{tmp_file} /home/{bitbake_const.CONTAINER_USER}/.bashrc",
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
        content = self.client.container_exec_command(
            container=container,
            command=f"cat /home/{bitbake_const.CONTAINER_USER}/.bashrc",
            user="root",
            work_space=None,
            stream=False).output

        return content.decode()

    def _copy_qemuboot_file(self, container, arch, time_stamp):

        current_directory = os.getcwd()
        last_folder_name = os.path.basename(current_directory)
        folder_path = "./tmp/deploy/images/"
        subfolders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
        unique_subfolder = ""
        # unique_subfolder
        if len(subfolders) == 1:
            unique_subfolder = subfolders[0]
            
        else:
            print("No unique subfolders")

        
        script_content = f"""
        [config_bsp]

        machine=qemuarm64
        initrd=./output/{time_stamp}/openeuler-image-*-{arch}-*.rootfs.cpio.gz
        kernel=./output/{time_stamp}/zImage-5.10.0
        SERIAL_CONSOLES = "115200;ttyS0 115200;ttyS1"
        QB_NET=none
        QB_MEM=1024
        QB_DEFAULT_FSTYPE=cpio.gz
        # QB_SLIRP_OPT="-netdev user,id=net0,hostfwd=tcp::8080-:80,hostfwd=tcp::2222-:22"
        # QB_NETWORK_DEVICE="-device virtio-net-device,netdev=tap0"
        STAGING_DIR_NATIVE=/opt/buildtools/nativesdk/sysroots/
        STAGING_BINDIR_NATIVE=/opt/buildtools/nativesdk/sysroots/x86_64-pokysdk-linux/usr/bin
        """
        
        with open("generated_conf.qemuboot.conf", "w") as file:
            file.write(script_content)
        
        # directory = './tmp/deploy/images/'
        # subdirs = [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]

        # if len(subdirs) == 1:
        #     full_path = os.path.join(directory, subdirs[0])
        #     print(full_path)
        # else:
        #     print("Wrong directory for qemuboot file.")


        logger.info("Copying qemuboot file into the docker container...")

        # to_path=f"/home/{bitbake_const.CONTAINER_USER}/{last_folder_name}/tmp/deploy/images/{unique_subfolder}/{time_stamp}/"
        to_path = f"/home/{bitbake_const.CONTAINER_USER}/{last_folder_name}/"
        logger.info(f"To path: {to_path}")
        self.client.copy_to_container(
            container=container, 
            source_path="./generated_conf.qemuboot.conf", 
            to_path=to_path) #aarch64-std  {bitbake_const.CONTAINER_USER}
            # to_path=f"/home/{bitbake_const.CONTAINER_USER}/{last_folder_name}/") #aarch64-std  {bitbake_const.CONTAINER_USER}



            # /home/openeuler/build/aarch64-std/tmp/deploy/images/qemu-aarch64/


#     def _copy_script_file(self,container):
#         '''
#         Copy script file for enabling network of qemu
#         '''
#         script_content = """#!/bin/bash
# ifconfig $1 192.168.10.1 up
#         """
#         # chmod a+x /etc/qemu-ifup
#         with open("qemu-ifup", "w") as file:
#             file.write(script_content)
#         os.chmod("qemu-ifup", 0o755)
#         logger.info("Copying script file into the docker container...")
#         self.client.copy_to_container(
#             container=container, 
#             source_path="./qemu-ifup", 
#             to_path="/etc/")
#         os.remove("qemu-ifup")