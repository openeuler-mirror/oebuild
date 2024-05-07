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
from ruamel.yaml.scalarstring import LiteralScalarString

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.configure import Configure
from oebuild.parse_template import BaseParseTemplate, ParseTemplate, \
    get_docker_param_dict, parse_repos_layers_local_obj
from oebuild.m_log import logger
from oebuild.check_docker_tag import CheckDockerTag
import oebuild.const as oebuild_const


class Generate(OebuildCommand):
    '''
    compile.yaml is generated according to different command parameters by generate
    '''

    help_msg = 'help to mkdir build directory and generate compile.yaml'
    description = textwrap.dedent('''\
            The generate command is the core command in the entire build process, which
            is mainly used to customize the build configuration parameters and generate
            a compile.yaml by customizing each parameter. In addition, for a large number
            of configuration parameter input is not very convenient, generate provides a
            way to specify compile.yaml, users can directly specify the file after
            customizing the build configuration file
            ''')

    def __init__(self):
        self.configure = Configure()
        self.nativesdk_dir = None
        self.toolchain_dir = None
        self.sstate_mirrors = None
        self.tmp_dir = None
        self.oebuild_kconfig_path = os.path.expanduser(
            '~') + '/.local/oebuild_kconfig/'
        super().__init__('generate', self.help_msg, self.description)

    def do_add_parser(self, parser_adder):
        parser = self._parser(parser_adder, usage='''

%(prog)s
''')

        parser.add_argument('-l',
                            '--list',
                            dest='list',
                            action="store_true",
                            help='''
            will list support archs and features
            ''')

        parser.add_argument('-p',
                            '--platform',
                            dest='platform',
                            default="qemu-aarch64",
                            help='''
            this param is for arch, you can find it in yocto-meta-openeuler/.oebuild/platform
            ''')

        parser.add_argument('-s',
                            '--state_mirrors',
                            dest='sstate_mirrors',
                            help='''
            this param is for SSTATE_MIRRORS
            ''')

        parser.add_argument('-s_dir',
                            '--sstate_dir',
                            dest='sstate_dir',
                            help='''
            this param is for SSTATE_DIR
            ''')

        parser.add_argument('-m',
                            '--tmp_dir',
                            dest='tmp_dir',
                            help='''
            this param is for tmp directory, the build result will be stored in
            ''')

        parser.add_argument('-f',
                            '--features',
                            dest='features',
                            action='append',
                            help='''
            this param is feature, it's a reuse command
            ''')

        parser.add_argument('-d',
                            '--directory',
                            dest='directory',
                            help='''
            this param is build directory, the default is same to platform
            ''')

        parser.add_argument('-t',
                            '--toolchain_dir',
                            dest='toolchain_dir',
                            default='',
                            help='''
            this param is for external toolchain dir, if you want use your own toolchain
            ''')

        parser.add_argument('-n',
                            '--nativesdk_dir',
                            dest='nativesdk_dir',
                            default='',
                            help='''
            this param is for external nativesdk dir, the param will be useful when you
            want to build in host
            ''')

        parser.add_argument('-tag',
                            '--docker_tag',
                            dest='docker_tag',
                            default='',
                            help='''
            when build in docker, the param can be point docker image
            ''')

        parser.add_argument('-dt',
                            '--datetime',
                            dest="datetime",
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
                            choices=[
                                oebuild_const.BUILD_IN_DOCKER,
                                oebuild_const.BUILD_IN_HOST
                            ],
                            default=oebuild_const.BUILD_IN_DOCKER,
                            help='''
            This parameter marks the mode at build time, and is built in the container by docker
            ''')

        parser.add_argument('--nativesdk',
                            dest='nativesdk',
                            action="store_true",
                            help='''
                    This parameter is used to indicate whether to build an SDK
                    ''')

        parser.add_argument('--toolchain',
                            dest='toolchain',
                            action="store_true",
                            help='''
                            This parameter is used to indicate whether to build an toolchain
                            ''')

        parser.add_argument('--toolchain_name',
                            dest='toolchain_name',
                            action='append',
                            help='''
                            This parameter is used to toolchain name
                            ''')

        parser.add_argument('--auto_build',
                            dest='auto_build',
                            action="store_true",
                            help='''
                                    This parameter is used for nativesdk and toolchain build
                            ''')

        return parser

    # pylint:disable=[R0914,R0911,R0912,R0915,W1203,R0913]
    def do_run(self, args: argparse.Namespace, unknown=None):
        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            sys.exit(0)
        if not self.configure.is_oebuild_dir():
            logger.error('Your current directory had not finished init')
            sys.exit(-1)

        yocto_dir = self.configure.source_yocto_dir()
        if not self.check_support_oebuild(yocto_dir):
            logger.error(
                'Currently, yocto-meta-openeuler does not support oebuild, \
                    please modify .oebuild/config and re-execute `oebuild update`'
            )
            sys.exit(-1)

        if len(unknown) == 0:
            config_path = self.create_kconfig(yocto_dir)
            if not os.path.exists(config_path):
                sys.exit(0)
            generate_command = self.generate_command(config_path)
            # sys.exit(0)
            subprocess.check_output(f'rm -rf  {config_path}', shell=True)
            args = args.parse_args(generate_command)
        else:
            args = args.parse_args(unknown)
        build_in = args.build_in
        auto_build = bool(args.auto_build)

        if args.nativesdk:
            # this is for default directory is qemu-aarch64
            if args.directory is None or args.directory == '':
                args.directory = "nativesdk"
            build_dir = self._init_build_dir(args=args)
            if build_dir is None:
                sys.exit(0)
            self.build_nativesdk(args.build_in, build_dir, auto_build)
            self._print_nativesdk(build_dir=build_dir)
            sys.exit(0)

        if args.toolchain:
            # this is for default directory is qemu-aarch64
            if args.directory is None or args.directory == '':
                args.directory = "toolchain"
            toolchain_name_list = args.toolchain_name if args.toolchain_name else []
            build_dir = self._init_build_dir(args=args)
            if build_dir is None:
                sys.exit(0)
            self.build_toolchain(build_dir, toolchain_name_list, auto_build)
            self._print_toolchain(build_dir=build_dir)
            sys.exit(-1)

        if args.build_in == oebuild_const.BUILD_IN_HOST:
            try:
                self._check_param_in_host(args=args)
            except ValueError as v_e:
                logger.error(str(v_e))
                sys.exit(-1)
            self.nativesdk_dir = args.nativesdk_dir
            build_in = oebuild_const.BUILD_IN_HOST

        if args.toolchain_dir != '':
            self.toolchain_dir = args.toolchain_dir

        if args.sstate_mirrors is not None:
            self.sstate_mirrors = args.sstate_mirrors

        if args.tmp_dir is not None:
            self.tmp_dir = args.tmp_dir

        if args.list:
            self.list_info()
            sys.exit(0)

        build_dir = self._init_build_dir(args=args)

        if build_dir is None:
            sys.exit(1)

        parser_template = ParseTemplate(yocto_dir=yocto_dir)

        yocto_oebuild_dir = os.path.join(yocto_dir, '.oebuild')

        try:
            self._add_platform_template(args=args,
                                        yocto_oebuild_dir=yocto_oebuild_dir,
                                        parser_template=parser_template)
        except BaseParseTemplate as b_t:
            logger.error(str(b_t))
            sys.exit(-1)
        except ValueError as v_e:
            logger.error(str(v_e))
            sys.exit(-1)

        try:
            self._add_features_template(args=args,
                                        yocto_oebuild_dir=yocto_oebuild_dir,
                                        parser_template=parser_template)
        except BaseParseTemplate as b_t:
            logger.error(str(b_t))
            self._list_feature()
            sys.exit(-1)
        except ValueError as v_e:
            logger.error(str(v_e))
            sys.exit(-1)

        if os.path.exists(os.path.join(build_dir, 'compile.yaml')):
            os.remove(os.path.join(build_dir, 'compile.yaml'))

        docker_image = get_docker_image(
                yocto_dir=self.configure.source_yocto_dir(),
                docker_tag=args.docker_tag,
                configure=self.configure)

        out_dir = pathlib.Path(os.path.join(build_dir, 'compile.yaml'))

        param = parser_template.get_default_generate_compile_conf_param()
        param['nativesdk'] = self.nativesdk_dir
        param['toolchain_dir'] = self.toolchain_dir
        param['build_in'] = build_in
        param['sstate_mirrors'] = self.sstate_mirrors
        param['tmp_dir'] = self.tmp_dir
        param['datetime'] = args.datetime
        param['is_disable_fetch'] = args.is_disable_fetch
        param['docker_image'] = docker_image
        param['src_dir'] = self.configure.source_dir()
        param['compile_dir'] = build_dir
        oebuild_util.write_yaml(
            out_dir,
            parser_template.generate_compile_conf(param))

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

    def _print_nativesdk(self, build_dir):
        format_dir = f'''
generate compile.yaml successful

please run follow command:
=============================================

cd {build_dir}
oebuild bitbake or oebuild bitbake buildtools-extended-tarball

=============================================
'''
        logger.info(format_dir)

    def _print_toolchain(self, build_dir):
        format_dir = f'''
generate toolchain.yaml successful

please run follow command:
=============================================

cd {build_dir}
oebuild toolchain

=============================================
'''
        logger.info(format_dir)

    def _check_param_in_host(self, args):
        if args.toolchain_dir == '':
            raise ValueError(
                "build in host must points toolchain directory in '-t' param")

        if args.nativesdk_dir == '':
            raise ValueError(
                "build in host must points nativesdk directory in '-n' param")

    def _add_platform_template(self, args, yocto_oebuild_dir,
                               parser_template: ParseTemplate):
        if args.platform + '.yaml' in os.listdir(
                os.path.join(yocto_oebuild_dir, 'platform')):
            try:
                parser_template.add_template(
                    os.path.join(yocto_oebuild_dir, 'platform',
                                 args.platform + '.yaml'))
            except BaseParseTemplate as e_p:
                raise e_p
        else:
            logger.error("""
wrong platform, please run `oebuild generate -l` to view support platform""")
            sys.exit(-1)

    def _add_features_template(self, args, yocto_oebuild_dir,
                               parser_template: ParseTemplate):
        if args.features:
            for feature in args.features:
                if feature + '.yaml' in os.listdir(
                        os.path.join(yocto_oebuild_dir, 'features')):
                    try:
                        parser_template.add_template(
                            os.path.join(yocto_oebuild_dir, 'features',
                                         feature + '.yaml'))
                    except BaseParseTemplate as b_t:
                        raise b_t
                else:
                    logger.error("""
Wrong platform, please run `oebuild generate -l` to view support feature""")
                    sys.exit(-1)

    def _init_build_dir(self, args):
        if not os.path.exists(self.configure.build_dir()):
            os.makedirs(self.configure.build_dir())

        if args.directory is None or args.directory == '':
            build_dir = os.path.join(self.configure.build_dir(), args.platform)
        else:
            build_dir = os.path.join(self.configure.build_dir(),
                                     args.directory)

        if not os.path.abspath(build_dir).startswith(
                self.configure.build_dir()):
            logger.error("Build path must in oebuild workspace")
            return None

        # detects if a build directory already exists
        if os.path.exists(build_dir):
            logger.warning("the build directory %s already exists", build_dir)
            while True:
                in_res = input(f"""
    do you want to overwrite it({os.path.basename(build_dir)})? the overwrite
    action will replace the compile.yaml to new and delete conf directory,
    enter Y for yes, N for no, C for create:""")
                if in_res not in ["Y", "y", "yes", "N", "n", "no", "C", "c", "create"]:
                    print("""
    wrong input""")
                    continue
                if in_res in ['N', 'n', 'no']:
                    return None
                if in_res in ['C', 'c', 'create']:
                    in_res = input("""
    please enter now build name, we will create it under build directory:""")
                    build_dir = os.path.join(self.configure.build_dir(), in_res)
                    if os.path.exists(build_dir):
                        continue
                break
            if os.path.exists(os.path.join(build_dir, "conf")):
                rmtree(os.path.join(build_dir, "conf"))
            elif os.path.exists(build_dir):
                rmtree(build_dir)
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
        print(table)

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
            feat = oebuild_util.read_yaml(
                pathlib.Path(
                    os.path.join(yocto_oebuild_dir, 'features', feature)))
            if "support" in feat:
                table.add_row([feature_name, feat.get('support')])
            else:
                table.add_row([feature_name, "all"])
        print(table)

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
        toolchain_data = self.add_toolchain(yocto_oebuild_dir)
        if not os.path.exists(
                pathlib.Path(self.oebuild_kconfig_path).absolute()):
            os.makedirs(pathlib.Path(self.oebuild_kconfig_path).absolute())
        kconfig_path = pathlib.Path(self.oebuild_kconfig_path,
                                    str(int(time.time())))
        info = textwrap.dedent("""
        config NATIVE_SDK
            bool "Build Nativesdk"
            depends on !TOOLCHAIN
        config AUTO_BUILD
            bool "Auto Build"
            depends on NATIVE_SDK
        config IMAGE
            bool "Build OS"
            depends on !NATIVE_SDK && !TOOLCHAIN
            default y
        if IMAGE
        """)
        write_data = toolchain_data + info + platform_data + feature_data + basic_data + "\nendif"
        with open(kconfig_path, 'w', encoding='utf-8') as kconfig_file:
            kconfig_file.write(write_data)

        kconf = Kconfig(filename=kconfig_path)
        os.environ["MENUCONFIG_STYLE"] = "aquatic selection=fg:white,bg:blue"
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
            platform_info = (
                f"""    config PLATFORM_{platform_name.upper()}\n"""
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
                support_str = ("if PLATFORM_" +
                               feature_data['support'].upper().replace(
                                   '|', '||PLATFORM_'))

            feature_info = (f"""\nconfig FEATURE_{feature_name.upper()}\n"""
                            f"""    bool "{feature_name}" {support_str}\n\n""")
            feature_start += feature_info

        return feature_start

    def add_toolchain(self, yocto_oebuild_dir):
        """
            add toolchain to kconfig
        Args:
            yocto_oebuild_dir: yocto_oebuild_dir

        Returns:

        """
        cross_path = os.path.join(yocto_oebuild_dir, "cross-tools")
        if not os.path.exists(cross_path):
            logger.error('Build dependency not downloaded, not supported for build. Please '
                         'download the latest yocto meta openeuler repository')
            sys.exit(-1)
        toolchain_list = os.listdir(os.path.join(cross_path, 'configs'))
        toolchain_start = """
        config TOOLCHAIN
            bool "Build Toolchain"
        config AUTO_BUILD
            bool "Auto Build"
            depends on TOOLCHAIN
        """
        for config in toolchain_list:
            if not re.search('xml', config):
                toolchain_info = (f"""\nconfig TOOLCHAINS_{config.upper()}\n"""
                                  f"""    bool "{config.upper()}"\n"""
                                  """     depends on TOOLCHAIN && AUTO_BUILD\n""")
                toolchain_start += toolchain_info

        return toolchain_start

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
        platform_search = re.search(r"(?<=CONFIG_PLATFORM_).*(?==y)", content)
        feature_list = re.findall(r"(?<=CONFIG_FEATURE_).*(?==y)", content)
        build_in = re.search(r"(?<=CONFIG_BUILD).*(?==y)", content)
        native_sdk = re.search("(?<=NATIVE_SDK).*", content)
        tool_chain = re.search("(?<=TOOLCHAIN).*", content)
        toolchain_list = re.findall("(?<=TOOLCHAINS_).*(?==y)", content)
        auto_build = re.findall("(?<=AUTO_BUILD).*", content)
        generate_command = []
        for basic in basic_list:
            basic_info = basic.lower().replace("\"", "").split('=')
            if re.search(r"(?<=--).*(?==)", basic):
                basic_info[0] = '-' + re.search(r"(?<=--).*(?==)",
                                                basic).group().lower()
                if re.search('-DF', basic):
                    generate_command += ['-df']
                else:
                    generate_command += basic_info

        if build_in:
            build_command = build_in.group().lower().replace('=y',
                                                             '').split('--')
            generate_command += build_command

        platform = platform_search.group(
        ) if platform_search else 'qemu-aarch64'
        generate_command += ['-p', platform.lower()]

        for feature in feature_list:
            generate_command += ['-f', feature.lower()]

        if native_sdk:
            generate_command = ['--nativesdk']

        if tool_chain:
            generate_command = ['--toolchain']

            if toolchain_list:
                for toolchain_info in toolchain_list:
                    generate_command += ['--toolchain_name', toolchain_info.lower()]

        if auto_build:
            generate_command += ['--auto_build']

        return generate_command

    def build_nativesdk(self, build_in, build_dir, auto_build):
        """

        Args:
            build_in: host or docker
            directory: build dir
            auto_build: auto_build
        Returns:

        """
        compile_dir = os.path.join(self.configure.build_dir(), build_dir)
        compile_yaml_path = f"{compile_dir}/compile.yaml"
        common_yaml_path = os.path.join(
            self.configure.source_yocto_dir(), '.oebuild/common.yaml')
        repos, layers, local_conf = parse_repos_layers_local_obj(common_yaml_path)
        info = {
            'repos': repos,
            'layers': layers,
            'local_conf': local_conf
        }
        if build_in == 'host':
            info['build_in'] = 'host'
        else:
            docker_image = get_docker_image(
                yocto_dir=self.configure.source_yocto_dir(),
                docker_tag="latest",
                configure=self.configure
            )
            info['docker_param'] = get_docker_param_dict(
                docker_image=docker_image,
                src_dir=self.configure.source_dir(),
                compile_dir=compile_dir,
                toolchain_dir=None,
                sstate_mirrors=None
            )
        # add nativesdk conf
        nativesdk_yaml_path = os.path.join(
            self.configure.source_yocto_dir(), '.oebuild/nativesdk/local.conf')
        with open(nativesdk_yaml_path, 'r', encoding='utf-8') as f:
            local_conf += f.read()+"\n"
            info['local_conf'] = LiteralScalarString(local_conf)
        oebuild_util.write_yaml(compile_yaml_path, info)
        if auto_build:
            os.chdir(compile_dir)
            subprocess.run('oebuild bitbake buildtools-extended-tarball', shell=True, check=False)

    def build_toolchain(self, build_dir, toolchain_name_list, auto_build):
        """

        Args:
            toolchain_name_list: choose toolchain
            auto_build: auto_build

        Returns:

        """
        source_cross_dir = os.path.join(self.configure.source_yocto_dir(), ".oebuild/cross-tools")
        if not os.path.exists(source_cross_dir):
            logger.error('Build dependency not downloaded, not supported for build. Please '
                         'download the latest yocto meta openeuler repository')
            sys.exit(-1)
        # add toolchain.yaml to compile
        docker_param = get_docker_param_dict(
            docker_image=get_sdk_docker_image(yocto_dir=self.configure.source_yocto_dir()),
            src_dir=self.configure.source_dir(),
            compile_dir=build_dir,
            toolchain_dir=None,
            sstate_mirrors=None)
        config_list = []
        for toolchain_name in toolchain_name_list:
            if toolchain_name.startswith("config_"):
                config_list.append(toolchain_name)
                continue
            config_list.append("config_" + toolchain_name)
        oebuild_util.write_yaml(
            yaml_path=os.path.join(build_dir, 'toolchain.yaml'),
            data={
                'config_list': config_list,
                'docker_param': docker_param
            }
        )
        if auto_build:
            with subprocess.Popen('oebuild toolchain auto', shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  cwd=build_dir,
                                  encoding="utf-8", text=True) as s_p:
                if s_p.returncode is not None and s_p.returncode != 0:
                    err_msg = ''
                    if s_p.stderr is not None:
                        for line in s_p.stderr:
                            err_msg.join(line)
                        raise ValueError(err_msg)
                res = None
                while res is None:
                    res = s_p.poll()
                    if s_p.stdout is not None:
                        for line in s_p.stdout:
                            logger.info(line.strip('\n'))
                    if s_p.stderr is not None:
                        for line in s_p.stderr:
                            logger.error(line.strip('\n'))
                sys.exit(res)


def get_docker_image(yocto_dir, docker_tag, configure: Configure):
    '''
    get docker image
    first we search in yocto-meta-openeuler/.oebuild/env.yaml
    second search in default ${workdir}/.oebuild/config.yaml
    third get from user input
    '''
    docker_image = oebuild_util.get_docker_image_from_yocto(yocto_dir=yocto_dir)
    if docker_image is None:
        check_docker_tag = CheckDockerTag(docker_tag, configure)
        oebuild_config = configure.parse_oebuild_config()
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
                    print(
                        f"{key}, {oebuild_config.docker.repo_url}:{value}")
                k = input("please entry number:")
                if k == "q":
                    sys.exit(0)
                try:
                    index = int(k)
                    docker_tag = image_list[index]
                    break
                except IndexError:
                    print("please entry true number")
        docker_tag = docker_tag.strip()
        docker_tag = docker_tag.strip('\n')
        docker_image = f"{oebuild_config.docker.repo_url}:{docker_tag}"
    return docker_image


def get_sdk_docker_image(yocto_dir):
    '''
    get toolchain docker image
    '''
    docker_image = oebuild_util.get_sdk_docker_image_from_yocto(yocto_dir=yocto_dir)
    if docker_image is None:
        docker_image = oebuild_const.DEFAULT_SDK_DOCKER
    return docker_image


def basic_config():
    """
        Kconfig basic_config
    Returns:

    """
    toolchain_help = ("(this param is for external toolchain dir, "
                      "if you want use your own toolchain)")
    nativesdk_help = (
        "(this param is for external nativesdk dir,"
        "the param will be useful when you want to build in host)")
    is_disable_fetch_help = (
        "(this param is set openeuler_fetch in local.conf, "
        "the default value is enable, if set -df, the OPENEULER_FETCH"
        "will set to 'disable')")
    basic_str = textwrap.dedent(f"""
    comment "                           THIS IS BASIC CONFIG                               "
    config BASIC-SSTATE_CACHE--S
        string "sstate_mirrors     (this param is for SSTATE_MIRRORS)"
        default "None"
    config BASIC-SSTATE_DIR--S_DIR
        string "sstate_dir     (this param is for SSTATE_DIR)"
        default "None"
    config BASIC-TMP_DIR--M
        string "tmp_dir     (this param is for tmp directory, the build result will be stored in)"
        default "None"
    config BASIC-DIRECTORY--D
        string "directory     (this param is build directory, the default is same to platform)"
        default "None"
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
    """)
    return basic_str
