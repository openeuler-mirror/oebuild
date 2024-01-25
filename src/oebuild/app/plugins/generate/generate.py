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
import re
import subprocess
import textwrap
import os
import sys
import pathlib
import time
from shutil import rmtree

from kconfiglib import Kconfig
from menuconfig import menuconfig
from prettytable import PrettyTable

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.configure import Configure, YoctoEnv
from oebuild.parse_template import BaseParseTemplate, ParseTemplate
from oebuild.m_log import logger, INFO_COLOR
from oebuild.check_docker_tag import CheckDockerTag
import oebuild.const as oebuild_const


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
        self.oebuild_kconfig_path = os.path.expanduser('~') + '/.local/oebuild_kconfig/'
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

%(prog)s
''')

        parser.add_argument('-l', '--list', dest='list', action="store_true",
                            help='''
            will list support archs and features
            '''
                            )

        parser.add_argument('-p', '--platform', dest='platform', default="qemu-aarch64",
                            help='''
            this param is for arch, you can find it in yocto-meta-openeuler/.oebuild/platform
            '''
                            )

        parser.add_argument('-s', '--state_cache', dest='sstate_cache',
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

        parser.add_argument('-d', '--directory', dest='directory',
                            help='''
            this param is build directory, the default is same to platform
            '''
                            )

        parser.add_argument('-t', '--toolchain_dir', dest='toolchain_dir', default='',
                            help='''
            this param is for external toolchain dir, if you want use your own toolchain
            '''
                            )

        parser.add_argument('-n', '--nativesdk_dir', dest='nativesdk_dir', default='',
                            help='''
            this param is for external nativesdk dir, the param will be useful when you
            want to build in host
            '''
                            )

        parser.add_argument('-tag', '--docker_tag', dest='docker_tag', default='',
                            help='''
            when build in docker, the param can be point docker image
            '''
                            )

        parser.add_argument('-dt', '--datetime', dest="datetime",
                            help='''
            this param is add DATETIME to local.conf, the value format is 20231212010101
            ''')

        parser.add_argument('-df',
                            '--disable_fetch',
                            dest="is_disable_fetch",
                            action="store_true",
                            help='''
            this param is set openeuler_fetch in local.conf, the default value is enable, if
            set -df, the OPENEULER_FETCH will set to 'disable'
            ''')

        parser.add_argument('-b_in',
                            '--build_in',
                            dest='build_in',
                            choices=[oebuild_const.BUILD_IN_DOCKER, oebuild_const.BUILD_IN_HOST],
                            default=oebuild_const.BUILD_IN_DOCKER, help='''
            This parameter marks the mode at build time, and is built in the container by docker
            ''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            return
        if not self.configure.is_oebuild_dir():
            logger.error('Your current directory had not finished init')
            sys.exit(-1)

        yocto_dir = self.configure.source_yocto_dir()
        if not self.check_support_oebuild(yocto_dir):
            logger.error('Currently, yocto-meta-openeuler does not support oebuild, \
                    please modify .oebuild/config and re-execute `oebuild update`')
            return

        if len(unknown) == 0:
            config_path = self.create_kconfig(yocto_dir)
            if not os.path.exists(config_path):
                sys.exit(0)
            generate_command = self.generate_command(config_path)
            subprocess.check_output(f'rm {config_path}', shell=True)
            args = args.parse_args(generate_command)
        else:
            args = args.parse_args(unknown)

        build_in = oebuild_const.BUILD_IN_DOCKER
        if args.build_in == oebuild_const.BUILD_IN_HOST:
            try:
                self._check_param_in_host(args=args)
            except ValueError as v_e:
                logger.error(str(v_e))
                return
            self.nativesdk_dir = args.nativesdk_dir
            build_in = oebuild_const.BUILD_IN_HOST

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

        if os.path.exists(os.path.join(build_dir, 'compile.yaml')):
            os.remove(os.path.join(build_dir, 'compile.yaml'))

        docker_image = YoctoEnv().get_docker_image(yocto_dir=yocto_dir)
        if docker_image is None:
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

                    for key, value in enumerate(image_list):
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

        out_dir = pathlib.Path(os.path.join(build_dir, 'compile.yaml'))

        oebuild_util.write_yaml(out_dir, parser_template.generate_compile_conf(
            nativesdk_dir=self.nativesdk_dir,
            toolchain_dir=self.toolchain_dir,
            build_in=build_in,
            sstate_cache=self.sstate_cache,
            tmp_dir=self.tmp_dir,
            datetime=args.datetime,
            is_disable_fetch=args.is_disable_fetch,
            docker_image=docker_image,
            src_dir=self.configure.source_dir(),
            compile_dir=build_dir
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
                                 args.platform + '.yaml'))
            except BaseParseTemplate as e_p:
                raise e_p
        else:
            logger.error("""
wrong platform, please run `oebuild generate -l` to view support platform""")
            sys.exit(-1)

    def _add_features_template(self, args, yocto_oebuild_dir, parser_template: ParseTemplate):
        if args.features:
            for feature in args.features:
                if feature + '.yaml' in os.listdir(os.path.join(yocto_oebuild_dir, 'features')):
                    try:
                        parser_template.add_template(os.path.join(yocto_oebuild_dir,
                                                                  'features',
                                                                  feature + '.yaml'))
                    except BaseParseTemplate as b_t:
                        raise b_t
                else:
                    logger.error("""
wrong platform, please run `oebuild generate -l` to view support feature""")
                    sys.exit(-1)

    def _init_build_dir(self, args):
        if not os.path.exists(self.configure.build_dir()):
            os.makedirs(self.configure.build_dir())

        if args.directory is None or args.directory == '':
            build_dir = os.path.join(self.configure.build_dir(), args.platform)
        else:
            build_dir = os.path.join(self.configure.build_dir(), args.directory)

        if not os.path.abspath(build_dir).startswith(self.configure.build_dir()):
            logger.error("Build path must in oebuild workspace")
            return None

        # detects if a build directory already exists
        if os.path.exists(build_dir):
            logger.warning("the build directory %s already exists", build_dir)
            while True:
                in_res = input("""
    do you want to overwrite it? the overwrite action will replace the compile.yaml
    to new and delete conf directory, enter Y for yes, N for no:""")
                if in_res not in ["Y", "y", "yes", "N", "n", "no"]:
                    print("""
    wrong input""")
                    continue
                if in_res in ['N', 'n', 'no']:
                    return None
                break
            if os.path.exists(os.path.join(build_dir, "conf")):
                rmtree(os.path.join(build_dir, "conf"))
        else:
            os.makedirs(build_dir)
        return build_dir

    def list_info(self, ):
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

    def _list_feature(self, ):
        yocto_dir = self.configure.source_yocto_dir()
        yocto_oebuild_dir = os.path.join(yocto_dir, ".oebuild")
        list_feature = os.listdir(os.path.join(yocto_oebuild_dir, 'features'))
        print("the feature list is:")
        table = PrettyTable(['feature name', 'support arch'])
        table.align = "l"
        for feature in list_feature:
            if feature.endswith('.yml'):
                feature_name = feature.replace('.yml', '')
            if feature.endswith('.yaml'):
                feature_name = feature.replace('.yaml', '')
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

    def create_kconfig(self, yocto_dir):
        """
            create_kconfig
        Returns:

        """
        yocto_oebuild_dir = os.path.join(yocto_dir, '.oebuild')
        basic_data = basic_config()
        platform_data = self.choice_platform(yocto_oebuild_dir)
        feature_data = self.add_feature(yocto_oebuild_dir)
        if not os.path.exists(pathlib.Path(self.oebuild_kconfig_path).absolute()):
            os.makedirs(pathlib.Path(self.oebuild_kconfig_path).absolute())
        kconfig_path = pathlib.Path(self.oebuild_kconfig_path, str(int(time.time())))
        with open(kconfig_path, 'w', encoding='utf-8') as kconfig_file:
            kconfig_file.write(platform_data + feature_data + basic_data)

        kconf = Kconfig(filename=kconfig_path)
        with oebuild_util.suppress_print():
            menuconfig(kconf)
        subprocess.check_output(f'rm -rf {kconfig_path}', shell=True)
        config_path = pathlib.Path(os.getcwd(), '.config')
        return config_path

    def choice_platform(self, yocto_oebuild_dir):
        """
            add platform to kconfig
        Args:
            yocto_oebuild_dir:

        Returns:

        """
        platform_path = os.path.join(yocto_oebuild_dir, 'platform')
        if os.path.exists(platform_path):
            platform_list = os.listdir(platform_path)
        else:
            logger.error('platform dir is not exists')
            sys.exit(-1)
        platform_start = textwrap.dedent("""
        comment "                           THIS IS CHOOSE PLATFORM                               "
        choice
            prompt "choice platform"
            default PLATFORM_QEMU-AARCH64\n
        """)
        platform_end = "endchoice"
        for platform in platform_list:
            platform_name = os.path.splitext(platform)[0].strip("\n")
            platform_info = (f"""    config PLATFORM_{platform_name.upper()}\n"""
                             f"""        bool "{platform_name}"\n\n""")
            platform_start += platform_info
        platform_data = platform_start + platform_end
        return platform_data

    def add_feature(self, yocto_oebuild_dir):
        """
            add feature to kconfig
        Args:
            yocto_oebuild_dir:

        Returns:

        """
        feature_path = os.path.join(yocto_oebuild_dir, 'features')
        if os.path.exists(feature_path):
            feature_list = os.listdir(feature_path)
        else:
            logger.error('feature dir is not exists')
            sys.exit(-1)
        feature_start = """
        comment "                           THIS IS CHOOSE FEATURE                               "
        """
        for feature in feature_list:
            support_str = ""
            feature_path = pathlib.Path(yocto_oebuild_dir, 'features', feature)
            feature_data = oebuild_util.read_yaml(feature_path)
            feature_name = os.path.splitext(feature)[0].strip("\n")
            if 'support' in feature_data:
                support_str = ("if PLATFORM_" + feature_data['support'].upper().
                               replace('|', '||PLATFORM_'))

            feature_info = (f"""\nconfig FEATURE_{feature_name.upper()}\n"""
                            f"""    bool "{feature_name}" {support_str}\n\n""")
            feature_start += feature_info

        return feature_start

    def generate_command(self, config_path):
        """
            generate_command to oebuild generate
        Args:
            config_path:

        Returns:

        """
        with open(config_path, 'r', encoding='utf-8') as config_file:
            content = config_file.read()
        content = re.sub('#.*|.*None.*', "", content)
        basic_list = re.findall('(?<=CONFIG_BASIC).*', content)
        platform_search = re.search(r"(?<=CONFIG_PLATFORM_).*(?=\=y)", content)
        feature_list = re.findall(r"(?<=CONFIG_FEATURE_).*(?=\=y)", content)
        build_in = re.search(r"(?<=CONFIG_BUILD).*(?=\=y)", content)
        generate_command = []
        for basic in basic_list:
            basic_info = basic.lower().replace("\"", "").split('=')
            if re.search(r"(?<=--).*(?=\=)", basic):
                basic_info[0] = '-' + re.search(r"(?<=--).*(?=\=)", basic).group().lower()
                if re.search('-DF', basic):
                    generate_command += ['-df']
                else:
                    generate_command += basic_info

        if build_in:
            build_command = build_in.group().lower().replace('=y', '').split('--')
            generate_command += build_command

        platform = platform_search.group() if platform_search else 'qemu-aarch64'
        generate_command += ['-p', platform.lower()]

        for feature in feature_list:
            generate_command += ['-f', feature.lower()]

        return generate_command


