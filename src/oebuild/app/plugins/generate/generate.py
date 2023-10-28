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
import pathlib
from shutil import copyfile

from prettytable import PrettyTable

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.parse_compile import ParseCompile,CheckCompileError
from oebuild.configure import Configure
from oebuild.parse_template import BaseParseTemplate, ParseTemplate, BUILD_IN_DOCKER, BUILD_IN_HOST
from oebuild.m_log import logger, INFO_COLOR
from oebuild.check_docker_tag import CheckDockerTag

class Generate(OebuildCommand):
    '''
    compile.yaml is generated according to different command parameters by generate
    '''
    def __init__(self):
        self.configure = Configure()
        self.nativesdk_dir = None
        self.toolchain_dir = None
        self.sstate_cache = None
        self.tmp_dir = None
        super().__init__(
            'generate',
            'help to mkdir build directory and generate compile.yaml',
            textwrap.dedent('''\
            The generate command is the core command in the entire build process, which 
            is mainly used to customize the build configuration parameters and generate 
            a compile.yaml by customizing each parameter. In addition, for a large number 
            of configuration parameter input is not very convenient, generate provides a 
            way to specify compile.yaml, users can directly specify the file after 
            customizing the build configuration file
'''
        ))

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [-p platform] [-f features] [-t toolchain_dir] [-d build_directory] [-l list] [-b_in build_in]
''')

        parser.add_argument('-l', '--list', dest='list',action = "store_true",
            help='''
            will list support archs and features
            '''
        )

        parser.add_argument('-p', '--platform', dest='platform', default="qemu-aarch64",
            help='''
            this param is for arch, you can find it in yocto-meta-openeuler/.oebuild/platform
            '''
        )

        parser.add_argument('-s','--state_cache', dest='sstate_cache',
            help='''
            this param is for SSTATE_MIRRORS
            '''
        )

        parser.add_argument('-s_dir', '--sstate_dir', dest='sstate_dir',
            help='''
            this param is for SSTATE_DIR
            '''
        )

        parser.add_argument('-m', '--tmp_dir', dest='tmp_dir',
            help='''
            this param is for tmp directory, the build result will be stored in
            '''
        )

        parser.add_argument('-f', '--features', dest='features', action='append',
            help='''
            this param is feature, it's a reuse command
            '''
        )

        parser.add_argument('-c', '--compile_dir', dest='compile_dir',
            help='''
            this param is for compile.yaml directory
            '''
        )

        parser.add_argument('-d', '--directory', dest='directory',
            help='''
            this param is build directory, the default is same to platform
            '''
        )

        parser.add_argument('-t', '--toolchain_dir', dest='toolchain_dir', default = '',
            help='''
            this param is for external toolchain dir, if you want use your own toolchain
            '''
        )

        parser.add_argument('-n', '--nativesdk_dir', dest='nativesdk_dir', default = '',
            help='''
            this param is for external nativesdk dir, the param will be useful when you want to build in host
            '''
        )
        
        parser.add_argument('-tag', '--docker_tag', dest='docker_tag', default = '',
            help='''
            when build in docker, the param can be point docker image
            '''
        )

        parser.add_argument('-dt', '--datetime', dest = "datetime",
            help='''
            this param is add DATETIME to local.conf, the value format is 20231212010101
            ''')

        parser.add_argument('-df',
                            '--disable_fetch',
                            dest = "is_disable_fetch",
                            action = "store_true",
            help='''
            this param is set openeuler_fetch in local.conf, the default value is enable, if set -df, the OPENEULER_FETCH will set to 'disable'
            ''')

        parser.add_argument('-b_in', '--build_in', dest='build_in', choices=[BUILD_IN_DOCKER, BUILD_IN_HOST],
                            default = BUILD_IN_DOCKER, help='''
            This parameter marks the mode at build time, and is built in the container by docker
            '''
        )

        return parser

    def do_run(self, args: argparse.Namespace, unknown = None):
        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            return

        args = args.parse_args(unknown)

        if not self.configure.is_oebuild_dir():
            logger.error('your current directory had not finishd init')
            sys.exit(-1)

        yocto_dir = self.configure.source_yocto_dir()
        if not self.check_support_oebuild(yocto_dir):
            logger.error('Currently, yocto-meta-openeuler does not support oebuild, \
                    please modify .oebuild/config and re-execute `oebuild update`')
            return

        if args.compile_dir is not None:
            try:
                platform = self._check_compile(args.compile_dir)
                args.platform = platform
                build_dir = self._init_build_dir(args=args)
                if build_dir is None:
                    logger.error("build directory can not mkdir")
                    return
                # copy compile.yaml to build directory
                copyfile(args.compile_dir, os.path.join(build_dir, "compile.yaml"))
                self._print_generate(build_dir=build_dir)
            except CheckCompileError as c_e:
                logger.error(str(c_e))
            except ValueError as v_e:
                logger.error(str(v_e))
            except IOError as e:
                logger.error(str(e))
            return

        build_in = BUILD_IN_DOCKER
        if args.build_in == BUILD_IN_HOST:
            try:
                self._check_param_in_host(args=args)
            except ValueError as v_e:
                logger.error(str(v_e))
                return
            self.nativesdk_dir = args.nativesdk_dir
            build_in = BUILD_IN_HOST

        if args.toolchain_dir != '':
            self.toolchain_dir = args.toolchain_dir

        if args.sstate_cache is not None:
            self.sstate_cache = args.sstate_cache

        if args.tmp_dir is not None:
            self.tmp_dir = args.tmp_dir

        if args.list:
            self.list_info()
            return

        build_dir = self._init_build_dir(args=args)
        if build_dir is None:
            return

        parser_template = ParseTemplate(yocto_dir=yocto_dir)

        yocto_oebuild_dir = os.path.join(yocto_dir, '.oebuild')

        try:
            self._add_platform_template(args=args,
            yocto_oebuild_dir=yocto_oebuild_dir,
            parser_template=parser_template)
        except BaseParseTemplate as b_t:
            logger.error(str(b_t))
            return
        except ValueError as v_e:
            logger.error(str(v_e))
            return

        try:
            self._add_features_template(args=args,
            yocto_oebuild_dir=yocto_oebuild_dir,
            parser_template=parser_template)
        except BaseParseTemplate as b_t:
            logger.error(str(b_t))
            self._list_feature()
            return
        except ValueError as v_e:
            logger.error(str(v_e))
            return

        if os.path.exists(os.path.join(build_dir,'compile.yaml')):
            os.remove(os.path.join(build_dir,'compile.yaml'))

        check_docker_tag = CheckDockerTag(args.docker_tag, self.configure)
        oebuild_config = self.configure.parse_oebuild_config()
        if check_docker_tag.get_tag() is not None:
            docker_tag = str(check_docker_tag.get_tag())
        else:
            # select docker image
            while True:
                print('''
