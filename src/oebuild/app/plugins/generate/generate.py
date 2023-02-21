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

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.configure import Configure
from oebuild.parse_template import BaseParseTemplate, ParseTemplate, BUILD_IN_DOCKER, BUILD_IN_HOST
from oebuild.my_log import MyLog as log

class Generate(OebuildCommand):
    '''
    compile.yaml is generated according to different command parameters by generate
    '''
    def __init__(self):
        self.configure = Configure()
        self.nativesdk_dir = None
        self.toolchain_dir = None
        self.sstate_cache = None
        super().__init__(
            'generate',
            'help to mkdir build directory and generate compile.yaml',
            textwrap.dedent('''\
            compile.yaml is generated according to different command parameters by generate
'''
        ))

    def do_add_parser(self, parser_adder):
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [-p platform] [-f features] [-t toolchain_dir] [-d build_directory] [-l list] [-b_in build_in]
''')

        parser.add_argument('-l', dest='list', choices=['platform', 'feature'],
            help='''
            with platform will list support archs, with feature will list support features
            '''
        )

        parser.add_argument('-p', dest='platform', default="aarch64-std",
            help='''
            this param is for arch, for example aarch4-std, aarch64-pro and so on
            '''
        )

        parser.add_argument('-s', dest='sstate_cache',
            help='''
            this param is for arch, for example aarch4-std, aarch64-pro and so on
            '''
        )

        parser.add_argument('-f', dest='features', action='append',
            help='''
            this param is feature, it's a reuse command
            '''
        )

        parser.add_argument('-d', dest='directory',
            help='''
            this param is build directory, the default is same to platform
            '''
        )

        parser.add_argument('-t', dest='toolchain_dir', default = '',
            help='''
            this param is for external toolchain dir, if you want use your own toolchain
            '''
        )

        parser.add_argument('-n', dest='nativesdk_dir', default = '',
            help='''
            this param is for external nativesdk dir, the param will be useful when you want to build in host
            '''
        )

        parser.add_argument('-b_in', dest='build_in', choices=[BUILD_IN_DOCKER, BUILD_IN_HOST],
                            default = BUILD_IN_DOCKER, help='''
            This parameter marks the mode at build time, and is built in the container by docker
            '''
        )

        return parser

    def do_run(self, args: argparse.Namespace, unknown = None):
        args = args.parse_args(unknown)

        if not self.configure.is_oebuild_dir():
            log.err('your current directory had not finishd init')
            sys.exit(-1)

        build_in = BUILD_IN_DOCKER
        if args.build_in == BUILD_IN_HOST:
            try:
                self._check_param_in_host(args=args)
            except ValueError as v_e:
                log.err(str(v_e))
                return
            self.nativesdk_dir = args.nativesdk_dir
            build_in = BUILD_IN_HOST

        if args.toolchain_dir != '':
            self.toolchain_dir = args.toolchain_dir

        if args.sstate_cache is not None:
            self.sstate_cache = args.sstate_cache

        yocto_dir = self.configure.source_yocto_dir()
        if not self.check_support_oebuild(yocto_dir):
            log.err('Currently, yocto-meta-openeuler does not support oebuild, \
                    please modify .oebuild/config and re-execute `oebuild update`')
            return

        if args.list is not None:
            self.list_info(args=args)
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
            log.err(str(b_t))
            return
        except ValueError as v_e:
            log.err(str(v_e))
            return
        else:
            pass

        try:
            self._add_features_template(args=args,
            yocto_oebuild_dir=yocto_oebuild_dir,
            parser_template=parser_template)
        except BaseParseTemplate as b_t:
            log.err(str(b_t))
            self._list_feature()
            return
        except ValueError as v_e:
            log.err(str(v_e))
            return
        else:
            pass

        if os.path.exists(os.path.join(build_dir,'compile.yaml')):
            os.remove(os.path.join(build_dir,'compile.yaml'))

        out_dir = pathlib.Path(os.path.join(build_dir,'compile.yaml'))
        oebuild_util.write_yaml(out_dir, parser_template.generate_template(
            nativesdk_dir= self.nativesdk_dir,
            toolchain_dir= self.toolchain_dir,
            build_in=build_in,
            sstate_cache= self.sstate_cache
            ))

        log.info("=============================================")
        log.successful("generate compile.yaml successful")
        log.info("please run `oebuild bitbake` in directory next")
        format_dir = f'''

cd {build_dir}

'''
        log.info(format_dir)
        log.info("=============================================")

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
            raise ValueError("wrong platform, please run\
                    `oebuild generate -l platform` to view support platform")

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
                    raise ValueError("wrong platform, please run \
                            `oebuild generate -l feature` to view support feature")

    def _init_build_dir(self, args):
        if not os.path.exists(self.configure.build_dir()):
            os.makedirs(self.configure.build_dir())

        if args.directory is None or args.directory == '':
            build_dir = os.path.join(self.configure.build_dir(), args.platform)
        else:
            build_dir = os.path.join(self.configure.build_dir(), args.directory)

        if not os.path.abspath(build_dir).startswith(self.configure.build_dir()):
            log.err("build path must in oebuild workspace")
            return None

        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        return build_dir

    def list_info(self, args):
        '''
        print platform list or feature list
        '''
        if args.list == 'platform':
            self._list_platform()
            return
        if args.list == 'feature':
            self._list_feature()
            return

    def _list_platform(self):
        log.info("=============================================")
        yocto_dir = self.configure.source_yocto_dir()
        yocto_oebuild_dir = os.path.join(yocto_dir, ".oebuild")
        list_platform = os.listdir(os.path.join(yocto_oebuild_dir, 'platform'))
        log.info("the platform list is:")
        for platform in list_platform:
            if platform.endswith('.yml'):
                log.info(platform.rstrip('.yml'))
            if platform.endswith('.yaml'):
                log.info(platform.rstrip('.yaml'))

    def _list_feature(self,):
        log.info("=============================================")
        yocto_dir = self.configure.source_yocto_dir()
        yocto_oebuild_dir = os.path.join(yocto_dir, ".oebuild")
        list_feature = os.listdir(os.path.join(yocto_oebuild_dir, 'features'))
        log.info("the feature list is:")
        for feature in list_feature:
            if feature.endswith('.yml'):
                log.info(feature.rstrip('.yaml'))
            if feature.endswith('.yaml'):
                log.info(feature.rstrip('.yaml'))
            feat = oebuild_util.read_yaml(pathlib.Path(os.path.join(yocto_oebuild_dir,
                                                                    'features',
                                                                    feature)))
            if "support" in feat:
                log.info(f"    support arch: {feat.get('support')}")
            else:
                log.info("    support arch: all")

    def check_support_oebuild(self, yocto_dir):
        '''
        Determine if OeBuild is supported by checking if .oebuild
        exists in the yocto-meta-openeuler directory
        '''
        return os.path.exists(os.path.join(yocto_dir, '.oebuild'))
