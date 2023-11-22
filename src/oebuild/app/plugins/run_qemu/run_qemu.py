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

import argparse
import textwrap
import os
import sys

from docker.models.containers import Container
from docker.errors import DockerException

import oebuild.util as oebuild_util
from oebuild.docker_proxy import DockerProxy
from oebuild.command import OebuildCommand
from oebuild.configure import Configure
from oebuild.m_log import logger

CONTAINER_BUILD = '/home/openeuler/build'
DEFAULT_DOCKER = "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container:latest"
CONTAINER_SRC = '/usr1/openeuler/src'
CONTAINER_USER = "openeuler"

class RunQemu(OebuildCommand):
    '''
    The command for run in qemu platform.
    '''
    def __init__(self):
        self.configure = Configure()
        self.client = None
        self.container_id = None
        self.work_dir = os.getcwd()
        self.old_bashrc = None

        super().__init__(
            'run_qemu',
            'run in qemu platform',
            textwrap.dedent('''
            The command for run in qemu platform.
            ''')
        )

    def __del__(self):
        if self.client is not None:
            print("""

            container is being destroyed, please wait ...

""")
            try:
                container = self.client.get_container(self.container_id)
                self.client.stop_container(container=container)
                self.client.delete_container(container=container)
            except DockerException:
                print(f"""
the container {self.container_id} failed to be destroyed, please run 

`docker rm {self.container_id}`

""")

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''
  %(prog)s [command]
''')
        parser_adder.add_argument(
            'command', nargs='?', default=None,
            help='''The name of the directory that will be initialized''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        try:
            self.client = DockerProxy()
        except DockerException:
            logger.error("please install docker first!!!")
            return
        logger.info('Run QEMU......')

        docker_image = self.get_docker_image()
        self._check_qemu_ifup()
        self.deal_env_container(docker_image=docker_image)
        # container:Container = self.client.get_container(self.container_id)

        #
        for index, param in enumerate(unknown):
            if param.startswith("qemuparams"):
                unknown[index] = "qemuparams=\""+param.split("=")[1]+"\""
            if param.startswith("bootparams"):
                unknown[index] = "bootparams=\""+param.split("=")[1]+"\""
        self.exec_qemu(' '.join(unknown))

    def exec_qemu(self, params):
        '''
        exec qemu
        '''
        container:Container = self.client.get_container(self.container_id) # type: ignore
        self.bak_bash(container=container)
        self.init_bash(container=container)
        content = self._get_bashrc_content(container=container)
        qemu_helper_usr = CONTAINER_BUILD+"/tmp/work/x86_64-linux/qemu-helper-native/1.0-r1/recipe-sysroot-native/usr"
        qemu_helper_dir = CONTAINER_BUILD+"/tmp/work/x86_64-linux/qemu-helper-native"
        STAGING_BINDIR_NATIVE = f"""
if [ ! -d {qemu_helper_usr} ];then
    mkdir -p {qemu_helper_usr}
    chown -R {CONTAINER_USER}:{CONTAINER_USER} {qemu_helper_dir}
    ln -s /opt/buildtools/nativesdk/sysroots/x86_64-pokysdk-linux/usr/bin {qemu_helper_usr}
fi
"""
        content = oebuild_util.add_bashrc(content=content, line=STAGING_BINDIR_NATIVE)
        content = oebuild_util.add_bashrc(content=content, line=f"mv -f /root/{self.old_bashrc} /root/.bashrc")
        content = oebuild_util.add_bashrc(content=content, line=f"""runqemu {params} && exit""")
        self.update_bashrc(container=container, content=content)
        os.system(f"docker exec -it -u root {container.short_id}  bash")

        self.restore_bashrc(container=container)

    def restore_bashrc(self, container: Container):
        '''
        Restoring .bashrc will strip out the command line
        content added during bitbake initialization
        '''
        old_content = self._get_bashrc_content(container=container)
        self.update_bashrc(container=container,
                           content=oebuild_util.restore_bashrc_content(old_content=old_content))

    def _check_qemu_ifup(self,):
        if not os.path.exists("/etc/qemu-ifup"):
            print("""please create a virtual network interface as follows:
                  1, open /etc/qemu-ifup in vim or vi
                  2, add content to qemu-ifup
                        #!/bin/bash
                        ifconfig $1 192.168.10.1 up
                  3, save qemu-ifup and exit
                  4, run command `chmod a+x /etc/qemu-ifup` with sudo or in root usermod
now, you can continue run `oebuild runqemu` in compile directory
                  """)
            sys.exit(0)
        return

    def deal_env_container(self,docker_image):
        '''
        This operation realizes the processing of the container,
        controls how the container is processed by parsing the env
        variable, if the container does not exist, or the original
        environment and the current environment that needs to be set
        are inconsistent, you need to create a new container, otherwise
        directly enable the sleeping container
        '''
        volumns = []
        volumns.append("/dev/net/tun:/dev/net/tun")
        volumns.append("/etc/qemu-ifup:/etc/qemu-ifup")
        volumns.append(self.work_dir + ':' + CONTAINER_BUILD)
        volumns.append(self.configure.source_dir() + ':' + CONTAINER_SRC)
        container:Container = self.client.container_run_simple(
            image=docker_image,
            volumes=volumns,
            is_priv=True) # type: ignore

        self.container_id = container.short_id
        container:Container = self.client.get_container(self.container_id) # type: ignore
        if not self.client.is_container_running(container):
            self.client.start_container(container)

    def get_docker_image(self):
        '''
        this is function is to get openeuler docker image automatic
        '''
        return DEFAULT_DOCKER

    def bak_bash(self, container: Container):
        '''
        xxx
        '''
        old_bash = oebuild_util.generate_random_str(6)
        self.client.container_exec_command(
            container=container,
            command=f"cp /root/.bashrc /root/{old_bash}",
            user="root",
            work_space=None,
            stream=False)
        self.old_bashrc = old_bash

    def init_bash(self, container: Container):
        '''
        Bitbake will initialize the compilation environment by reading
        the user initialization script first, then making directional
        substitutions, and finally writing the initialization script
        '''
        # read container default user .bashrc content
        content = self._get_bashrc_content(container=container)

        init_sdk_command = '. /opt/buildtools/nativesdk/environment-setup-x86_64-pokysdk-linux'
        init_oe_command = f'. {CONTAINER_SRC}/yocto-poky/oe-init-build-env {CONTAINER_BUILD}'
        init_command = [init_sdk_command, init_oe_command]
        new_content = oebuild_util.init_bashrc_content(content, init_command)
        self.update_bashrc(container=container, content=new_content)

    def _get_bashrc_content(self, container: Container):
        content = self.client.container_exec_command(
            container=container,
            command="cat /root/.bashrc",
            user="root",
            work_space=None,
            stream=False).output

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
            to_path='/root')
        container.exec_run(
            cmd=f"mv /root/{tmp_file} /root/.bashrc",
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
