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
import shutil
import os
import textwrap
import sys

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.configure import Configure, YOCTO_META_OPENEULER, ConfigBasicRepo, CONFIG, Config
from oebuild.m_log import logger

class Init(OebuildCommand):
    '''
    Directory initialization directive, mainly used to initialize
    the OEbuild project directory, running this directive needs
    to be followed by the directory name to be initialized
    '''

    def __init__(self):
        self.configure = Configure()
        self.oebuild_dir = None
        self.src_dir = None

        super().__init__(
            'init',
            'Initialize an OEBUILD working directory',
            textwrap.dedent('''\
            Initialize an OEBUILD working directory, and execute 
            all other OEbuild instructions in the initialized directory
'''
        ))

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''
            
  %(prog)s [directory] [-u yocto_remote_url] [-b branch]
''')

        parser.add_argument('-u', dest = 'yocto_remote_url',
            help='''Specifies the remote of yocto-meta-openeuler''')

        parser.add_argument('-b', dest = 'branch',
            help='''Specifies the branch of yocto-meta-openeuler''')

        parser.add_argument(
            'directory', nargs='?', default=None,
            help='''The name of the directory that will be initialized''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown = None):
        '''
        detach target dicrectory if finished init, if inited, just put out err msg and exit
        '''
        iargs = args
        args = args.parse_args(unknown)

        if self.configure.is_oebuild_dir():
            log = f'The "{os.path.dirname(self.configure.oebuild_dir())}" \
                    has already been initialized, please change other directory'
            logger.error(log)
            sys.exit(-1)

        if args.directory is None:
            logger.error("'oebuild init' need param directory")
            logger.info("\noebuild init help:")
            self.print_help(iargs)
            return

        if not self.init_workspace(args.directory):
            logger.error("mkdir %s faild", args.directory)
            return

        os.chdir(args.directory)
        oebuild_config:Config = self.configure.parse_oebuild_config()

        yocto_config:ConfigBasicRepo = oebuild_config.basic_repo[YOCTO_META_OPENEULER]
        if args.yocto_remote_url is not None:
            yocto_config.remote_url = args.yocto_remote_url
        if args.branch is not None:
            yocto_config.branch = args.branch
        oebuild_config.basic_repo[YOCTO_META_OPENEULER] = yocto_config

        self.configure.update_oebuild_config(oebuild_config)

        logger.info("init %s successful",args.directory)
        format_msg = f'''
please execute the follow commands next

    cd {os.path.abspath(os.getcwd())}
    oebuild update
        '''
        print(format_msg)

    def init_workspace(self, directory):
        '''
        init workspace will copy config file and make new src directory
        '''
        try:
            os.mkdir(directory)
        except FileExistsError:
            return False

        self.oebuild_dir = self.create_oebuild_directory(directory)
        self.copy_config_file(self.oebuild_dir)
        self.src_dir = self.create_src_directory(directory)
        return True

    @staticmethod
    def create_oebuild_directory(updir : str):
        '''
        create oebuild config directory
        '''
        try:
            oebuild_dir = os.path.join(updir, ".oebuild")
            os.mkdir(oebuild_dir)
            return oebuild_dir
        except FileExistsError:
            logger.error("mkdir .oebuild faild")
            return ""

    @staticmethod
    def create_src_directory(updir : str):
        '''
        this is desctiption
        '''
        try:
            src_dir = os.path.join(updir, "src")
            os.makedirs(src_dir)
            return src_dir
        except FileExistsError:
            logger.error("mkdir src faild")
            return None

    @staticmethod
    def copy_config_file(updir : str):
        '''
        copy oebuild config to some directory
        '''
        try:
            config = oebuild_util.get_config_yaml_dir()
            shutil.copyfile(config, os.path.join(updir, CONFIG))
        except FileNotFoundError:
            logger.error("mkdir config faild")
