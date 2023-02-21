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

import textwrap
import argparse
import pathlib
import os
import getpass
import shutil

import requests

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.ogit import OGit
from oebuild.my_log import MyLog as log

class Upgrade(OebuildCommand):
    '''
    the command for oebuild upgrade
    '''
    def __init__(self):
        super().__init__(
            'upgrade',
            'the command to upgrade oebuild',
            textwrap.dedent('''\
            you can run this command to upgrade oebuild
'''
        ))

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s
''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown = None):
        '''
        Implement the online upgrade function by comparing
        the local version and the remote version, and perform
        the online upgrade function if there is inconsistency.
        The upgrade method is to download the remote oebuild
        binary warehouse locally, then execute 'pip install *.whl',
        and then delete the local binary warehouse
        '''
        args.parse_args(unknown)

        upgrade_conf_dir = oebuild_util.get_upgrade_yaml_dir()
        upgrade_conf = oebuild_util.read_yaml(pathlib.Path(upgrade_conf_dir))
        ver_url = os.path.join(upgrade_conf['remote_url'],
                               'raw',
                               upgrade_conf['branch'],
                               upgrade_conf['ver_file'])
        response = requests.get(url=ver_url, timeout=5)
        if response.status_code == 200:
            log.info("the oebuild is latest version")
        else:
            log.err("download faild")
            return

        version = oebuild_util.get_oebuild_version()
        if version != response.content.decode():
            self.download_binary(upgrade_conf['remote_url'], upgrade_conf['branch'])

    def download_binary(self, remote_url, branch):
        '''
        download oebuild binary package and install it
        '''
        while True:
            random_str = oebuild_util.generate_random_str(6)
            random_repo_dir = os.path.join('/home',getpass.getuser(), random_str)
            if os.path.exists(random_repo_dir):
                continue
            break
        ogit = OGit(repo_dir=random_repo_dir, remote_url=remote_url, branch= branch)
        ogit.clone_or_pull_repo()

        for f_name in os.listdir(random_repo_dir):
            if f_name.endswith("whl"):
                oebuild_file = f_name
        os.system(f"pip install {os.path.join(random_repo_dir,oebuild_file)}")
        if os.path.exists(random_repo_dir):
            shutil.rmtree(random_repo_dir)
