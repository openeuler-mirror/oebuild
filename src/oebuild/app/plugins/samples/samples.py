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
import sys
import textwrap
import os

from oebuild.command import OebuildCommand
from oebuild.configure import Configure
from oebuild.m_log import logger


class Samples(OebuildCommand):
    '''
    The 'samples' command is used to efficiently manage the existing compilation templates in
    yocto-meta-openeuler. These templates are located in the yocto-meta-openeuler/.oebuild/samples
    directory, and this command allows for rapid implementation of the build process.
    '''

    help_msg = "manage the yocto-meta-openeuler's samples compile files"
    description = textwrap.dedent('''
    The 'samples' command is used to efficiently manage the existing compilation templates in
    yocto-meta-openeuler. These templates are located in the yocto-meta-openeuler/.oebuild/samples
    directory, and this command allows for rapid implementation of the build process.
    ''')

    def __init__(self):
        self.configure = Configure()
        super().__init__('samples', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''
  %(prog)s [list]
''')

        # Secondary command
        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        # perpare parse help command
        if '-h' in unknown:
            unknown = ['-h']
            self.pre_parse_help(args, unknown)
            sys.exit(0)
        if not self.configure.is_oebuild_dir():
            logger.error('Your current directory had not finished init')
            sys.exit(-1)
        samples = self._get_samples()
        if len(unknown) > 0 and 'list' == unknown[0]:
            for key, value in samples.items():
                print(f"{key}: {value}")
            return

        self.do_exec(samples=samples)

    def _get_samples(self):
        list_samples = []

        def recursive_listdir(path):
            files = os.listdir(path)
            for file in files:
                file_path = os.path.join(path, file)
                if os.path.isfile(file_path):
                    list_samples.append(file_path)
                if os.path.isdir(file_path):
                    recursive_listdir(file_path)
        recursive_listdir(self.configure.yocto_samples_dir())

        res = {}
        for index, sample in enumerate(list_samples):
            res[str(index + 1)] = sample.replace(self.configure.yocto_samples_dir(), "").lstrip("/")
        return res

    def do_exec(self, samples: dict):
        """
        we let the user select the sample num for next build task
        """
        for key, value in samples.items():
            print(f"{key}: {value}")
        select_num = ""
        while True:
            res = input("please select what you want build, enter the num, q for exit: ")
            if res not in samples and res != "q":
                logger.info("please enter the valid num or q")
                continue
            if res == "q":
                sys.exit(0)
            select_num = res
            break
        sample = samples[select_num]
        sample_path = os.path.join(self.configure.yocto_samples_dir(), sample)

        os.system(f"oebuild {sample_path}")
