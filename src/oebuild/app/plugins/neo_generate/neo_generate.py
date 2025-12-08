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
import os
import pathlib
import sys
import textwrap
from shutil import rmtree

from menuconfig_generator import NeoMenuconfigGenerator
from prettytable import HRuleStyle, PrettyTable, TableStyle, VRuleStyle
from ruamel.yaml.scalarstring import LiteralScalarString

import oebuild.util as oebuild_util
from oebuild.app.plugins.generate.generate import get_docker_image
from oebuild.app.plugins.generate.parses import parsers
from oebuild.command import OebuildCommand
from oebuild.configure import Configure
from oebuild.m_log import logger
from oebuild.nightly_features import (
    ResolutionError,
    FeatureResolver,
    NeoFeatureError,
    FeatureRegistry,
)
from oebuild.parse_template import (
    BaseParseTemplate,
    FeatureTemplate,
    ParseTemplate,
)


class NeoGenerate(OebuildCommand):
    """Neo-generate handles the refreshed feature workflow starting point."""

    help_msg = 'neo generate command'
    description = textwrap.dedent("""
            Neo-generate manages build preparation with nightly-features state
            while keeping other generate options stable.
            """)

    def __init__(self):
        self.configure = Configure()
        self.params = {}
        self.yocto_dir = None
        self.feature_registry = None
        super().__init__('neo-generate', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder, usage="""%(prog)s""")
        parser = parsers(parser, include_features=True)
        menu_group = parser.add_mutually_exclusive_group()
        menu_group.add_argument(
            '--menuconfig',
            dest='menuconfig',
            action='store_true',
            help="""
            Launch an interactive menuconfig to pick nightly features.
            """,
        )
        menu_group.add_argument(
            '--no-menuconfig',
            dest='menuconfig',
            action='store_false',
            help='Skip the interactive menuconfig step and rely on explicit feature IDs.',
        )
        parser.set_defaults(menuconfig=True)
        return parser

    def do_run(self, args: argparse.ArgumentParser, unknown=[]):
        if self.pre_parse_help(args, unknown):
            sys.exit(0)

        unknown = unknown or []
        parsed_args = args.parse_args(unknown)

        self._validate_environment()

        if parsed_args.list:
            self.list_info()
            return

        interactive_invocation = parsed_args.menuconfig and not unknown
        if interactive_invocation:
            menu_selection = self._run_menuconfig(parsed_args)
            if menu_selection is None:
                logger.info(
                    'Menuconfig was exited without applying any configuration; nothing generated.'
                )
                return
            parsed_args.platform = menu_selection.platform
            parsed_args.features = menu_selection.features

        try:
            resolution = self._resolve_features(
                parsed_args.platform, parsed_args.features or []
            )
        except ResolutionError as err:
            logger.error(str(err))
            sys.exit(1)

        try:
            parser_template = self._prepare_parser_template(
                args=parsed_args,
                resolved_features=resolution.features,
            )
        except BaseParseTemplate as b_t:
            logger.error(str(b_t))
            sys.exit(-1)
        except ValueError as v_e:
            logger.error(str(v_e))
            sys.exit(-1)

        build_dir = self._init_build_dir(parsed_args)
        if build_dir is None:
            sys.exit(1)

        self.params = self._collect_params(parsed_args, build_dir)
        self.params['resolved_features'] = resolution.features
        self._log_summary(build_dir, parsed_args)
        self._generate_compile_conf(
            args=parsed_args,
            build_dir=build_dir,
            parser_template=parser_template,
        )

    def _validate_environment(self):
        if not self.configure.is_oebuild_dir():
            logger.error('Your current directory had not finished init')
            sys.exit(-1)

        oebuild_config = self.configure.parse_oebuild_config()
        yocto_dir = self.configure.source_yocto_dir()
        self.yocto_dir = yocto_dir
        if not self.check_support_oebuild(yocto_dir):
            logger.error(
                'yocto-meta-openeuler does not contain valid oebuild metadata '
                'Update .oebuild/config and re-run `oebuild update`.'
            )
            sys.exit(-1)

        try:
            feat_root_dir = (
                oebuild_config.feat_root_dir.strip()
                if isinstance(oebuild_config.feat_root_dir, str)
                else ''
            )
            if not feat_root_dir:
                feat_root_dir = 'nightly-features'
            nightly_dir = pathlib.Path(
                yocto_dir, '.oebuild', feat_root_dir
            )
            self.feature_registry = FeatureRegistry(nightly_dir)
        except NeoFeatureError as err:
            logger.error(str(err))
            sys.exit(-1)

    def _run_menuconfig(self, args):
        platform_dir = pathlib.Path(self.yocto_dir, '.oebuild', 'platform')
        config_path = pathlib.Path(os.getcwd(), '.config')
        if config_path.exists():
            try:
                config_path.unlink()
            except OSError:
                pass
        try:
            generator = NeoMenuconfigGenerator(
                registry=self.feature_registry,
                platform_dir=platform_dir,
                default_platform=args.platform,
            )
        except ValueError as exc:
            logger.error('Menuconfig setup failed: %s', exc)
            sys.exit(-1)
        try:
            return generator.run_menuconfig()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logger.error('Menuconfig failed: %s', exc)
            sys.exit(-1)

    def _collect_params(self, args, build_dir):
        return {
            'platform': args.platform,
            'build_dir': build_dir,
            'build_in': args.build_in,
            'directory': args.directory,
            'nativesdk_dir': args.nativesdk_dir or None,
            'toolchain_dir': args.toolchain_dir or None,
            'llvm_toolchain_dir': args.llvm_toolchain_dir or None,
            'sstate_mirrors': args.sstate_mirrors,
            'sstate_dir': args.sstate_dir,
            'tmp_dir': args.tmp_dir,
            'cache_src_dir': args.cache_src_dir,
            'datetime': args.datetime,
            'no_fetch': args.no_fetch,
            'no_layer': args.no_layer,
            'auto_build': args.auto_build,
            'nativesdk': args.nativesdk,
            'gcc': args.gcc,
            'gcc_name': args.gcc_name or [],
            'llvm': args.llvm,
            'llvm_lib': args.llvm_lib,
            'resolved_features': [],
        }

    def _log_summary(self, build_dir, args):
        summary = textwrap.dedent(f"""
            neo-generate pre-flight completed.
            Build directory: {build_dir}
            Platform: {args.platform}
            Build mode: {args.build_in}
            Auto build: {'enabled' if args.auto_build else 'disabled'}

            Feature selection will follow nightly-features state resolution next.
        """)
        logger.info(summary)

    def _prepare_parser_template(self, args, resolved_features):
        parser_template = ParseTemplate(yocto_dir=self.yocto_dir)
        yocto_oebuild_dir = pathlib.Path(self.yocto_dir, '.oebuild')
        self._add_platform_template(
            args=args,
            yocto_oebuild_dir=yocto_oebuild_dir,
            parser_template=parser_template,
        )
        self._add_nightly_features_template(
            parser_template, resolved_features
        )
        return parser_template

    def _resolve_features(self, platform, requested):
        resolver = FeatureResolver(self.feature_registry, platform)
        return resolver.resolve(requested)

    def _generate_compile_conf(
        self, args, build_dir, parser_template
    ):
        compile_yaml_path = pathlib.Path(build_dir, 'compile.yaml')
        if compile_yaml_path.exists():
            compile_yaml_path.unlink()

        docker_image = get_docker_image(
            yocto_dir=self.configure.source_yocto_dir(),
            docker_tag='',
            configure=self.configure,
        )

        param = parser_template.get_default_generate_compile_conf_param()
        param['nativesdk_dir'] = self.params.get('nativesdk_dir')
        param['toolchain_dir'] = self.params.get('toolchain_dir')
        param['llvm_toolchain_dir'] = self.params.get('llvm_toolchain_dir')
        param['build_in'] = args.build_in
        param['sstate_mirrors'] = self.params.get('sstate_mirrors')
        param['sstate_dir'] = self.params.get('sstate_dir')
        param['tmp_dir'] = self.params.get('tmp_dir')
        param['datetime'] = args.datetime
        param['no_fetch'] = self.params.get('no_fetch')
        param['no_layer'] = self.params.get('no_layer')
        param['docker_image'] = docker_image
        param['src_dir'] = self.configure.source_dir()
        param['compile_dir'] = build_dir
        param['cache_src_dir'] = self.params.get('cache_src_dir')
        oebuild_util.write_yaml(
            compile_yaml_path,
            parser_template.generate_compile_conf(param),
        )

        self._print_generate(build_dir)

    def _add_platform_template(
        self, args, yocto_oebuild_dir, parser_template: ParseTemplate
    ):
        platform_path = pathlib.Path(yocto_oebuild_dir, 'platform')
        platform_files = [f.name for f in platform_path.iterdir() if f.is_file()]
        target_file = args.platform + '.yaml'
        if target_file in platform_files:
            try:
                platform_file = platform_path / target_file
                parser_template.add_template(platform_file)
            except BaseParseTemplate as b_t:
                raise b_t
        else:
            logger.error(
                'Invalid platform. Run `oebuild neo-generate -l` to list supported platforms.'
            )
            sys.exit(-1)


    def _add_nightly_features_template(
        self, parser_template: ParseTemplate, resolved_features
    ):
        for feature in resolved_features:
            local_conf = self._local_conf_from_lines(
                feature.config.local_conf
            )
            parser_template.feature_template.append(
                FeatureTemplate(
                    feature_name=LiteralScalarString(feature.full_id),
                    repos=(
                        feature.config.repos if feature.config.repos else None
                    ),
                    layers=(
                        feature.config.layers
                        if feature.config.layers
                        else None
                    ),
                    local_conf=None
                    if local_conf is None
                    else LiteralScalarString(local_conf),
                    support=feature.machines or [],
                )
            )

    @staticmethod
    def _local_conf_from_lines(lines):
        if not lines:
            return None
        return '\n'.join(lines)

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
            logger.error('Build path must be in oebuild workspace')
            return None

        if build_dir.exists():
            logger.warning('the build directory %s already exists', build_dir)
            while not args.yes:
                in_res = input(f"""
    Overwrite {build_dir.name}? This will replace generated assets and delete conf/
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

    @staticmethod
    def _get_terminal_width():
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 80

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

    def list_info(self):
        self._list_platform()
        self._list_feature()

    def _list_platform(self):
        logger.info(
            '\n================= Available Platforms ================='
        )
        yocto_oebuild_dir = pathlib.Path(
            self.configure.source_yocto_dir(), '.oebuild'
        )
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

        terminal_width = self._get_terminal_width()

        table = self._build_table(
            ['Feature Name', 'Supported Arch'],
            terminal_width,
            title='Available Features',
        )

        def display_feature(feature, depth=0):
            indent = '  ' * depth

            if depth == 0:
                display_name = feature.full_id
            else:
                display_name = f"{indent}- {feature.full_id}"

            support = (
                'all'
                if not feature.machines
                else ', '.join(feature.machines)
            )

            table.add_row([display_name, support])

        features_by_category = {}
        for feature in self.feature_registry.list_features():
            category = feature.category
            if category not in features_by_category:
                features_by_category[category] = []
            features_by_category[category].append(feature)

        # For each category, display features in hierarchical order
        for category in sorted(features_by_category.keys()):
            category_features = features_by_category[category]

            root_feature = None
            other_features = []

            for feature in category_features:
                if feature.category == feature.leaf_id and not feature.parent_full_id:
                    root_feature = feature
                else:
                    other_features.append(feature)

            if root_feature:
                display_feature(root_feature, depth=0)

                for feature in sorted(other_features, key=lambda f: f.full_id):
                    display_feature(feature, depth=1)
            else:
                table.add_row([category, ''])
                for feature in sorted(other_features, key=lambda f: f.full_id):
                    display_feature(feature, depth=1)

        print(table)
        logger.info(
            """* 'Supported Arch' defaults to 'all' if not specified in the feature's .yaml file."""
        )

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

    def check_support_oebuild(self, yocto_dir):
        return pathlib.Path(yocto_dir, '.oebuild').exists()
