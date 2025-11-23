"""
Copyright (c) 2023 openEuler Embedded
oebuild is licensed under Mulan PSL v2.
You can use this software according to the terms and conditions of the Mulan PSL v2.
You may obtain a copy of Mulan PSL v2 at:
         http://license.coscl.org.cn/MulanPSL2
THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
See the Mulan PSL v2 for more details.
"""

import argparse
import re
import subprocess
import textwrap
import os
import sys
import pathlib
from shutil import rmtree

from prettytable import PrettyTable, TableStyle, HRuleStyle, VRuleStyle
from ruamel.yaml.scalarstring import LiteralScalarString

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.configure import Configure
from oebuild.parse_template import (
    BaseParseTemplate,
    ParseTemplate,
    get_docker_param_dict,
    parse_repos_layers_local_obj,
)
from oebuild.m_log import logger
from oebuild.check_docker_tag import CheckDockerTag
import oebuild.const as oebuild_const
from oebuild.app.plugins.generate.parses import parsers, parse_feature_files
from oebuild.app.plugins.generate.kconfig_generator import KconfigGenerator


class Generate(OebuildCommand):
    """Generate compile.yaml (and toolchain.yaml) from CLI options."""

    help_msg = 'Create build dir and generate compile.yaml'
    description = textwrap.dedent("""\
            Customize build parameters and output compile.yaml; optionally
            emit toolchain.yaml for GCC/LLVM builds.
            """)

    def __init__(self):
        self.configure = Configure()
        # Cache of parsed CLI parameters affecting generation
        # nativesdk_dir
        # toolchain_dir
        # llvm_toolchain_dir
        # sstate_mirrors
        # sstate_dir
        # tmp_dir
        # cache_src_dir
        self.params = {}
        self.oebuild_kconfig_path = (
            os.path.expanduser('~') + '/.local/oebuild_kconfig/'
        )
        super().__init__('generate', self.help_msg, self.description)

    def do_add_parser(self, parser_adder):
        """Add arguments to the parser."""
        parser = self._parser(
            parser_adder,
            usage="""
%(prog)s
""",
        )

        parser = parsers(parser)

        return parser

    # pylint:disable=[R0914,R0911,R0912,R0915,W1203,R0913]
    def do_run(self, args: argparse.Namespace, unknown=None):
        """The main entry point for the command."""
        if self.pre_parse_help(args, unknown):
            sys.exit(0)
        if not self.configure.is_oebuild_dir():
            logger.error('Your current directory had not finished init')
            sys.exit(-1)

        yocto_dir = self.configure.source_yocto_dir()
        if not self.check_support_oebuild(yocto_dir):
            logger.error(
                'yocto-meta-openeuler does not container valid oebuild metadata '
                'Update .oebuild/config and re-run `oebuild update`.'
            )
            sys.exit(-1)

        if len(unknown) == 0:
            yocto_oebuild_dir = pathlib.Path(yocto_dir, '.oebuild')
            kconfig_generator = KconfigGenerator(
                self.oebuild_kconfig_path, yocto_oebuild_dir
            )
            config_path = kconfig_generator.create_kconfig()
            if not os.path.exists(config_path):
                sys.exit(0)
            g_command = self.generate_command(config_path)
            subprocess.check_output(f'rm -rf  {config_path}', shell=True)
            args = args.parse_args(g_command)
        else:
            args = args.parse_args(unknown)
        auto_build = bool(args.auto_build)

        if args.nativesdk:
            # default dir for nativesdk
            if args.directory is None or args.directory == '':
                args.directory = 'nativesdk'
            build_dir = self._init_build_dir(args=args)
            if build_dir is None:
                sys.exit(0)
            self.build_nativesdk(args.build_in, build_dir, auto_build)
            self._print_nativesdk(build_dir=build_dir)
            sys.exit(0)

        if args.gcc:
            # default dir for toolchain
            if args.directory is None or args.directory == '':
                args.directory = 'toolchain'
            toolchain_name_list = args.gcc_name if args.gcc_name else []
            build_dir = self._init_build_dir(args=args)
            if build_dir is None:
                sys.exit(0)
            self.build_gcc(build_dir, toolchain_name_list, auto_build)
            self._print_toolchain(
                build_dir=build_dir,
            )
            sys.exit(0)

        if args.llvm:
            # default dir for toolchain
            if args.directory is None or args.directory == '':
                args.directory = 'toolchain'
            llvm_lib = args.llvm_lib
            build_dir = self._init_build_dir(args=args)
            if build_dir is None:
                sys.exit(0)
            self.build_llvm(build_dir, llvm_lib, auto_build)
            self._print_toolchain(build_dir=build_dir)
            sys.exit(0)

        if args.nativesdk_dir != '':
            self.params['nativesdk_dir'] = args.nativesdk_dir

        if args.toolchain_dir != '':
            self.params['toolchain_dir'] = args.toolchain_dir

        if args.llvm_toolchain_dir != '':
            self.params['llvm_toolchain_dir'] = args.llvm_toolchain_dir

        if args.sstate_mirrors is not None:
            self.params['sstate_mirrors'] = args.sstate_mirrors

        if args.sstate_dir is not None:
            self.params['sstate_dir'] = args.sstate_dir

        if args.tmp_dir is not None:
            self.params['tmp_dir'] = args.tmp_dir

        if args.cache_src_dir is not None and args.cache_src_dir != '':
            self.params['cache_src_dir'] = args.cache_src_dir

        if args.list:
            self.list_info()
            sys.exit(0)

        build_dir = self._init_build_dir(args=args)

        if build_dir is None:
            sys.exit(1)

        parser_template = ParseTemplate(yocto_dir=yocto_dir)

        yocto_oebuild_dir = pathlib.Path(yocto_dir, '.oebuild')

        try:
            self._add_platform_template(
                args=args,
                yocto_oebuild_dir=yocto_oebuild_dir,
                parser_template=parser_template,
            )
        except BaseParseTemplate as b_t:
            logger.error(str(b_t))
            sys.exit(-1)
        except ValueError as v_e:
            logger.error(str(v_e))
            sys.exit(-1)

        try:
            self._add_features_template(
                args=args,
                yocto_oebuild_dir=yocto_oebuild_dir,
                parser_template=parser_template,
            )
        except BaseParseTemplate as b_t:
            logger.error(str(b_t))
            self._list_feature()
            sys.exit(-1)
        except ValueError as v_e:
            logger.error(str(v_e))
            sys.exit(-1)

        compile_yaml_path = pathlib.Path(build_dir, 'compile.yaml')
        if compile_yaml_path.exists():
            compile_yaml_path.unlink()

        docker_image = get_docker_image(
            yocto_dir=self.configure.source_yocto_dir(),
            docker_tag='',
            configure=self.configure,
        )

        out_dir = pathlib.Path(build_dir, 'compile.yaml')

        param = parser_template.get_default_generate_compile_conf_param()
        param['nativesdk_dir'] = self.params.get('nativesdk_dir', None)
        param['toolchain_dir'] = self.params.get('toolchain_dir', None)
        param['llvm_toolchain_dir'] = self.params.get(
            'llvm_toolchain_dir', None
        )
        param['build_in'] = args.build_in
        param['sstate_mirrors'] = self.params.get('sstate_mirrors', None)
        param['sstate_dir'] = self.params.get('sstate_dir', None)
        param['tmp_dir'] = self.params.get('tmp_dir', None)
        param['datetime'] = args.datetime
        param['no_fetch'] = args.no_fetch
        param['no_layer'] = args.no_layer
        param['docker_image'] = docker_image
        param['src_dir'] = self.configure.source_dir()
        param['compile_dir'] = build_dir
        param['cache_src_dir'] = self.params.get('cache_src_dir', None)
        oebuild_util.write_yaml(
            out_dir, parser_template.generate_compile_conf(param)
        )

        self._print_generate(build_dir=build_dir)

    def _print_generate(self, build_dir):
        format_dir = f"""
generate compile.yaml successful

Run commands below:
=============================================

cd {build_dir}
oebuild bitbake

=============================================
"""
        logger.info(format_dir)

    def _print_nativesdk(self, build_dir):
        format_dir = f"""
generate compile.yaml successful

Run commands below:
=============================================

cd {build_dir}
oebuild bitbake or oebuild bitbake buildtools-extended-tarball

=============================================
"""
        logger.info(format_dir)

    def _print_toolchain(self, build_dir):
        format_dir = f"""
generate toolchain.yaml successful

Run commands below:
=============================================

cd {build_dir}
oebuild toolchain

=============================================
"""
        logger.info(format_dir)

    def _add_platform_template(
        self, args, yocto_oebuild_dir, parser_template: ParseTemplate
    ):
        platform_path = pathlib.Path(yocto_oebuild_dir, 'platform')
        platform_files = [
            f.name for f in platform_path.iterdir() if f.is_file()
        ]
        if args.platform + '.yaml' in platform_files:
            try:
                platform_file = platform_path / (args.platform + '.yaml')
                parser_template.add_template(platform_file)
            except BaseParseTemplate as e_p:
                raise e_p
        else:
            logger.error(
                'Invalid platform. Run `oebuild generate -l` to list supported platforms.'
            )
            sys.exit(-1)

    def _add_features_template(
        self, args, yocto_oebuild_dir, parser_template: ParseTemplate
    ):
        if args.features:
            features_path = pathlib.Path(yocto_oebuild_dir, 'features')
            feature_files = [
                f.name for f in features_path.iterdir() if f.is_file()
            ]
            for feature in args.features:
                if feature + '.yaml' in feature_files:
                    try:
                        feature_file = features_path / (feature + '.yaml')
                        parser_template.add_template(feature_file)
                    except BaseParseTemplate as b_t:
                        raise b_t
                else:
                    logger.error(
                        'Invalid feature. Run `oebuild generate -l` to list features.'
                    )
                    sys.exit(-1)

    def _init_build_dir(self, args):
        build_dir_path = pathlib.Path(self.configure.build_dir())
        if not build_dir_path.exists():
            build_dir_path.mkdir(parents=True)

        if args.directory is None or args.directory == '':
            build_dir = build_dir_path / args.platform
        else:
            build_dir = build_dir_path / args.directory

        if (
            not pathlib.Path(build_dir)
            .absolute()
            .is_relative_to(build_dir_path.absolute())
        ):
            logger.error('Build path must in oebuild workspace')
            return None

        # If build dir exists, prompt/handle overwrite
        if build_dir.exists():
            logger.warning('the build directory %s already exists', build_dir)
            while not args.yes:
                in_res = input(f"""
    Overwrite {build_dir.name}? This will replace compile.yaml/toolchain.yaml and delete conf/
    Enter Y=yes, N=no, C=create : """)
                if in_res not in [
                    'Y',
                    'y',
                    'yes',
                    'N',
                    'n',
                    'no',
                    'C',
                    'c',
                    'create',
                ]:
                    print('Invalid input')
                    continue
                if in_res in ['N', 'n', 'no']:
                    return None
                if in_res in ['C', 'c', 'create']:
                    in_res = input(
                        'Enter new build name (will be created under build/):'
                    )
                    build_dir = build_dir_path / in_res
                    if build_dir.exists():
                        continue
                break
            conf_dir = build_dir / 'conf'
            if conf_dir.exists():
                rmtree(conf_dir)
            elif build_dir.exists():
                rmtree(build_dir)
        build_dir.mkdir(parents=True, exist_ok=True)
        return str(build_dir)

    def list_info(
        self,
    ):
        """
        print platform list or feature list
        """
        self._list_platform()
        self._list_feature()

    def _list_platform(self):
        logger.info(
            '\n================= Available Platforms ================='
        )
        yocto_dir = self.configure.source_yocto_dir()
        yocto_oebuild_dir = pathlib.Path(yocto_dir, '.oebuild')
        platform_path = pathlib.Path(yocto_oebuild_dir, 'platform')
        list_platform = [f for f in platform_path.iterdir() if f.is_file()]
        terminal_width = self._get_terminal_width()
        table = self._build_table(
            ['Platform Name'], terminal_width, title='Available Platforms'
        )
        for platform in list_platform:
            if platform.suffix in ['.yml', '.yaml']:
                table.add_row([platform.stem])
        table.sortby = 'Platform Name'
        print(table)

    def _list_feature(self):
        logger.info(
            '\n================= Available Features =================='
        )
        yocto_dir = self.configure.source_yocto_dir()
        yocto_oebuild_dir = pathlib.Path(yocto_dir, '.oebuild')
        feature_triples = parse_feature_files(yocto_oebuild_dir)
        terminal_width = self._get_terminal_width()
        table = self._build_table(
            ['Feature Name', 'Supported Arch'],
            terminal_width,
            title='Available Features',
        )
        for feature_name, _, feature_data in feature_triples:
            table.add_row([feature_name, feature_data.get('support') or 'all'])
        print(table)
        logger.info(
            """* 'Supported Arch' defaults to 'all' if not specified in the feature's .yaml file."""
        )

    def _build_table(self, headers, terminal_width, title=None):
        narrow_charnum, narrow_colnum = 60, 10
        max_width = max(int(terminal_width * 0.9), 20)
        table = PrettyTable(headers, max_width=max_width)
        table.align = 'l'
        table.header = True

        col_width = max(10, max_width // max(len(headers), 1))
        for header in headers:
            table.max_width[header] = col_width

        is_narrow = (
            terminal_width < narrow_charnum or col_width < narrow_colnum
        )
        if is_narrow:
            table.set_style(TableStyle.PLAIN_COLUMNS)
            table.hrules = HRuleStyle.NONE
            table.vrules = VRuleStyle.NONE
            table.left_padding_width = 0
            table.right_padding_width = 0
        else:
            table.set_style(TableStyle.SINGLE_BORDER)
            table.hrules = HRuleStyle.FRAME
            table.vrules = VRuleStyle.FRAME
            table.left_padding_width = 1
            table.right_padding_width = 1
            if title:
                table.title = title
        return table

    @staticmethod
    def _get_terminal_width():
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 80

    def check_support_oebuild(self, yocto_dir):
        """
        Return True if <yocto-meta-openeuler>/.oebuild exists.
        """
        return pathlib.Path(yocto_dir, '.oebuild').exists()

    def generate_command(self, config_path):
        """
        Parse .config and build argv list for 'oebuild generate'.
        """
        with open(config_path, 'r', encoding='utf-8') as config_file:
            content = config_file.read()
        # sys.exit(0)
        content = re.sub('#.*|.*None.*', '', content)
        common_list = re.findall('(?<=CONFIG_COMMON_).*', content)
        platform_search = re.search(r'(?<=CONFIG_PLATFORM_).*(?==y)', content)
        feature_list = re.findall(r'(?<=CONFIG_FEATURE_).*(?==y)', content)
        build_in = re.search(r'(?<=CONFIG_BUILD_IN-).*(?==y)', content)
        nativesdk = re.search(r'(?<=CONFIG_NATIVESDK).*(?==y)', content)
        gcc = re.search(r'(?<=CONFIG_GCC-TOOLCHAIN).*(?==y)', content)
        gcc_list = re.findall(r'(?<=CONFIG_GCC-TOOLCHAIN_).*(?==y)', content)
        llvm = re.search(r'(?<=CONFIG_LLVM-TOOLCHAIN).*(?==y)', content)
        llvm_lib = re.search(
            r'(?<=CONFIG_LLVM-TOOLCHAIN_AARCH64-LIB).*', content
        )
        auto_build = re.search(r'(?<=CONFIG_AUTO-BUILD).*(?==y)', content)
        g_command = []
        for basic in common_list:
            basic_info = basic.lower().replace('"', '').split('=')
            basic_info[0] = basic_info[0].replace('-', '_')
            if basic_info[0] == 'no_fetch':
                g_command += ['--' + basic_info[0]]
                continue
            if basic_info[0] == 'no_layer':
                g_command += ['--' + basic_info[0]]
                continue
            g_command += ['--' + basic_info[0], basic_info[1]]
        # sys.exit(0)
        if build_in:
            g_command += ['-b_in', build_in.group().lower()]

        platform = (
            platform_search.group() if platform_search else 'qemu-aarch64'
        )
        g_command += ['-p', platform.lower()]

        for feature in feature_list:
            g_command += ['-f', feature.lower()]

        if nativesdk:
            g_command += ['--nativesdk']

        if gcc:
            g_command += ['--gcc']

            if gcc_list:
                for gcc_name in gcc_list:
                    g_command += ['--gcc_name', gcc_name.lower()]

        if llvm:
            g_command += ['--llvm']
            if llvm_lib:
                g_command += ['--llvm_lib', llvm_lib.group()]

        if auto_build:
            g_command += ['--auto_build']

        return g_command

    def build_nativesdk(self, build_in, build_dir, auto_build):
        """

        Args:
            build_in: host or docker
            directory: build dir
            auto_build: auto_build
        Returns:

        """
        compile_dir = os.path.join(self.configure.build_dir(), build_dir)
        compile_yaml_path = f'{compile_dir}/compile.yaml'
        common_yaml_path = os.path.join(
            self.configure.source_yocto_dir(), '.oebuild/common.yaml'
        )
        repos, layers, local_conf = parse_repos_layers_local_obj(
            common_yaml_path
        )
        info = {'repos': repos, 'layers': layers, 'local_conf': local_conf}
        if build_in == 'host':
            info['build_in'] = 'host'
        else:
            docker_image = get_docker_image(
                yocto_dir=self.configure.source_yocto_dir(),
                docker_tag='latest',
                configure=self.configure,
            )
            info['docker_param'] = get_docker_param_dict(
                docker_image=docker_image,
                dir_list={
                    'src_dir': self.configure.source_dir(),
                    'compile_dir': compile_dir,
                    'toolchain_dir': None,
                    'llvm_toolchain_dir': None,
                    'sstate_mirrors': None,
                },
            )
        # add nativesdk conf
        nativesdk_yaml_path = os.path.join(
            self.configure.source_yocto_dir(), '.oebuild/nativesdk/local.conf'
        )
        with open(nativesdk_yaml_path, 'r', encoding='utf-8') as f:
            local_conf += f.read() + '\n'
            info['local_conf'] = LiteralScalarString(local_conf)
        oebuild_util.write_yaml(compile_yaml_path, info)
        if auto_build:
            os.chdir(compile_dir)
            subprocess.run(
                'oebuild bitbake buildtools-extended-tarball',
                shell=True,
                check=False,
            )

    def build_gcc(self, build_dir, gcc_name_list, auto_build):
        """

        Args:
            gcc_name_list: choose toolchain
            auto_build: auto_build

        Returns:

        """
        source_cross_dir = pathlib.Path(
            self.configure.source_yocto_dir(), '.oebuild/cross-tools'
        )
        if not source_cross_dir.exists():
            logger.error(
                'Build dependency not downloaded, not supported for build. Please '
                'download the latest yocto meta openeuler repository'
            )
            sys.exit(-1)
        # add toolchain.yaml to compile
        docker_param = get_docker_param_dict(
            docker_image=get_sdk_docker_image(
                yocto_dir=self.configure.source_yocto_dir()
            ),
            dir_list={
                'src_dir': self.configure.source_dir(),
                'compile_dir': build_dir,
                'toolchain_dir': None,
                'llvm_toolchain_dir': None,
                'sstate_mirrors': None,
            },
        )
        config_list = []
        for gcc_name in gcc_name_list:
            if gcc_name.startswith('config_'):
                config_list.append(gcc_name)
                continue
            config_list.append('config_' + gcc_name)
        oebuild_util.write_yaml(
            yaml_path=pathlib.Path(build_dir, 'toolchain.yaml'),
            data={
                'kind': oebuild_const.GCC_TOOLCHAIN,
                'gcc_configs': config_list,
                'docker_param': docker_param,
            },
        )
        if auto_build:
            with subprocess.Popen(
                'oebuild toolchain auto',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=build_dir,
                encoding='utf-8',
                text=True,
            ) as s_p:
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

    def build_llvm(self, build_dir, llvm_lib, auto_build):
        """

        Args:
            llvm_lib: llvm aarch64 lib
            auto_build: auto_build

        Returns:

        """
        source_llvm_dir = pathlib.Path(
            self.configure.source_yocto_dir(), '.oebuild/llvm-toolchain'
        )
        if not source_llvm_dir.exists():
            logger.error(
                'Build dependency not downloaded, not supported for build. Please '
                'download the latest yocto meta openeuler repository'
            )
            sys.exit(-1)
        # add toolchain.yaml to compile
        docker_param = get_docker_param_dict(
            docker_image=get_sdk_docker_image(
                yocto_dir=self.configure.source_yocto_dir()
            ),
            dir_list={
                'src_dir': self.configure.source_dir(),
                'compile_dir': build_dir,
                'toolchain_dir': None,
                'llvm_toolchain_dir': None,
                'sstate_mirrors': None,
            },
        )
        oebuild_util.write_yaml(
            yaml_path=pathlib.Path(build_dir, 'toolchain.yaml'),
            data={
                'kind': oebuild_const.LLVM_TOOLCHAIN,
                'llvm_lib': llvm_lib,
                'docker_param': docker_param,
            },
        )
        if auto_build:
            with subprocess.Popen(
                'oebuild toolchain auto',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=build_dir,
                encoding='utf-8',
                text=True,
            ) as s_p:
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
    """
    Resolve docker image from env, config defaults, or user selection, ordered by priority
    """
    docker_image = oebuild_util.get_docker_image_from_yocto(
        yocto_dir=yocto_dir
    )
    if docker_image is None:
        check_docker_tag = CheckDockerTag(docker_tag, configure)
        oebuild_config = configure.parse_oebuild_config()
        if check_docker_tag.get_tag() is not None:
            docker_tag = str(check_docker_tag.get_tag())
        else:
            # select docker image
            while True:
                print('Select a container image by number (q to quit):')
                image_list = check_docker_tag.get_tags()

                for key, value in enumerate(image_list):
                    print(f'{key}, {oebuild_config.docker.repo_url}:{value}')
                k = input('Enter number: ')
                if k == 'q':
                    sys.exit(0)
                try:
                    index = int(k)
                    docker_tag = image_list[index]
                    break
                except IndexError:
                    print('Enter a valid number')
        docker_tag = docker_tag.strip()
        docker_tag = docker_tag.strip('\n')
        docker_image = f'{oebuild_config.docker.repo_url}:{docker_tag}'
    return docker_image


def get_sdk_docker_image(yocto_dir):
    """
    get toolchain docker image
    """
    docker_image = oebuild_util.get_sdk_docker_image_from_yocto(
        yocto_dir=yocto_dir
    )
    if docker_image is None:
        docker_image = oebuild_const.DEFAULT_SDK_DOCKER
    return docker_image
