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
import sys
import os
import pathlib

import git
from git.repo import Repo

from oebuild.command import OebuildCommand
from oebuild.configure import Configure
import oebuild.util as oebuild_util
from oebuild.m_log import logger
from oebuild.ogit import OGit


class Manifest(OebuildCommand):
    '''
    manifest provides the manifest function of generating dependent
    source repositories in the build working directory, and can restore
    relevant source repositories based on the manifest file
    '''

    help_msg = 'generate manifest from oebuild workspace'
    description = textwrap.dedent('''\
            manifest provides the manifest function of generating dependent
            source repositories in the build working directory, and can restore
            relevant source repositories based on the manifest file, also you can
            download single repo, for zlib example:

                oebuild manifest download zlib
            ''')

    def __init__(self):
        self.configure = Configure()
        self.manifest_command = ['download', 'create']
        super().__init__('manifest', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''

  %(prog)s [create / download] [repo] [-f MANIFEST_DIR]

''')

        parser.add_argument('-f',
                            '--manifest_dir',
                            dest='manifest_dir',
                            help='''
            specify a manifest path to perform the create or restore operation
            ''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        if not self.configure.is_oebuild_dir():
            logger.error('Your current directory had not finished init')
            sys.exit(-1)

        subrepo = ""
        command = ""
        if not (unknown and unknown[0] in self.manifest_command):
            unknown = ['-h']
        else:
            command = unknown[0]
            unknown = unknown[1:]
            if len(unknown) > 0 and not unknown[0].startswith("-"):
                subrepo = unknown[0]
                unknown = unknown[1:]

        # perpare parse help command
        if self.pre_parse_help(args, unknown):
            sys.exit(0)

        args = args.parse_args(unknown)
        manifest_dir = args.manifest_dir if args.manifest_dir else \
            (self.configure.source_yocto_dir() + '/.oebuild/manifest.yaml')
        if command == 'create':
            self._create_manifest(manifest_dir)
        elif command == 'download':
            if not os.path.exists(manifest_dir):
                logger.error('The path is invalid, please check the path')
                sys.exit(1)
            self._restore_manifest(manifest_dir, subrepo)

    def _create_manifest(self, manifest_dir):
        src_list = os.listdir(self.configure.source_dir())
        manifest_list = {}
        for index, repo_dir in enumerate(src_list):
            local_dir = os.path.join(self.configure.source_dir(), repo_dir)
            try:
                repo = Repo(local_dir)
                remote_url = repo.remote("upstream").url
                version = repo.head.commit.hexsha
            except git.GitError:
                continue
            except ValueError:
                continue

            manifest_list[repo_dir] = {
                'remote_url': remote_url,
                'version': version
            }
            print("\r", end="")
            progress = int((index + 1) / len(src_list) * 100)
            print(f"Expose progress: {progress}%: ",
                  "▋" * (progress // 2),
                  end="")
            sys.stdout.flush()
        print()
        manifest_list = dict(sorted(manifest_list.items(), key=lambda s: s[0]))
        oebuild_util.write_yaml(yaml_path=pathlib.Path(manifest_dir),
                                data={'manifest_list': manifest_list})
        self._add_manifest_banner(manifest_dir=os.path.abspath(manifest_dir))

        print(
            f"expose successful, the directory is {os.path.abspath(manifest_dir)}"
        )

    def _add_manifest_banner(self, manifest_dir):
        oebuild_conf_dir = os.path.join(oebuild_util.get_base_oebuild(),
                                        'app/conf')
        manifest_banner_dir = os.path.join(oebuild_conf_dir, 'manifest_banner')

        with open(manifest_banner_dir, 'r', encoding='utf-8') as r_f:
            banner = r_f.read()
        with open(manifest_dir, 'r', encoding='utf-8') as r_f:
            manifest_str = r_f.read()

        manifest_content = banner + '\n' + manifest_str
        with open(manifest_dir, 'w', encoding='utf-8') as w_f:
            w_f.write(manifest_content)

    def _restore_manifest(self, manifest_dir, subrepo):
        manifest_data = oebuild_util.read_yaml(pathlib.Path(manifest_dir))
        manifest_list = manifest_data.get('manifest_list', {})
        src_dir = self.configure.source_dir()
        if subrepo != "":
            if subrepo in manifest_list:
                self._download_repo(src_dir, subrepo, manifest_list[subrepo])
                return
            logger.error("%s not in manifest.yaml", subrepo)
            sys.exit(-1)
        final_res = []
        for key, value in manifest_list.items():
            if not self._download_repo(src_dir, key, value):
                final_res.append(key)
        if len(final_res) > 0:
            print("")
            print("the list package download failed:")
            for item in final_res:
                remote_url = manifest_list[item]['remote_url']
                version = manifest_list[item]['version']
                print(f"{item}: {remote_url}, {version}")
            print("you can manually download them!!!")
        else:
            print("""
    all package download successful!!!""")

    def _download_repo(self, src_dir, key, value):
        logger.info("====================download %s=====================",
                    key)
        repo_git = OGit(os.path.join(src_dir, key),
                        remote_url=value['remote_url'],
                        branch=None)
        if repo_git.check_out_version(version=value['version']):
            logger.info(
                "====================download %s successful=====================",
                key)
            return True
        logger.warning(
            "====================download %s failed=====================", key)
        return False
