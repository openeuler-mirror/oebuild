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
import subprocess
import pty
import shutil

from oebuild.local_conf import NativesdkNotExist, NativesdkNotValid
from oebuild.configure import Configure
from oebuild.parse_compile import ParseCompile
from oebuild.m_log import logger
import oebuild.app.plugins.bitbake.const as bitbake_const
from oebuild.app.plugins.bitbake.base_build import BaseBuild

class InHost(BaseBuild):
    '''
    bitbake command execute in host
    '''

    def __init__(self, configure: Configure):
        self.configure = configure
        self.container_id = None

    def exec(self, parse_compile: ParseCompile, command):
        '''
        execute bitbake commands
        '''
        self._init_build_sh(build_dir=os.getcwd())
        self._mk_build_sh(nativesdk_dir=parse_compile.nativesdk_dir, build_dir=os.getcwd())
        self.init_bitbake()

        # add bblayers, this action must before replace local_conf
        bblayers_dir = os.path.join(os.getcwd(), "conf", "bblayers.conf")
        self.add_bblayers(
            bblayers_dir=bblayers_dir,
            pre_dir=self.configure.source_dir(),
            base_dir=self.configure.source_dir(),
            layers=parse_compile.layers)

        local_dir = os.path.join(os.getcwd(), 'conf', 'local.conf')
        try:
            self.replace_local_conf(
                parse_compile=parse_compile,
                local_dir=local_dir,
                src_dir=self.configure.source_dir())
        except NativesdkNotExist as n_e:
            logger.error(str(n_e))
            logger.error("please set valid nativesdk directory")
            return
        except NativesdkNotValid as n_e:
            logger.error(str(n_e))
            logger.error('''
The nativesdk path must be valid, it is recommended 
that you download the nativesdk script and then perform 
initialization operations''')
            return

        if command is not None and command != "":
            self._append_build_sh(str_list=[command], build_dir= os.getcwd())
            with subprocess.Popen('bash build.sh',
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        encoding="utf-8") as s_p:
                if s_p.returncode is not None and s_p.returncode != 0:
                    err_msg = ''
                    if s_p.stderr is not None:
                        for line in s_p.stderr:
                            err_msg.join(line)
                        raise ValueError(err_msg)

                if s_p.stdout is not None:
                    for line in s_p.stdout:
                        logger.info(line.strip('\n'))
        else:
            # run in Interactive mode
            banner_list = []
            for b_s in bitbake_const.BASH_BANNER.split('\n'):
                b_s = f"echo {b_s}{bitbake_const.BASH_END_FLAG}"
                banner_list.append(b_s)
            self._append_build_sh(str_list=banner_list, build_dir= os.getcwd())
            append_str = f"sed -i '/{bitbake_const.BASH_END_FLAG}/d' $HOME/.bashrc"
            self._append_build_sh(str_list = [append_str], build_dir= os.getcwd())

            build_sh_dir = os.path.join(os.getcwd(), 'build.sh')
            source_build_str = f"source {build_sh_dir}"
            content = self._get_bashrc_content()
            content = self._restore_bashrc_content(old_content=content)
            new_content = self._add_bashrc(content, line=source_build_str)
            self.update_bashrc(new_content)
            pty.spawn("bash")

    def _mk_build_sh(self, nativesdk_dir, build_dir):
        init_sdk_command = f'. {nativesdk_dir}/environment-setup-x86_64-pokysdk-linux'
        set_template = f'export TEMPLATECONF="{self.configure.source_dir()}/yocto-meta-openeuler/.oebuild"'
        init_oe_command = f'. {self.configure.source_dir()}/yocto-poky/oe-init-build-env {build_dir}'
        ps1_command = 'PS1="\\u\\h:\\W> "'

        self._append_build_sh(str_list= [init_sdk_command, set_template, init_oe_command, ps1_command],
                              build_dir=build_dir)

    def _init_build_sh(self, build_dir):
        build_sh_dir = os.path.join(build_dir, 'build.sh')
        if os.path.exists(build_sh_dir):
            os.remove(build_sh_dir)
        os.mknod(build_sh_dir)

    def _append_build_sh(self, str_list:list, build_dir):
        build_sh_dir = os.path.join(build_dir, 'build.sh')
        if not os.path.exists(build_sh_dir):
            raise ValueError("build.sh not exists")

        with open(build_sh_dir, 'a', encoding='utf-8') as w_f:
            w_f.write('\n')
            w_f.write('\n'.join(str_list))

    def init_bitbake(self,):
        '''
        Bitbake will initialize the compilation environment by reading
        the user initialization script first, then making directional
        substitutions, and finally writing the initialization script
        '''
        subprocess.getoutput("bash build.sh")

    def _get_bashrc_content(self,):
        return subprocess.getoutput('cat $HOME/.bashrc')

    def update_bashrc(self, content: str):
        '''
        update user initialization script by replace file, first create
        a file and writed content and mv it to host's .bashrc
        '''
        tmp_file = self._set_tmpfile_content(content)
        shutil.move(tmp_file, os.path.join(os.environ['HOME'], '.bashrc'))
