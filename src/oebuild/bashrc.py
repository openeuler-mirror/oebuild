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
import shutil
import subprocess

from docker.models.containers import Container

import oebuild.util as oebuild_util
import oebuild.const as oebuild_const
from oebuild.docker_proxy import DockerProxy
from oebuild.m_log import logger


class Bashrc:
    '''
    is for modify ${HOME}/.bashrc
    '''
    def __init__(self,) -> None:
        self.container = None
        self.client = None

    def set_container(self, container: Container):
        '''
        After setting the container parameters, all operations on bashrc
        will be based on the container.
        '''
        self.container = container
        self.client = DockerProxy()

    def update_bashrc(self, content: str):
        '''
        update user initialization script by replace file, first create
        a file and writed content and move it to .bashrc
        '''
        tmp_file = self._set_tmpfile_content(content)
        # deal host bashrc
        if self.container is None:
            shutil.move(tmp_file, os.path.join(os.environ['HOME'], '.bashrc'))
            return
        # deal container bashrc
        self.client.copy_to_container(
            container=self.container,
            source_path=tmp_file,
            to_path=f'/home/{oebuild_const.CONTAINER_USER}')
        self.container.exec_run(
            cmd=f'''
mv /home/{oebuild_const.CONTAINER_USER}/{tmp_file} /home/{oebuild_const.CONTAINER_USER}/.bashrc
            ''',
            user="root"
        )
        os.remove(tmp_file)

    def restore_bashrc(self):
        '''
        Restoring .bashrc will strip out the command line
        content added during bitbake initialization
        '''
        old_content = self.get_bashrc_content()
        self.update_bashrc(content=self.restore_bashrc_content(old_content=old_content))

    def get_bashrc_content(self,):
        '''
        get bashrc shell content
        '''
        # return host bashrc
        if self.container is None:
            return subprocess.getoutput('cat $HOME/.bashrc')
        # deal container bashrc
        res = self.client.container_exec_command(
            container=self.container,
            command=f"cat /home/{oebuild_const.CONTAINER_USER}/.bashrc",
            user="root",
            params={
                "work_space": None,
                "stream": False
            })

        if res.exit_code != 0:
            logger.error(res.output)
            sys.exit(1)

        return res.output.decode()

    @staticmethod
    def restore_bashrc_content(old_content):
        '''
        restore bashrc content, it will delete line with oebuild_const.BASH_END_FLAG
        '''
        new_content = ''
        for line in old_content.split('\n'):
            line: str = line
            if line.endswith(oebuild_const.BASH_END_FLAG) or line.replace(" ", '') == '':
                continue
            new_content = new_content + line + '\n'
        return new_content

    @staticmethod
    def add_bashrc(content: str, line: str):
        '''
        add new line to bashrc with oebuild_const.BASH_END_FLAG
        '''
        if not content.endswith('\n'):
            content = content + '\n'
        content = content + line + oebuild_const.BASH_END_FLAG + '\n'

        return content

    @staticmethod
    def init_bashrc_content(old_content, init_command: list):
        '''
        add init command line to bashrc shell
        '''
        new_content = Bashrc().restore_bashrc_content(old_content=old_content)

        for command in init_command:
            new_content = new_content + command + oebuild_const.BASH_END_FLAG + '\n'

        return new_content

    def _set_tmpfile_content(self, content: str):
        while True:
            tmp_file = oebuild_util.generate_random_str(6)
            if os.path.exists(tmp_file):
                continue
            with open(tmp_file, 'w', encoding="utf-8") as w_f:
                w_f.write(content)
            break
        return tmp_file