If the system does not recognize which container image to use, select the
following container, enter it numerically, and enter q to exit:''')
                image_list = check_docker_tag.get_tags()

                for key,value in enumerate(image_list):
                    print(f"{key}, {oebuild_config.docker.repo_url}:{value}")
                k = input("please entry number:")
                if k == "q":
                    return
                try:
                    index = int(k)
                    docker_tag = image_list[index]
                    break
                except IndexError:
                    print("please entry true number")
        docker_tag = docker_tag.strip()
        docker_tag = docker_tag.strip('\n')
        docker_image = f"{oebuild_config.docker.repo_url}:{docker_tag}"

        out_dir = pathlib.Path(os.path.join(build_dir,'compile.yaml'))
        oebuild_util.write_yaml(out_dir, parser_template.generate_template(
            nativesdk_dir= self.nativesdk_dir,
            toolchain_dir= self.toolchain_dir,
            build_in=build_in,
            sstate_cache= self.sstate_cache,
            tmp_dir = self.tmp_dir,
            datetime = args.datetime,
            is_disable_fetch = args.is_disable_fetch,
            docker_image=docker_image
            ))

        self._print_generate(build_dir=build_dir)

    def _print_generate(self, build_dir):
        format_dir = f'''
generate compile.yaml successful

please run follow command:
=============================================

