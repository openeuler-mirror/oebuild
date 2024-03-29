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
import fcntl
import pty
import re
import struct
import subprocess
from subprocess import SubprocessError
import sys
import termios
import textwrap
import os
import pathlib

from oebuild.command import OebuildCommand
from oebuild.configure import Configure
import oebuild.util as oebuild_util
from oebuild.m_log import logger


class Menv(OebuildCommand):
    '''
    the class is used to manager sdk environment, the sdk environment refers to openEuler
    Embedded image sdk, you can use the sdk to develop some apps that can run in openEuler
    Embedded system you built. for example, the sdk with qt image can be used to develop apps
    runned in qt system, the sdk with ros image can be used to develop apps runned in ros system
    '''

    help_msg = 'Update the basic environment required for the build'
    description = textwrap.dedent('''
            This is an environment management function that allows you to configure the environment
            through SDK files or unzipped setup files, and you can view, delete, and activate the
            corresponding environment. These operations will not have any impact on
            your current machine
            ''')

    def __init__(self):
        self.configure = Configure()
        self.oebuild_env_path = os.path.expanduser(
            '~') + '/.local/oebuild_env/'
        self.oebuild_env_yaml_path = pathlib.Path(
            os.path.join(self.oebuild_env_path, 'oebuild_env.yaml'))
        self.oebuild_env_command = ['list', 'create', 'activate', 'remove']
        super().__init__('menv', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        parser = self._parser(parser_adder,
                              usage='''
  %(prog)s [create list remove activate][command]
  create: [-d -f]  Create an environment  -n env_name
  list:  View existing environment
  remove: -n  Delete specified environment
  activate: -n  Activate specified environment
''')

        parser.add_argument('-d',
                            '--directory',
                            dest='directory',
                            help='''
                this param is build directory
                ''')

        parser.add_argument('-f',
                            '--file',
                            dest='file',
                            help='''
                this param is build file
                ''')

        parser.add_argument('-n',
                            '--env_name',
                            dest='env_name',
                            help='''
                        this param is env_name
                        ''')

        # Secondary command
        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        # perpare parse help command
        if unknown[0] not in self.oebuild_env_command or (
                len(set(unknown[1:]).intersection({'-d', '-f', '-n'})) == 0
                and unknown[0] != 'list'):
            unknown = ['-h']
        else:
            command = unknown[0]
            unknown = unknown[1:]

        if self.pre_parse_help(args, unknown):
            sys.exit(0)
        args = args.parse_args(unknown)

        if command == 'create':
            if not args.env_name:
                print('''
Please enter the correct command: oebuild menv create [-d -f] Create an environment -n env_name
                      ''')
                sys.exit(1)
            self.create_environment(args=args)
        elif command == 'activate':
            # Activate Environment
            if args.env_name:
                self.activate_environment(args.env_name)
                sys.exit(0)
            print(
                'Please enter the correct command: oebuild menv activate -n env_name'
            )
            sys.exit(1)

        elif command == 'list':
            env_dict = oebuild_util.read_yaml(self.oebuild_env_yaml_path)
            if env_dict and 'env_config' in env_dict:
                self.list_environment(env_dict)
                sys.exit(0)
            else:
                print('No environment has been created yet')
                sys.exit(-1)

        # delete environment
        elif command == 'remove':
            if args.env_name:
                self.delete_environment(args.env_name)
                sys.exit(0)
            print(
                'Please enter the correct command: oebuild menv remove -n env_name'
            )
            sys.exit(1)

    def create_environment(self, args):
        '''
        create environment file in ~/.local/oebuild_env/ and do something in next step
        '''
        # Check if the file path exists
        if args.directory and os.path.isdir(args.directory):
            setup_file_path = os.path.abspath(args.directory)
            sdk_name = args.env_name if args.env_name else args.directory.split(
                '/')[-1]
            self.create_or_update_env_yaml(sdk_name, args.directory)
            print(
                f' Created Environment successfully \n {sdk_name.ljust(30)}{setup_file_path}'
            )
            sys.exit(0)

        #  Creating an environment
        if args.file and os.path.exists(args.file):
            sdk_name = args.env_name if args.env_name else (args.file.split(
                '/')[-1].replace('.sh', '') if args.file else None)
            setup_file_path = self.oebuild_env_path + sdk_name
            self.create_or_update_env_yaml(sdk_name, setup_file_path)
            self.execute_sdk_file(args.file, setup_file_path)
            print(
                f' Created Environment successfully \n {sdk_name.ljust(30)}{setup_file_path}'
            )
            sys.exit(0)

        print('The path is invalid, please check the path ')
        sys.exit(-1)

    # pylint: disable=R0914
    def execute_setup_directory(self, setup_file_path, env_name):
        """
            Prepare the environment using the parsed SDK folder provided
        Args:
            setup_file_path: Resolve completed sdk folder path
            env_name: environment name

        Returns: results of execution

        """
        file_list = str(os.listdir(setup_file_path))
        # number of setup_file
        setup_num = len(re.findall('environment-setup', file_list))
        # Determine the number of setup_files
        if setup_num == 1:
            try:
                file_path = os.path.join(
                    setup_file_path,
                    re.search('environment-setup.*?(?=\')', file_list).group())
                absolute_file_path = os.path.abspath(file_path)
                # Splice Execution Command
                shell_command = '. ' + absolute_file_path

                print(shell_command)
                print('setup_file matching successful')
                subprocess.check_output('cp ~/.bashrc ~/.bashrc_back',
                                        shell=True)
                # Obtain the current terminal height and length
                terminal_info = fcntl.ioctl(sys.stdout.fileno(),
                                            termios.TIOCGWINSZ, "1234")
                rows_and_cloumns = struct.unpack('HH', terminal_info)
                rows_command = f'stty rows {rows_and_cloumns[0]} columns {rows_and_cloumns[1]}'
                subprocess.check_output(
                    rf"sed -i '$a\{rows_command}' ~/.bashrc", shell=True)
                # Add the command to execute the setup file in the .bashrc file in the
                # working directory
                subprocess.check_output(
                    rf"sed -i '$a\{shell_command}' ~/.bashrc", shell=True)
                # Replace Console Prompt
                subprocess.check_output(
                    rf"sed -i 's/\$ /({env_name})>>>>> /g' ~/.bashrc",
                    shell=True)
                subprocess.check_output(
                    r"sed -i '$a\mv ~/.bashrc_back ~/.bashrc -f' ~/.bashrc",
                    shell=True)
                # Add prompt words
                separator = "===================================================="
                prompt_one = "Your environment is ready"
                prompt_two = "Please proceed with the subsequent operations here"
                wrap = '\\n###!###\\n'
                prompt_words = separator + wrap + prompt_one + wrap + prompt_two + wrap + separator
                subprocess.check_output(
                    rf'''sed -i '$a\echo "{prompt_words}"' ~/.bashrc''',
                    shell=True)
                pty.spawn("/bin/bash")
            except SubprocessError as s_e:
                print('Please provide the valid folder path')
                logger.error(str(s_e))
                sys.exit(-1)
            return True
        if setup_num == 0:
            print('not setup_file, please check your directory')
            return False
        print('Illegal path, only one environment setup file allowed')
        return False

    def execute_sdk_file(self, sdk_file, setup_file_path):
        """
            Execute the SDK file, produce the setup folder, and then execute the corresponding
            method for the setup file
        Args:
            sdk_file: SDK file path
            setup_file_path: setup file path

        Returns: results of execution

        """
        try:
            if os.path.isdir(setup_file_path):
                print(
                    f'The setup file folder already exists.path is {setup_file_path}'
                )
            else:
                print('Extracting sdk...............')
                subprocess.check_output(
                    f'sh {sdk_file} -d {setup_file_path} -y', shell=True)
                subprocess.check_output(f'chmod -R 755 {setup_file_path}',
                                        shell=True)
        except SubprocessError as s_e:
            print('Please provide the valid folder path')
            logger.error(str(s_e))
            sys.exit(1)

    def create_or_update_env_yaml(self, env_name, setup_file_path):
        """

        Args:
            env_name:
            setup_file_path:

        Returns:

        """
        if not os.path.exists(self.oebuild_env_yaml_path.absolute()):
            if not os.path.exists(
                    os.path.dirname(self.oebuild_env_yaml_path.absolute())):
                os.makedirs(
                    os.path.dirname(self.oebuild_env_yaml_path.absolute()))
            os.mknod(self.oebuild_env_yaml_path)
        env_dict = oebuild_util.read_yaml(self.oebuild_env_yaml_path)
        if env_dict and 'env_config' in env_dict:
            env_list = self.input_or_update_dict(env_name, setup_file_path,
                                                 env_dict['env_config'])
            env_dict['env_config'] = env_list
            oebuild_util.write_yaml(self.oebuild_env_yaml_path, env_dict)
            return

        env_dict = {
            'env_config': [{
                'env_name': env_name,
                'env_value': setup_file_path
            }]
        }
        oebuild_util.write_yaml(self.oebuild_env_yaml_path, env_dict)

    def input_or_update_dict(self, env_name, env_value, env_list):
        """
            Modify or insert environmental data
        Args:
            env_name:  Environment Name
            env_value:  Setup file file path
            env_list: Environment

        Returns: new Environment

        """
        insert_flag = True
        for env_data in env_list:
            if 'env_name' not in env_data:
                print('env_name not exits')
                sys.exit(-1)
            if env_data['env_name'] == env_name:
                while True:
                    user_input = input("""
Do you want to overwrite the path of the original environment configuration(Y/N)
                    """)
                    if user_input.lower() == 'y':
                        env_data['env_value'] = env_value
                        break
                    if user_input.lower() == 'n':
                        return []
                insert_flag = False
        if insert_flag:
            env_list.append({'env_name': env_name, 'env_value': env_value})
        return env_list

    def activate_environment(self, env_name):
        '''
        activate the sdk environment, is means that environment shell will be sourced, and
        open a new pty, so that developer can compile app with sdk environment
        '''
        env_dict = oebuild_util.read_yaml(self.oebuild_env_yaml_path)
        if env_dict and 'env_config' in env_dict:
            setup_file_path = self._get_environment(env_name, env_dict)
            if setup_file_path:
                self.execute_setup_directory(setup_file_path, env_name)
            print('The environment does not exist')
            sys.exit(-1)

    def list_environment(self, env_dict):
        """
            View the environment, if env_ If name exists, it is necessary to find the corresponding
            environment's setup file
        Args:
            env_name: environment name
            env_dict: environment yaml
        Returns:

        """
        print("""# oebuild environment:\n#""")
        for env_data in env_dict['env_config']:
            print(env_data['env_name'].ljust(30) + env_data['env_value'])

    def _get_environment(self, env_name, env_dict):
        for env_data in env_dict['env_config']:
            if env_name and env_data['env_name'] == env_name:
                return env_data['env_value']
        return None

    def delete_environment(self, env_name):
        """
            delete your environment
        Args:
            env_name: The environment you want to delete

        Returns:

        """
        env_dict = oebuild_util.read_yaml(self.oebuild_env_yaml_path)
        if env_dict and 'env_config' in env_dict:
            env_list = []
            for env_data in env_dict['env_config']:

                if env_data['env_name'] != env_name:
                    env_list.append(env_data)
                elif '/.local/oebuild_env/' in env_data['env_value']:
                    try:
                        subprocess.check_output(
                            f'rm -rf {env_data["env_value"]}', shell=True)
                    except SubprocessError as s_e:
                        print('Fail deleted')
                        logger.error(str(s_e))
                        sys.exit(-1)

            if len(env_list) == len(env_dict['env_config']):
                logger.error(
                    'The environment does not exist, please check the input')
                sys.exit(-1)
            env_dict['env_config'] = env_list
        oebuild_util.write_yaml(self.oebuild_env_yaml_path, env_dict)
        print('Successfully deleted')
