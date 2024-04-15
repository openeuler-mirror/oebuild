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

import oebuild.const as oebuild_const
from oebuild.local_conf import LocalConf
from oebuild.bblayers import BBLayers


class BaseBuild:
    '''
    The class provides the basic methods that the build class inherits
    '''

    def replace_local_conf(self, compile_param, local_path, src_dir=None):
        '''
        replace some param in local.conf, the LocalConf will be instantiated
        and exec update
        '''
        local_conf = LocalConf(local_path)
        local_conf.update(compile_param, src_dir)

    def add_bblayers(self, bblayers_dir: str, pre_dir: str, base_dir: str, layers):
        '''
        add_layers has two main functions, one is to initialize
        the compilation directory, and the other is to add the
        bblayer layer so that subsequent build directory file
        replacement operations can be successfully executed
        '''
        bblayers = BBLayers(bblayers_dir=bblayers_dir,
                            base_dir=base_dir)
        pre_dir = os.path.join(pre_dir, f'{oebuild_const.YOCTO_POKY}/..')
        bblayers.add_layer(pre_dir=pre_dir, layers=layers)
