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
from oebuild.configure import Configure, YOCTO_META_OPENEULER, ConfigBasicRepo, CONFIG, COMPILE_YAML, Config
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
            Initialize the OEbuild working directory, and after executing this command,
            a new directory will be created as the OEBUILD working directory based on the
            current path. After initialization, the working directory will create an .oebuild
            directory, which stores configuration-related files, currently the directory has
            config and compile.yaml.sample two files, config files record environment-related
            parameters, mainly the main build warehouse yocto-meta-openeuler related information
            and build container related information, compile.yaml.sample is an example file of
            the build configuration file, users can copy the file to other places and then make
            certain changes according to their own needs。 This file is to meet the user's global
            consideration of the build configuration of OEbuild, and can be easily called by third
            parties
'''
        ))

    def do_add_parser(self, parser_adder):
        self._parser(
            parser_adder,
            usage='''
            
  %(prog)s [directory] [-u yocto_remote_url] [-b branch]
''')

        parser_adder.add_argument('-u','--yocto_remote_url', dest = 'yocto_remote_url',
            help='''Specifies the remote of yocto-meta-openeuler''')

        parser_adder.add_argument('-b', '--branch', dest = 'branch',
            help='''Specifies the branch of yocto-meta-openeuler''')

        parser_adder.add_argument(
            'directory', nargs='?', default=None,
            help='''The name of the directory that will be initialized''')

        return parser_adder

    def do_run(self, args: argparse.ArgumentParser, unknown = None):
        '''
        detach target dicrectory if finished init, if inited, just put out err msg and exit
        '''

        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            return

        args = args.parse_args(unknown)

        if self.configure.is_oebuild_dir():
            log = f'The "{os.path.dirname(self.configure.oebuild_dir())}" \
                    has already been initialized, please change other directory'
            logger.error(log)
            sys.exit(-1)

        if args.directory is None:
            logger.error("'oebuild init' need param directory")
            logger.info("\noebuild init help:")
            self.print_help_msg()
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
There is a build configuration example file under {args.directory}/.oebuild/compile.yaml.sample, 
if you want to block complex generate instructions, you can directly copy a configuration file, 
and then modify it according to your own needs, and then execute `oebuild generate -c <compile_dir>`.
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
        self.copy_compile_file(self.oebuild_dir)
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

    @staticmethod
    def copy_compile_file(updir : str):
        '''
        copy oebuild compile.yaml.sample to some directory
        '''
        try:
            compil = oebuild_util.get_compile_yaml_dir()
            shutil.copyfile(compil, os.path.join(updir, COMPILE_YAML))
        except FileNotFoundError:
            logger.error("mkdir compile.yaml.sample faild")
