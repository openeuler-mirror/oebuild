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

import oebuild.bb.utils as bb_utils

class BBLayers:
    '''
    The BBlayer class implements the layer added in the
    container environment in the physical environment,
    and the add operation references bitbake-related code
    '''
    def __init__(self, bblayers_dir: str, base_dir: str):
        self._base_dir = base_dir
        self._bblayers_dir = bblayers_dir

    @property
    def base_dir(self):
        '''
        Returns base_dir value
        '''
        return self._base_dir

    @property
    def bblayers_dir(self):
        '''
        Returns bblayers_dir value
        '''
        return self._bblayers_dir

    def add_layer(self, pre_dir: str, layers: str or list):
        '''
        Add a layer layer to bblayers.conf, but our layer
        layer verification is done on the host,
        and the added path is written as a path in the container
        args:
            pre_dir (str): when added layer with path, for example
            pre_dir/layer
            layers (str or list): needed to add to bblayers.conf
        '''
        try:
            self.check_layer_exist(layers=layers)
        except Exception as e_p:
            raise e_p

        bblayers = []
        if isinstance(layers, str):
            bblayers = [os.path.join(pre_dir, layers)]
        if isinstance(layers, list):
            for layer in layers:
                bblayers.append(os.path.join(pre_dir, layer))

        bb_utils.edit_bblayers_conf(self.bblayers_dir, add=bblayers, remove=None)

    def check_layer_exist(self, layers:str or list):
        '''
        To check if it is legitimate to add a layer,
        the main thing is to verify the existence of layer.conf
        args:
            layers (str or list): needed to add to bblayers.conf
        '''
        bblayers = []
        if isinstance(layers, str):
            bblayers.append(layers)
        else:
            bblayers.extend(bblayers)

        for layer in bblayers:
            layer_dir = os.path.join(self.base_dir, layer)
            if not os.path.exists(layer_dir):
                raise ValueError("layer does not exists")

            layer_conf_dir = os.path.join(layer_dir, 'conf', 'layer.conf')
            if not os.path.exists(layer_conf_dir):
                raise ValueError("invalid layer")