cd {build_dir}
oebuild bitbake

=============================================
'''
        logger.info(format_dir)

    def _check_compile(self, compile_dir: str):
        if not os.path.exists(compile_dir):
            raise ValueError(f"the compile_dir:{compile_dir} is not exists, please check again")

        parse_compile = ParseCompile(compile_dir)
        return parse_compile.platform

    def _check_param_in_host(self, args):
        if args.toolchain_dir == '':
            raise ValueError("build in host must points toolchain directory in '-t' param")

        if args.nativesdk_dir == '':
            raise ValueError("build in host must points nativesdk directory in '-n' param")

    def _add_platform_template(self, args, yocto_oebuild_dir, parser_template: ParseTemplate):
        if args.platform + '.yaml' in os.listdir(os.path.join(yocto_oebuild_dir, 'platform')):
            try:
                parser_template.add_template(
                    os.path.join(yocto_oebuild_dir,
                    'platform',
                    args.platform+'.yaml'))
            except BaseParseTemplate as e_p:
                raise e_p
        else:
            raise ValueError("wrong platform, please run `oebuild generate -l` to view support platform")

    def _add_features_template(self, args, yocto_oebuild_dir, parser_template: ParseTemplate):
        if args.features:
            for feature in args.features:
                if feature + '.yaml' in os.listdir(os.path.join(yocto_oebuild_dir, 'features')):
                    try:
                        parser_template.add_template(os.path.join(yocto_oebuild_dir,
                                                                    'features',
                                                                    feature+'.yaml'))
                    except BaseParseTemplate as b_t:
                        raise b_t
                else:
                    raise ValueError("wrong platform, please run `oebuild generate -l` to view support feature")

    def _init_build_dir(self, args):
        if not os.path.exists(self.configure.build_dir()):
            os.makedirs(self.configure.build_dir())

        if args.directory is None or args.directory == '':
            build_dir = os.path.join(self.configure.build_dir(), args.platform)
        else:
            build_dir = os.path.join(self.configure.build_dir(), args.directory)

        if not os.path.abspath(build_dir).startswith(self.configure.build_dir()):
            logger.error("build path must in oebuild workspace")
            return None

        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        return build_dir

    def list_info(self,):
        '''
        print platform list or feature list
        '''
        self._list_platform()
        self._list_feature()

    def _list_platform(self):
        logger.info("=============================================")
        yocto_dir = self.configure.source_yocto_dir()
        yocto_oebuild_dir = os.path.join(yocto_dir, ".oebuild")
        list_platform = os.listdir(os.path.join(yocto_oebuild_dir, 'platform'))
        print("the platform list is:")
        table = PrettyTable(['platform name'])
        table.align = "l"
        for platform in list_platform:
            if platform.endswith('.yml'):
                table.add_row([platform.replace('.yml', '')])
            if platform.endswith('.yaml'):
                table.add_row([platform.replace('.yaml', '')])
        print(table, INFO_COLOR)

    def _list_feature(self,):
        yocto_dir = self.configure.source_yocto_dir()
        yocto_oebuild_dir = os.path.join(yocto_dir, ".oebuild")
        list_feature = os.listdir(os.path.join(yocto_oebuild_dir, 'features'))
        print("the feature list is:")
        table = PrettyTable(['feature name','support arch'])
        table.align = "l"
        for feature in list_feature:
            if feature.endswith('.yml'):
                feature_name = feature.replace('.yml','')
            if feature.endswith('.yaml'):
                feature_name = feature.replace('.yaml','')
            feat = oebuild_util.read_yaml(pathlib.Path(os.path.join(yocto_oebuild_dir,
                                                                    'features',
                                                                    feature)))
            if "support" in feat:
                table.add_row([feature_name, feat.get('support')])
            else:
                table.add_row([feature_name, "all"])
        print(table, INFO_COLOR)

    def check_support_oebuild(self, yocto_dir):
        '''
        Determine if OeBuild is supported by checking if .oebuild
        exists in the yocto-meta-openeuler directory
        '''
        return os.path.exists(os.path.join(yocto_dir, '.oebuild'))
