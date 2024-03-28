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
import copy
import os
import pathlib
import re
import subprocess
import textwrap
import sys

from oebuild.command import OebuildCommand
import oebuild.util as oebuild_util
from oebuild.configure import Configure
from oebuild.app.main import OebuildApp
from oebuild.m_log import logger


class MPlugin(OebuildCommand):
    """
    this class is used to manager oebuild plugin, you can install, list, enable and so on to
    manager it, the plugin must be in oebuild plugin standard, when you install the plugin you
    developped, you can use it through oebuild.
    """

    help_msg = 'Update the basic environment required for the build'
    description = textwrap.dedent('''
            This is a plugin management function that supports users to customize plugin and
            add them to the oebuild for use. plugin only affect locally installed oebuilds,
            and supports viewing personal existing plugin and uninstalling plugin.
            ''')

    def __init__(self):
        self.configure = Configure()
        self.oebuild_plugin_commands = [
            'install', 'list', 'enable', 'disable', 'remove'
        ]
        self.oebuild_plugin_path = os.path.expanduser(
            '~') + '/.local/oebuild_plugins/'
        self.oebuild_plugin_yaml_path = pathlib.Path(self.oebuild_plugin_path,
                                                     'append_plugins.yaml')
        self.oebuild_plugin_repository = pathlib.Path(self.oebuild_plugin_path,
                                                      'appends')
        plugin_dir = pathlib.Path(oebuild_util.get_plugins_yaml_path())
        self.command_ext = OebuildApp().get_command_ext(
            oebuild_util.read_yaml(plugin_dir)['plugins'])
        super().__init__('mplugin', self.help_msg, self.description)

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        """
            Registers a parser for this command, and returns it.
        The parser object is stored in a ``parser`` attribute.
        :param parser_adder: The return value of a call to
            ``argparse.ArgumentParser.add_subparsers()``
        Args:
            parser_adder:

        Returns:

        """
        parser = self._parser(parser_adder,
                              usage='''

  %(prog)s [install list remove enable/disable][command]
  install: -f  file_path  -n plugin_name
  install: -d  plugin_dir_path -m major_file  -n plugin_name
  list:
  enable/disable: enable/disable -n plugin_name
  remove: -n plugin_name
''')
        parser.add_argument('-f',
                            '--file',
                            dest='file',
                            help='''
                        this param is python file
                        ''')

        parser.add_argument('-n',
                            '--plugin_name',
                            dest='plugin_name',
                            help='''
                                this param is plugin name
                                ''')

        parser.add_argument('-d',
                            '--dir_path',
                            dest='dir_path',
                            help='''
                                        this param is dir path
                                        ''')

        parser.add_argument('-m',
                            '--major',
                            dest='major',
                            help='''
                                                        this param is major class
                                                        ''')

        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        """
            Subclasses must implement; called to run the command.
        :param args: ``argparse.Namespace`` of parsed arguments
        :param unknown: If ``accepts_unknown_args`` is true, a
            sequence of un-parsed argument strings.
        Args:
            args:
            unknown:

        Returns:

        """
        command = ''
        if not unknown:
            unknown = ['-h']
        elif unknown[0] not in self.oebuild_plugin_commands or (
                len(set(unknown[1:]).intersection({'-f', '-n', '-d'})) == 0
                and unknown[0] != 'list'):
            unknown = ['-h']
        else:
            command = unknown[0]
            unknown = unknown[1:]

        if self.pre_parse_help(args, unknown):
            sys.exit(0)
        args = args.parse_args(unknown)

        if not os.path.exists(self.oebuild_plugin_yaml_path.absolute()):
            if not os.path.exists(
                    os.path.dirname(self.oebuild_plugin_yaml_path.absolute())):
                os.makedirs(
                    os.path.dirname(self.oebuild_plugin_yaml_path.absolute()))
            os.mknod(self.oebuild_plugin_yaml_path)
        plugin_dict = oebuild_util.read_yaml(self.oebuild_plugin_yaml_path)
        plugin_dict_old = copy.deepcopy(plugin_dict)

        if command == 'install':
            self._install_param_check(args=args, plugin_dict=plugin_dict)
            if args.file and os.path.exists(args.file):
                self.install_plugin(
                    {
                        'file': args.file,
                        'plugin_name': args.plugin_name,
                        'command': command
                    }, plugin_dict, plugin_dict_old)
                sys.exit(0)
            elif args.dir_path and os.path.exists(args.dir_path):
                file = str(
                    pathlib.Path(args.dir_path,
                                 args.major.split('/')[-1]))
                self._install_for_dir_check(args=args, file=file)
                self.install_plugin(
                    {
                        'file': file,
                        'plugin_name': args.plugin_name,
                        'command': command,
                        'dir_path': args.dir_path
                    }, plugin_dict, plugin_dict_old)
                sys.exit(0)
            logger.error("the %s not exist, please check the plugin file path",
                         args.file)
            sys.exit(1)
        elif command == 'list':
            self.list_plugin(plugin_dict=plugin_dict)
        elif command in ['enable', 'disable']:
            self.enable_disable_plugin(command=command,
                                       plugin_dict=plugin_dict,
                                       args=args)
        elif command == 'remove':
            self.remove_plugin(args.plugin_name)

    def list_plugin(self, plugin_dict):
        '''
        list plugin infomation with format like 'plugin_name status plugin_path'
        '''
        if plugin_dict and 'plugins' in plugin_dict:
            print("""# oebuild plugin:\n#""")
            print(f'{"name".ljust(20)}{"status".ljust(20)}{"path"}')
            for plugin_data in plugin_dict['plugins']:
                print(f'{str(plugin_data["name"]).ljust(20)}'
                      f'{str(plugin_data["status"]).ljust(20)}'
                      f'{str(plugin_data["path"])}')
        else:
            logger.error('No plugin has been created yet')
            sys.exit(-1)

    def enable_disable_plugin(self, command, plugin_dict, args):
        '''
        enable plugin or disable plugin
        '''
        if plugin_dict and 'plugins' in plugin_dict:
            for plugin_data in plugin_dict['plugins']:
                if plugin_data['name'] == args.plugin_name:
                    plugin_data['status'] = command
                    oebuild_util.write_yaml(self.oebuild_plugin_yaml_path,
                                            plugin_dict)
                    print('change success')
            logger.error('the plugin %s does not exist', args.plugin_name)
            sys.exit(-1)
        else:
            logger.error('No plugin has been created yet')
            sys.exit(-1)

    def _install_for_dir_check(self, args, file):
        if not args.major:
            logger.error(" Please specify the major file ")
            sys.exit(-1)
        if not os.path.exists(file):
            logger.error("the %s not exist, please check the plugin file path",
                         file)
            sys.exit(-1)

    def _install_param_check(self, args, plugin_dict):
        if not args.plugin_name:
            logger.error(
                'Please enter the correct command:  Missing -n parameter ')
            sys.exit(-1)

        if args.plugin_name == 'mplugin':
            logger.error(' This command does not allow overwrite ')
            sys.exit(-1)

        if plugin_dict is not None:
            append_command_ext = OebuildApp().get_command_ext(
                plugin_dict['plugins'])
        else:
            append_command_ext = {}

        if args.plugin_name in self.command_ext.keys() \
                or args.plugin_name in append_command_ext.keys():
            while True:
                user_input = input(
                    'Do you want to overwrite the existing '
                    f'plugin ({args.plugin_name}) in oebuild(Y/N)')
                if user_input.lower() == 'y':
                    break
                if user_input.lower() == 'n':
                    sys.exit(0)

    def create_or_update_plugin_yaml(self, plugin_name, class_name,
                                     python_file_name, plugin_dict):
        """

        Args:
            plugin_name:
            class_name:
            python_file_name:
            plugin_dict:

        Returns:

        """
        old_plugin_path = ''

        if plugin_dict and 'plugins' in plugin_dict:
            plugin_list, old_plugin_path = self.input_or_update_dict(
                {
                    'plugin_name': plugin_name,
                    'class_name': class_name,
                    'python_file_name': python_file_name,
                    'plugin_status': "enable"
                }, plugin_dict['plugins'])
            plugin_dict['plugins'] = plugin_list
            oebuild_util.write_yaml(self.oebuild_plugin_yaml_path, plugin_dict)
            return old_plugin_path

        plugin_dict = {
            'plugins': [{
                'name': plugin_name,
                'class': class_name,
                'path': python_file_name,
                'status': 'enable'
            }]
        }
        oebuild_util.write_yaml(self.oebuild_plugin_yaml_path, plugin_dict)
        return old_plugin_path

    def input_or_update_dict(self, plugin_obj, plugin_list):
        """
            Modify or insert environmental data
        Args:
            plugin_name:  plugin Name
            class_name:  python class name
            python_file_name:  python file name
            plugin_status:  plugin status
            plugin_list: plugin List

        Returns:

        """
        insert_flag = True
        old_plugin_path = ''
        for plugin_data in plugin_list:
            if 'name' not in plugin_data:
                logger.error('plugin_name not exits')
                return plugin_list, old_plugin_path
            if plugin_data['name'] == plugin_obj['plugin_name']:
                plugin_data['class'] = plugin_obj['class_name']
                old_plugin_path = os.path.abspath(
                    os.path.dirname(plugin_data['path']))
                plugin_data['path'] = plugin_obj['python_file_name']
                plugin_data['status'] = plugin_obj['plugin_status']
                insert_flag = False
        if insert_flag:
            plugin_list.append({
                'name': plugin_obj['plugin_name'],
                'class': plugin_obj['class_name'],
                'path': plugin_obj['python_file_name'],
                'status': plugin_obj['plugin_status']
            })
        return plugin_list, old_plugin_path

    def query_method(self, file_path):
        """
            Check if the corresponding method is included in the Python file
        Args:
            file_path:

        Returns:

        """
        with open(file_path, 'r', encoding='UTF-8') as file:
            def_name = ""
            class_name = ""
            for file_line in file:
                if file_line.startswith('def') or file_line.startswith(
                        '    def'):
                    if re.search(r'(?<=def)\s+\w+', file_line):
                        def_name += re.search(r'(?<=def)\s+\w+',
                                              file_line).group()
                        def_name += ","
                if file_line.startswith('class') or file_line.startswith(
                        '    class'):
                    if re.search(r'((?<=class)\s+\w+\(OebuildCommand\))', file_line) and \
                            not class_name:
                        class_name = re.search(r'(?<=class)\s+\w+',
                                               file_line).group().strip()
        return def_name, class_name

    def remove_plugin(self, plugin_name):
        """
            remove oebuild plugin
        Args:
            plugin_name:
        Returns:

        """
        plugin_dict = oebuild_util.read_yaml(self.oebuild_plugin_yaml_path)
        if plugin_dict and 'plugins' in plugin_dict:
            for plugin_data in plugin_dict['plugins']:
                if plugin_data['name'] == plugin_name:
                    plugin_dict['plugins'].remove(plugin_data)
                    delete_path = os.path.abspath(
                        pathlib.Path(os.path.dirname(plugin_data['path']),
                                     '..'))
                    subprocess.check_output(f'rm -rf {delete_path}',
                                            shell=True)
                    oebuild_util.write_yaml(self.oebuild_plugin_yaml_path,
                                            plugin_dict)
                    print('delete success')
                    return
            logger.error('the plugin %s does not exist', plugin_name)
        else:
            logger.error('No plugin has been created yet')

    def install_plugin(self, install_plugin_object, plugin_dict,
                       plugin_dict_old):
        """
            install plugin the install_plugin_object container follow item
            file: xxx
            plugin_name: xxx
            command: xxx
            dir_path: xxx
        Args:
            install_plugin_object:
            plugin_dict:
            plugin_dict_old:

        Returns:

        """
        def_name, class_name = self.query_method(install_plugin_object['file'])
        if not ('do_run' in def_name and 'do_add_parser' in def_name):
            logger.error('do_run or do_add_parser method does not exist')
            sys.exit(-1)
        if not class_name:
            logger.error('class not extends OebuildCommand')
            sys.exit(-1)
        file_split_info = install_plugin_object['file'].split('/')
        if len(file_split_info) > 1:
            file_name = pathlib.Path(file_split_info[-2], file_split_info[-1])
            file_name_dir = file_split_info[-2]
        else:
            file_name = pathlib.Path('plugin_info', file_split_info[-1])
            file_name_dir = ""
        file_path = pathlib.Path(self.oebuild_plugin_repository,
                                 install_plugin_object['plugin_name'],
                                 file_name)

        old_plugin_path = self.create_or_update_plugin_yaml(
            install_plugin_object['plugin_name'], class_name, str(file_path),
            plugin_dict)

        if old_plugin_path != '':
            subprocess.check_output(
                f'mv {old_plugin_path} ~/.local/{old_plugin_path.split("/")[-1]}',
                shell=True)

        file_dir_path = pathlib.Path(
            self.oebuild_plugin_repository,
            install_plugin_object['plugin_name']).absolute()
        if not os.path.exists(pathlib.Path(file_dir_path, 'plugin_info')):
            os.makedirs(pathlib.Path(file_dir_path, 'plugin_info'))

        if file_name_dir and not os.path.exists(pathlib.Path(file_dir_path, file_name_dir)):
            os.makedirs(pathlib.Path(file_dir_path, file_name_dir))

        if 'dir_path' not in install_plugin_object:
            subprocess.check_output(
                f"cp {install_plugin_object['file']} {file_path}", shell=True)
        else:
            subprocess.check_output(
                f"cp -r {install_plugin_object['dir_path']} {file_dir_path}",
                shell=True)

        command_info = subprocess.run(
            ['oebuild', f"{install_plugin_object['plugin_name']}", '-h'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False)

        if command_info.returncode != 0:
            logger.error("\nError Message!!!!!!!!!!!!! \n\n %s ",
                         command_info.stderr)
            logger.error(
                'Installation failed. There is an issue with your code. '
                'Please check and fix it before reinstalling.')

            oebuild_util.write_yaml(self.oebuild_plugin_yaml_path,
                                    plugin_dict_old)
            subprocess.check_output(f'rm -rf {file_dir_path}', shell=True)

            if old_plugin_path != '':
                os.makedirs(file_dir_path)

                subprocess.check_output(
                    f'cp -r ~/.local/{old_plugin_path.split("/")[-1]} {file_dir_path}',
                    shell=True)
                subprocess.check_output(
                    f'rm -rf ~/.local/{old_plugin_path.split("/")[-1]}',
                    shell=True)
            sys.exit(-1)

        if old_plugin_path != '':
            subprocess.check_output(
                f'rm -rf ~/.local/{old_plugin_path.split("/")[-1]}',
                shell=True)

        print(
            f"{install_plugin_object['command'].title()} plugin successfully \n"
            f'{"name".ljust(20)}{"status".ljust(20)}{"path"} \n'
            f"{install_plugin_object['plugin_name'].ljust(20)}{'enable'.ljust(20)}{file_path}"
        )
