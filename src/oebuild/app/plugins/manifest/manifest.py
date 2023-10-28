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
import multiprocessing
from queue import Queue
from threading import Thread
from concurrent.futures import ThreadPoolExecutor,wait,ALL_COMPLETED

import git
from git.repo import Repo
from git.exc import GitCommandError

from oebuild.command import OebuildCommand
from oebuild.configure import Configure
import oebuild.util as oebuild_util
from oebuild.m_log import logger

class Manifest(OebuildCommand):
    '''
    manifest provides the manifest function of generating dependent
    source repositories in the build working directory, and can restore
    relevant source repositories based on the manifest file
    '''

    def __init__(self):
        self.configure = Configure()
        super().__init__(
            'manifest',
            'generate manifest from oebuild workspace',
            textwrap.dedent('''\
    manifest provides the manifest function of generating dependent
    source repositories in the build working directory, and can restore
    relevant source repositories based on the manifest file
'''
        ))

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(
            parser_adder,
            usage='''

  %(prog)s [-c CREATE] [-r recover] [-m_dir MANIFEST_DIR]

''')

        parser.add_argument('-c',
                            '--create', 
                            dest = "is_create",
                            action = "store_true",
                            help='''
            create manifest from oebuild workspace src directory
            ''')

        parser.add_argument('-r',
                            '--recover', 
                            dest = "is_recover",
                            action = "store_true",
                            help='''
            restore repo version to oebuild workspace src directory from a manifest
            ''')

        parser.add_argument('-m_dir',
                            '--manifest_dir',
                            dest='manifest_dir',
                            help='''
            specify a manifest path to perform the create or restore operation
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

        if args.is_create:
            self._create_manifest(args.manifest_dir)
        elif args.is_recover:
            self._restore_manifest(args.manifest_dir)

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
            print(f"Expose progress: {progress}%: ", "▋" * (progress // 2), end="")
            sys.stdout.flush()
        print()
        manifest_list = dict(sorted(manifest_list.items(),key=lambda s:s[0]))
        oebuild_util.write_yaml(
            yaml_dir=pathlib.Path(manifest_dir),
            data={'manifest_list': manifest_list})
        self._add_manifest_banner(manifest_dir = os.path.abspath(manifest_dir))

        print(f"expose successful, the directory is {os.path.abspath(manifest_dir)}")

    def _add_manifest_banner(self, manifest_dir):
        oebuild_conf_dir = os.path.join(oebuild_util.get_base_oebuild(), 'app/conf')
        manifest_banner_dir = os.path.join(oebuild_conf_dir, 'manifest_banner')

        with open(manifest_banner_dir, 'r', encoding='utf-8') as r_f:
            banner = r_f.read()
        with open(manifest_dir, 'r', encoding='utf-8') as r_f:
            manifest_str = r_f.read()

        manifest_content = banner + '\n' + manifest_str
        with open(manifest_dir, 'w', encoding='utf-8') as w_f:
            w_f.write(manifest_content)

    def _restore_manifest(self, manifest_dir):
        manifest_data = oebuild_util.read_yaml(pathlib.Path(manifest_dir))
        manifest_list = manifest_data.get('manifest_list', {})

        def print_progress(in_q: Queue, length: int):
            index = 0
            while True:
                data = in_q.get()
                if data == "over":
                    break
                index = index + 1
                print("\r", end="")
                progress = int((index + 1) / length * 100)
                print(f"restore progress: {progress}%: ", "▋" * (progress // 2), end="")
                sys.stdout.flush()
            print()
            print(f"restore successful, the source directory is {os.path.abspath(src_dir)}")

        q_e = Queue()
        dserver = Thread(target=print_progress, args=(q_e, len(manifest_list)))
        dserver.start()

        cpu_count = multiprocessing.cpu_count()
        with ThreadPoolExecutor(max_workers = cpu_count) as t_p:
            src_dir = self.configure.source_dir()
            all_task = []
            for key, value in manifest_list.items():
                all_task.append(t_p.submit(self._download_repo, q_e, src_dir, key, value))
            wait(all_task, return_when = ALL_COMPLETED)
        q_e.put("over")

    def _download_repo(self, out_q: Queue ,src_dir, key, value):
        repo_dir = os.path.join(src_dir, key)
        repo = Repo.init(repo_dir)
        remote = None
        for item in repo.remotes:
            if value['remote_url'] == item.url:
                remote = item
            else:
                continue
        if remote is None:
            remote_name = "upstream"
            remote = git.Remote.add(repo = repo, name = remote_name, url = value['remote_url'])
        try:
            repo.git.checkout(value['version'])
        except GitCommandError:
            remote.fetch(value['version'], depth = 1)
            repo.git.checkout(value['version'])
        out_q.put('ok')
