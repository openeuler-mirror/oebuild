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
import re
import configparser
import time

import git

from docker.models.containers import Container
from docker.errors import DockerException

import oebuild.util as oebuild_util
from oebuild.docker_proxy import DockerProxy
from oebuild.command import OebuildCommand
from oebuild.configure import Configure
from oebuild.m_log import logger

CONTAINER_POKY = '/usr1/openeuler/src/yocto-poky'
CONTAINER_IMAGE = '/home/openeuler/image'
CONTAINER_USER = "openeuler"
DEFAULT_MEM = "1G"
DEFAULT_SMP = "-smp 1"
POKY_REMOTE = "https://gitee.com/openeuler/yocto-poky"
POKY_BRANCH = "v4.0.10"
DEFAULT_DOCKER = "swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container:latest"

ARCH_MAP = {
    "aarch64": "qemuarm64",
    "arm": "qemuarm",
    "x86_64": "qemux86-64",
    "riscv64": "qemuriscv64"
}

MACHINE_MAP = {
    "qemuarm64": "virt-4.0",
    "qemuarm": "virt-2.12",
    "qemux86-64": "microvm",
    "qemuriscv64": "virt"
}

CPU_MAP = {
    "qemuarm64": "cortex-a57",
    "qemuarm": "cortex-a15",
    "qemux86-64": "qemu64",
    "qemuriscv64": "rv64"
}

class RunQemu(OebuildCommand):
    '''
    The command for run in qemu platform.
    '''
    def __init__(self):
        self.compile_conf_dir = os.path.join(os.getcwd(), 'compile.yaml')
        self.configure = Configure()
        self.client = None
        self.container_id = None
        self.machine = None
        self.kernel_path = None
        self.kernel = None
        self.rootfs_path = None
        self.rootfs = None
        self.mem = None
        self.smp = None
        self.poky_dir = None
        self.work_dir = os.getcwd()
        self.qemuboot_path = None

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

the destroy container, please wait ...

""")        
            try:
                container = self.client.get_container(self.container_id)
                self.client.stop_container(container=container)
                self.client.delete_container(container=container)
            except DockerException:
                print(f"destory container {self.container_id} faild, please run `docker rm {self.container_id} menully`")

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [-f conf] [-a arch] [-c create] [-k kernel] [-r rootfs] [-s smp] [-m mem]
''')
        parser.add_argument('-f','--conf', dest='conf',
            help='''
            this param is for qemuboot.conf, you can point qemuboot.conf, the qemuboot.conf is runqemu nessary file
            '''
        )
        parser.add_argument('-a','--arch', dest='arch',
            help='''
            this param is for arch. All possible choices: arm, aarch64, riscv64, x86_64, if you dont use the param, we will give
            you valid choices interactive
            '''
        )
        parser.add_argument('-c','--create', dest='create',
            help='''
            this param is for new qemuboot.conf, if you want create a new qemuboot.conf, use it.
            '''
        )
        parser.add_argument('-k','--kernel', dest='kernel',
            help='''
            this param is for kernel, you can use it point kernel, but if you use it in command, the current directory
can not exist any qemuboot.conf, else the param can not be effective, but you can modify qemuboot.conf's kernel_path
and kernel key if you want point the kernel.
            '''
        )
        parser.add_argument('-r','--rootfs', dest='rootfs',
            help='''
            this param is for rootfs, you can use it point rootfs, but if you use it in  command, the current directory
can not exist any qemuboot.conf, else the param can not be effective, but you can modify qemuboot.conf's rootfs_path
and rootfs key if you want point the rootfs.
            '''
        )
        parser.add_argument('-s','--smp', dest='smp',
            help='''
            this param is for smp, mapping qemu param -smp
            '''
        )
        parser.add_argument('-m','--mem', dest='mem',
            help='''
            this param is for mem, mapping qemu param mem
            '''
        )

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            return
        args = args.parse_args(unknown)
        try:
            self.client = DockerProxy()
        except DockerException:
            logger.error("please install docker first!!!")
            return
        logger.info('Run QEMU......')
        self._check_and_set(args)
        self.poky_dir = self._get_and_set_poky_dir()
        docker_image = self.get_docker_image()
        volumns = []
        if self.kernel is None:
            self.kernel_path = self._get_from_qemu_boot("kernel_path")
            self.kernel = os.path.basename(self.kernel_path)
        volumns.append(os.path.abspath(self.kernel_path)+":"+os.path.join(CONTAINER_IMAGE, self.kernel))
        if self.rootfs is None:
            self.rootfs_path = self._get_from_qemu_boot("rootfs_path")
            self.rootfs = os.path.basename(self.rootfs_path)
        volumns.append(os.path.abspath(self.rootfs_path)+":"+os.path.join(CONTAINER_IMAGE, self.rootfs))
        if not os.path.exists(os.path.join(self.work_dir, "build")):
            os.mkdir(os.path.join(self.work_dir, "build"))
        volumns.append(os.path.join(self.work_dir, "build")+":"+os.path.join(CONTAINER_IMAGE, "build"))
        volumns.append(os.path.abspath(self.qemuboot_path)+":"+os.path.join(
            CONTAINER_IMAGE, os.path.basename(self.qemuboot_path)))
        self.deal_env_container(docker_image=docker_image, other_volumns=volumns)

        self.exec_qemu()

    def exec_qemu(self):
        '''
        xxx
        '''
        container:Container = self.client.get_container(self.container_id) # type: ignore

        self.init_bash(container=container)

        content = self._get_bashrc_content(container=container)
        content = oebuild_util.add_bashrc(content=content, line=f"""
        runqemu {os.path.basename(self.qemuboot_path)} nographic
                                          """)
        self.update_bashrc(container=container, content=content)
        if self._get_from_qemu_boot("machine") == "qemux86-64":
            print("""
                  
                  x86-64 machine has not start log, please wait ...
                  
