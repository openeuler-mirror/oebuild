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

import oebuild.const as oebuild_const


def parsers(parser):
    '''
    xxx
    '''
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
        this param is for external gcc toolchain dir, if you want use your own toolchain
        ''')

    parser.add_argument('-lt',
                        '--llvm_toolchain_dir',
                        dest='llvm_toolchain_dir',
                        default='',
                        help='''
        this param is for external llvm toolchain dir, if you want use your own toolchain
        ''')

    parser.add_argument('-n',
                        '--nativesdk_dir',
                        dest='nativesdk_dir',
                        default='',
                        help='''
        this param is for external nativesdk dir, the param will be useful when you
        want to build in host
        ''')

    parser.add_argument('-dt',
                        '--datetime',
                        dest="datetime",
                        help='''
        this param is add DATETIME to local.conf, the value format is 20231212010101
        ''')

    parser.add_argument('-ny',
                        '--no_layer',
                        dest="no_layer",
                        action="store_true",
                        help='''
        this param will not fetch layer repo when startting bitbake environment
        ''')

    parser.add_argument('-nf',
                        '--no_fetch',
                        dest="no_fetch",
                        action="store_true",
                        help='''
        this param is set openeuler_fetch in local.conf, the default value is enable, if
        set -nf, the OPENEULER_FETCH will set to 'disable'
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

    parser.add_argument('--gcc',
                        dest='gcc',
                        action="store_true",
                        help='''
                        This parameter is used to indicate whether to build an toolchain
                        ''')

    parser.add_argument('--gcc_name',
                        dest='gcc_name',
                        action='append',
                        help='''
                        This parameter is used to gcc toolchain config name
                        ''')
    parser.add_argument('--llvm',
                        dest='llvm',
                        action="store_true",
                        help='''
                        This parameter is used to indicate whether to build an toolchain
                        ''')

    parser.add_argument('--llvm_lib',
                        dest='llvm_lib',
                        help='''
                        This parameter is used to indicate whether to build an toolchain
                        ''')

    parser.add_argument('--auto_build',
                        dest='auto_build',
                        action="store_true",
                        help='''
                                This parameter is used for nativesdk and toolchain build
                        ''')

    return parser
