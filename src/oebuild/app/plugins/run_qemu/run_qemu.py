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
import oebuild.const as oebuild_const
from oebuild.bashrc import Bashrc


class RunQemu(OebuildCommand):
    '''
    The command for run in qemu platform.
    '''

    help_msg = 'run in qemu platform'
    description = textwrap.dedent('''
            The command for run in qemu platform.
            ''')

    def __init__(self):
        self.configure = Configure()
        self.client = None
        self.container_id = None
        self.work_dir = os.getcwd()
        self.bashrc = Bashrc()

        super().__init__('run_qemu', self.help_msg, self.description)

    def __del__(self):
        if self.client is not None:
            try:
                container = self.client.get_container(self.container_id)
                self.client.delete_container(container=container,
                                             is_force=True)
            except DockerException:
                print(f"""
the container {self.container_id} failed to be destroyed, please run

`docker rm {self.container_id}`

""")

    def do_add_parser(self, parser_adder):
        parser = self._parser(parser_adder, usage='''
  %(prog)s [command]
''')
        parser_adder.add_argument(
            'command',
            nargs='?',
            default=None,
            help='''The name of the directory that will be initialized''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        try:
            self.client = DockerProxy()
        except DockerException:
            logger.error("Please install docker first!!!")
            sys.exit(-1)
        logger.info('Run QEMU......')

        docker_image = self.get_docker_image()
        self._check_qemu_ifup()
        self.deal_env_container(docker_image=docker_image)
        self.bashrc.set_container(
            container=self.client.get_container(container_id=self.container_id))
        self.bashrc.set_user("root")

        for index, param in enumerate(unknown):
            if param.startswith("qemuparams"):
                unknown[index] = "qemuparams=\"" + param.split("=")[1] + "\""
            if param.startswith("bootparams"):
                unknown[index] = "bootparams=\"" + param.split("=")[1] + "\""
        self.exec_qemu(' '.join(unknown))

    def exec_qemu(self, params):
        '''
        exec qemu
        '''
        container: Container = self.client.get_container(
            self.container_id)  # type: ignore
        # self.bak_bash(container=container)
        self.init_bash(container=container)
        content = self.bashrc.get_bashrc_content()
        qemu_helper_usr = os.path.join(
            oebuild_const.CONTAINER_BUILD,
            "tmp/work/x86_64-linux/qemu-helper-native/1.0-r1/recipe-sysroot-native/usr"
        )
        qemu_helper_dir = os.path.join(
            oebuild_const.CONTAINER_BUILD,
            "tmp/work/x86_64-linux/qemu-helper-native")
        staging_bindir_native = f"""
if [ ! -d {qemu_helper_usr} ];then
    mkdir -p {qemu_helper_usr}
    chown -R {oebuild_const.CONTAINER_USER}:{oebuild_const.CONTAINER_USER} {qemu_helper_dir}
    ln -s /opt/buildtools/nativesdk/sysroots/x86_64-openeulersdk-linux/usr/bin {qemu_helper_usr}
fi
"""
        content = self.bashrc.add_bashrc(content=content, line=staging_bindir_native)
        # content = self.bashrc.add_bashrc(
        #     content=content,
        #     line=f"mv -f /root/{self.old_bashrc} /root/.bashrc")
        content = self.bashrc.add_bashrc(content=content,
                                         line=f"runqemu {params} && exit")
        self.bashrc.update_bashrc(content=content)
        os.system(f"docker exec -it -u root {container.short_id}  bash")

        # self.bashrc.restore_bashrc()

    def _check_qemu_ifup(self, ):
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

    def deal_env_container(self, docker_image):
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
        volumns.append(self.work_dir + ':' + oebuild_const.CONTAINER_BUILD)
        volumns.append(self.configure.source_dir() + ':' +
                       oebuild_const.CONTAINER_SRC)

        parameters = oebuild_const.DEFAULT_CONTAINER_PARAMS + " --privileged"
        container: Container = self.client.create_container(
            image=docker_image,
            parameters=parameters,
            volumes=volumns,
            command="bash")

        self.container_id = container.short_id
        container: Container = self.client.get_container(self.container_id)
        if not self.client.is_container_running(container):
            self.client.start_container(container)
        # set sudo.conf be root
        cmd = "chown -R root:root /etc/sudo.conf /etc/sudoers /etc/sudoers.d"
        self.client.container_exec_command(container=container,
                                           command=cmd,
                                           user="root",
                                           params={"stream": False})

    def get_docker_image(self):
        '''
        this is function is to get openeuler docker image automatic
        '''
        return oebuild_const.DEFAULT_DOCKER

    def init_bash(self, container: Container):
        '''
        Bitbake will initialize the compilation environment by reading
        the user initialization script first, then making directional
        substitutions, and finally writing the initialization script
        '''
        # read container default user .bashrc content
        content = self.bashrc.get_bashrc_content()
        # get nativesdk environment path automatic for next step
        sdk_env_path = oebuild_util.get_nativesdk_environment(
            container=container)
        init_sdk_command = f'. {oebuild_const.NATIVESDK_DIR}/{sdk_env_path}'
        content = self.bashrc.add_bashrc(content=content, line=init_sdk_command)
        init_oe_command = f'. {oebuild_const.CONTAINER_SRC}/yocto-poky/oe-init-build-env \
            {oebuild_const.CONTAINER_BUILD}'
        content = self.bashrc.add_bashrc(content=content, line=init_oe_command)
        self.bashrc.update_bashrc(content=content)