""")
            time.sleep(3)
        os.system(
            f"docker exec -it -u {CONTAINER_USER} -w {CONTAINER_IMAGE} {container.short_id}  bash")

        self.restore_bashrc(container=container)

    def restore_bashrc(self, container: Container):
        '''
        Restoring .bashrc will strip out the command line
        content added during bitbake initialization
        '''
        old_content = self._get_bashrc_content(container=container)
        self.update_bashrc(container=container,
                           content=oebuild_util.restore_bashrc_content(old_content=old_content))

    def _get_and_set_poky_dir(self):
        if not self.configure.is_oebuild_dir():
            # it's not oebuild workspace, so need to download yocto-poky temporary
            # first mkdir src
            if not os.path.exists("src/yocto-poky"):
                os.mkdir("src")
                print("prepare rely code, please wait ...")
                git.Repo.clone_from(POKY_REMOTE, "src/yocto-poky",branch = POKY_BRANCH, depth=1)
            return  os.path.abspath("src/yocto-poky")
        return self.configure.source_poky_dir()

    def deal_env_container(self,docker_image, other_volumns):
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
        volumns.append(self.poky_dir + ':' + CONTAINER_POKY)
        volumns.extend(other_volumns)

        container:Container = self.client.container_run_simple(
            image=docker_image,
            volumes=volumns) # type: ignore

        self.container_id = container.short_id
        container:Container = self.client.get_container(self.container_id) # type: ignore
        if not self.client.is_container_running(container):
            self.client.start_container(container)

    def get_docker_image(self):
        '''
        this is function is to get openeuler docker image automatic
        '''
        return DEFAULT_DOCKER

    def init_bash(self, container: Container):
        '''
        Bitbake will initialize the compilation environment by reading
        the user initialization script first, then making directional
        substitutions, and finally writing the initialization script
        '''
        # read container default user .bashrc content
        content = self._get_bashrc_content(container=container)

        init_sdk_command = '. /opt/buildtools/nativesdk/environment-setup-x86_64-pokysdk-linux'
        init_oe_comand = f'. {CONTAINER_POKY}/oe-init-build-env'
        cd_image_comand = f'cd {CONTAINER_IMAGE}'
        init_command = [init_sdk_command, init_oe_comand, cd_image_comand]
        new_content = oebuild_util.init_bashrc_content(content, init_command)

        self.update_bashrc(container=container, content=new_content)

    def _get_bashrc_content(self, container: Container):
        content = self.client.container_exec_command(
            container=container,
            command=f"cat /home/{CONTAINER_USER}/.bashrc",
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
            to_path=f'/home/{CONTAINER_USER}')
        container.exec_run(
            cmd=f"mv /home/{CONTAINER_USER}/{tmp_file} /home/{CONTAINER_USER}/.bashrc",
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

    def _get_auto_kernel(self, search_dir):
        file_list = os.listdir(search_dir)
        for file_path in file_list:
            if not os.path.isfile(file_path):
                continue
            file_name:str = os.path.basename(file_path)
            if re.search(r'\.bin$', file_name) or re.search('bzImage', file_name) or \
             re.search('zImage', file_name) or re.search('uImage', file_name) or \
             re.search('fitImage', file_name) or re.search('Image', file_name):
                if file_name.endswith(".sha256sum"):
                    continue
                return file_path, file_name
        print(f"can not find any kernel file in {search_dir}")
        while True:
            kernel_path = input("please enter valid kernel path, or enter q for exit:")
            if kernel_path == "q":
                sys.exit(0)
            if not os.path.exists(kernel_path):
                print(f"the {kernel_path} is not exists")
                continue
            return kernel_path, os.path.basename(kernel_path)

    def _get_auto_rootfs(self, search_dir):
        file_list = os.listdir(search_dir)
        for file_path in file_list:
            if not os.path.isfile(file_path):
                continue
            file_name:str = os.path.basename(file_path)
            if file_name.endswith("cpio.gz") or file_name.endswith("cpio"):
                return file_path, file_name
        print(f"can not find any rootfs file in {search_dir}")
        while True:
            rootfs_path = input("please enter valid rootfs path, or enter q for exit:")
            if rootfs_path == "q":
                sys.exit(0)
            if not os.path.exists(rootfs_path):
                print(f"the {rootfs_path} is not exists")
                continue
            return rootfs_path, os.path.basename(rootfs_path)

    def _get_auto_machine(self) -> str:
        while True:
            print("we support the archs:")
            for index,arch in enumerate(ARCH_MAP):
                print(f"{index+1},{arch}")
            input_str = input("please enter arch, or enter q for exit:")
            if input_str  == "q":
                sys.exit(0)
            try:
                num_index = int(input_str)
            except ValueError:
                print("please enter right number\n")
                continue
            try:
                machine = ARCH_MAP[list(ARCH_MAP.keys())[num_index-1]]
                return machine
            except IndexError:
                print("please enter right number\n")
                continue

    def _find_qemu_boot(self,) -> (bool,str):
        '''
        if can not find any qemuboot.conf, we create a new qemuboot.conf
        if find a qemuboot.conf, we use it directly
        if find more than one qemuboot.conf, we give some choice to select
        '''
        qemu_boot_list = []
        file_list = os.listdir(self.work_dir)
        for file_path in file_list:
            if not os.path.isfile(file_path):
                continue
            if file_path.endswith(".qemuboot.conf"):
                qemu_boot_list.append(file_path)
        if len(qemu_boot_list) == 0:
            return True, "app.qemuboot.conf"
        if len(qemu_boot_list) == 1:
            return False, qemu_boot_list[0]
        print("check some qemu_boot conf")

        while True:
            for index,item in enumerate(qemu_boot_list):
                print(f"{index+1}, {item}")
            input_str = input("""