def basic_config():
    """
        Kconfig basic_config
    Returns:

    """
    toolchain_help = ("(this param is for external toolchain dir, "
                      "if you want use your own toolchain)")
    nativesdk_help = ("(this param is for external nativesdk dir,"
                      "the param will be useful when you want to build in host)")
    is_disable_fetch_help = ("(this param is set openeuler_fetch in local.conf, "
                             "the default value is enable, if set -df, the OPENEULER_FETCH"
                             "will set to 'disable')")
    basic_str = textwrap.dedent("""
    comment "                           THIS IS BASIC CONFIG                               "
    config BASIC-SSTATE_CACHE--S
        string "sstate_cache     (this param is for SSTATE_MIRRORS)"
        default "None"
    config BASIC-SSTATE_DIR--S_DIR
        string "sstate_dir     (this param is for SSTATE_DIR)"
        default "None"
    config BASIC-TMP_DIR--M
        string "tmp_dir     (this param is for tmp directory, the build result will be stored in)"
        default "None"
    config BASIC-DIRECTORY--D
        string "directory     (this param is build directory, the default is same to platform)"
        default "qemu-aarch64"
    config BASIC-TOOLCHAIN_DIR--T
        string "toolchain_dir     {toolchain_help}"
        default "None"
    config BASIC-NATIVESDK_DIR--N
        string "nativesdk_dir     {nativesdk_help}"
        default "None"
    config BASIC-DOCKER_TAG--TAG
        string "docker_tag     (when build in docker, the param can be point docker image)"
        default "None"
    config BASIC-DATETIME--DT
        string "datetime     (this param is add DATETIME to local.conf)"
        default "None"
    config BASIC-IS_DISABLE_FETCH--DF
        bool "is_disable_fetch     {is_disable_fetch_help}"
        default n
    comment " You can choose Docker or Host, default Docker "
    choice
        prompt "choice build_in"
        default BUILD-B_IN--DOCKER
        config BUILD-B_IN--DOCKER
            bool "build_in_docker"
        config BUILD-B_IN--HOST
            bool "build_in_host"
    endchoice
    """.format(toolchain_help=toolchain_help,
               nativesdk_help=nativesdk_help,
               is_disable_fetch_help=is_disable_fetch_help))
    return basic_str
