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

import oebuild.util as oebuild_util
from oebuild.local_conf import LocalConf
from oebuild.bblayers import BBLayers
import oebuild.app.plugins.bitbake.const as bitbake_const

class BaseBuild:
    '''
    The class provides the basic methods that the build class inherits
    '''
    def _set_tmpfile_content(self, content: str):
        while True:
            tmp_file = oebuild_util.generate_random_str(6)
            if os.path.exists(tmp_file):
                continue
            with open(tmp_file, 'w', encoding="utf-8") as w_f:
                w_f.write(content)
            break
        return tmp_file

    def replace_local_conf(self, parse_compile, local_dir, src_dir = None):
        '''
        replace some param in local.conf, the LocalConf will be instantiated
        and exec update
        '''
        local_conf = LocalConf(local_conf_dir=local_dir)
        local_conf.update(parse_compile=parse_compile, src_dir=src_dir)

    def add_bblayers(self, bblayers_dir: str, pre_dir: str, base_dir: str, layers):
        '''
        add_layers has two main functions, one is to initialize
        the compilation directory, and the other is to add the
        bblayer layer so that subsequent build directory file
        replacement operations can be successfully executed
        '''
        bblayers = BBLayers(bblayers_dir=bblayers_dir,
                            base_dir=base_dir)
        pre_dir = os.path.join(pre_dir, 'yocto-poky/..')
        bblayers.add_layer(pre_dir=pre_dir, layers=layers)

    def _restore_bashrc_content(self, old_content):
        new_content = ''
        for line in old_content.split('\n'):
            line: str = line
            if line.endswith(oebuild_util.BASH_END_FLAG) or line.replace(" ", '') == '':
                continue
            new_content = new_content + line + '\n'
        return new_content

    def _add_bashrc(self, content: str, line: str):
        if not content.endswith('\n'):
            content = content + '\n'
        content = content + line + oebuild_util.BASH_END_FLAG + '\n'

        return content

    def _init_bashrc_content(self, old_content, init_command: list):
        new_content = self._restore_bashrc_content(old_content=old_content)

        for command in init_command:
            new_content = new_content + command + oebuild_util.BASH_END_FLAG + '\n'

        return new_content