check some qemu_boot conf, please select one if you need,
or enter e for create a new, enter q for quit:""")
            if input_str == "q":
                sys.exit(0)
            if input_str == "e":
                return True,self._get_qemu_boot_input_name()
            try:
                num_index = int(input_str)
            except ValueError:
                print("please enter right number\n")
                continue
            try:
                qemu_path = qemu_boot_list[num_index-1]
                return True,qemu_path
            except IndexError:
                print("please enter right number\n")
                continue

    def _get_qemu_boot_input_name(self):
        while True:
            name = input("please enter qemuboot.conf prefix")
            if os.path.exists(f"{name}.qemuboot.conf"):
                print(f"the {name}.qemuboot.conf has exists!!!\n")
                continue
            return f"{name}.qemuboot.conf"

    def _check_and_set(self,args):
        # first, check the qemuboot file, if not exists, raise exception
        if args.conf is not None:
            if not os.path.exists(args.conf):
                raise ValueError(f"the {args.conf} not exists")
            else:
                self.work_dir = os.path.dirname(args.conf)
                self.qemuboot_path = args.conf
                return
        if args.create is None:
            is_new, self.qemuboot_path = self._find_qemu_boot()
            if not is_new:
                return
        else:
            while True:
                if not args.create.endswith(".qemuboot.conf"):
                    args.create = f"{args.create}.qemuboot.conf"
                if os.path.exists(os.path.join(self.work_dir, args.create)):
                    args.create = input(f"""
