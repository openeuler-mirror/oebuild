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
import logging
import sys

from oebuild.command import OebuildCommand
from oebuild.app.plugins.deploy.com_target import ComTarget

logger = logging.getLogger()


class DeployTarget(OebuildCommand):
    '''
    we use package in a
    '''

    help_msg = 'deploy software on line'
    description = textwrap.dedent('''\
            Deploys a recipe's build output (i.e. the output of the do_install task)
            to a live target machine over ssh. By default, any existing files will be
            preserved instead of being overwritten and will be restored if you run
            devtool undeploy-target. Note: this only deploys the recipe itself and
            not any runtime dependencies, so it is assumed that those have been
            installed on the target beforehand.
            ''')

    def __init__(self) -> None:
        super().__init__('{}', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''
oebuild deploy-target [-h] [-c] [-s] [-n] [-p] [--no-check-space] [-e SSH_EXEC]
[-P PORT] [-I KEY] [-S | --no-strip] recipename target
''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        if '-h' in unknown or '--help' in unknown:
            self.print_help_msg()
            sys.exit(0)
        str_args = ' '.join(unknown)
        com_target = ComTarget()
        com_target.exec(str_args=str_args, fun="deploy-target")

    def print_help_msg(self, ):
        print("""
usage: oebuild deploy-target [-h] [-c] [-s] [-n] [-p] [--no-check-space] [-e SSH_EXEC]
              [-P PORT] [-I KEY] [-S | --no-strip] recipename target

Deploys a recipe's build output (i.e. the output of the do_install task) to a live target
              machine over ssh. By default, any existing files will be preserved instead of being
overwritten and will be restored if you run devtool undeploy-target. Note: this only deploys
              the recipe itself and not any runtime dependencies, so it is assumed that those have
been installed on the target beforehand.

arguments:
  recipename            Recipe to deploy
  target                Live target machine running an ssh server: user@hostname[:destdir]

options:
  -h, --help            show this help message and exit
  -c, --no-host-check   Disable ssh host key checking
  -s, --show-status     Show progress/status output
  -n, --dry-run         List files to be deployed only
  -p, --no-preserve     Do not preserve existing files
  --no-check-space      Do not check for available space before deploying
  -e SSH_EXEC, --ssh-exec SSH_EXEC
                        Executable to use in place of ssh
  -P PORT, --port PORT  Specify port to use for connection to the target
  -I KEY, --key KEY     Specify ssh private key for connection to the target
  -S, --strip           Strip executables prior to deploying (default: False).
              The default value of this option can be controlled by
              setting the strip option in the [Deploy]
                        section to True or False.
  --no-strip            Do not strip executables prior to deploy
""")


class UnDeployTarget(OebuildCommand):
    '''
    we use package in a
    '''

    help_msg = 'undeploy software on line'
    description = textwrap.dedent('''\
            Un-deploys recipe output files previously deployed to a live target machine
                                  by devtool deploy-target.
            ''')

    def __init__(self) -> None:
        super().__init__('{}', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''
oebuild undeploy-target [-h] [-c] [-s] [-a] [-n] [-e SSH_EXEC]
[-P PORT] [-I KEY] [recipename] target
''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        if '-h' in unknown or '--help' in unknown:
            self.print_help_msg()
            sys.exit(0)
        str_args = ' '.join(unknown)
        com_target = ComTarget()
        com_target.exec(str_args=str_args, fun="undeploy-target")

    def print_help_msg(self):
        print("""

usage: oebuild undeploy-target [-h] [-c] [-s] [-a] [-n] [-e SSH_EXEC]
              [-P PORT] [-I KEY] [recipename] target

Un-deploys recipe output files previously deployed to a live target machine
              by devtool deploy-target.

arguments:
  recipename            Recipe to undeploy (if not using -a/--all)
  target                Live target machine running an ssh server: user@hostname

options:
  -h, --help            show this help message and exit
  -c, --no-host-check   Disable ssh host key checking
  -s, --show-status     Show progress/status output
  -a, --all             Undeploy all recipes deployed on the target
  -n, --dry-run         List files to be undeployed only
  -e SSH_EXEC, --ssh-exec SSH_EXEC
                        Executable to use in place of ssh
  -P PORT, --port PORT  Specify port to use for connection to the target
  -I KEY, --key KEY     Specify ssh private key for connection to the target
""")