the name {args.create} has exists, please enter other one:
""")
                    continue
                self.qemuboot_path = args.create
                break

        # make sure machine param
        if args.arch is None:
            self.machine = self._get_auto_machine()
        else:
            if args.arch in ARCH_MAP:
                self.machine = ARCH_MAP[args.arch]
            else:
                self.machine = self._get_auto_machine()

        # make sure kernel param
        if args.kernel is None:
            self.kernel_path,self.kernel = self._get_auto_kernel(self.work_dir)
        else:
            if not os.path.exists(args.kernel):
                print(f"the file {args.kernel} not exists")
                sys.exit(0)
            self.kernel_path = args.kernel
            self.kernel = os.path.basename(args.kernel)

        # make sure rootfs param
        if args.rootfs is None:
            self.rootfs_path, self.rootfs = self._get_auto_rootfs(os.getcwd())
        else:
            if not os.path.exists(args.rootfs):
                print(f"the file {args.rootfs} not exists")
                sys.exit(0)
            self.rootfs_path = args.rootfs
            self.rootfs = os.path.basename(args.rootfs)

        # make sure smp param
        if args.smp is None:
            self.smp = DEFAULT_SMP
        else:
            self.smp = args.smp

        # make sure mem param
        if args.mem is None:
            self.mem = DEFAULT_MEM
        else:
            self.mem = args.mem

        self._create_new_qemu_boot()

    def _create_new_qemu_boot(self):
        config_bsp = {}
        config_bsp['staging_dir_native'] = '/opt/buildtools/nativesdk/sysroots/'
        config_bsp['staging_bindir_native'] = '/opt/buildtools/nativesdk/sysroots/x86_64-pokysdk-linux/usr/bin/'
        config_bsp['machine'] = self.machine
        config_bsp['kernel_path'] = self.kernel_path
        config_bsp['kernel'] = self.kernel
        config_bsp['rootfs_path'] = self.rootfs_path
        config_bsp['rootfs'] = self.rootfs
        config_bsp['qb_default_fstype'] = "cpio.gz"
        config_bsp['qb_net'] = "none"
        config_bsp['qb_machine'] = f"-M {MACHINE_MAP[self.machine]}"
        config_bsp['qb_cpu'] = f"-cpu {CPU_MAP[self.machine]}"
        config_bsp['qb_mem'] = self.mem
        config_bsp['qb_smp'] = self.smp
        config = configparser.ConfigParser()
        config['config_bsp'] = config_bsp
        with open(self.qemuboot_path, 'w', encoding="utf-8") as cf:
            config.write(cf, False)
        return

    def _get_from_qemu_boot(self, key:str):
        cf = configparser.ConfigParser()
        cf.read(self.qemuboot_path)
        for k,v in cf.items('config_bsp'):
            if k.upper() == key.upper():
                return v
        return ""
