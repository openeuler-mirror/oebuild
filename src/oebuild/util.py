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

import pathlib
import os
import time
import random
import getpass

from ruamel.yaml import YAML
from docker.errors import DockerException

from oebuild.docker_proxy import DockerProxy
from oebuild.version import __version__

CONFIG_YAML = 'config.yaml'
UPGRADE_YAML = 'upgrade.yaml'
COMPILE_YAML = 'compile.yaml.sample'
BASH_END_FLAG = "  ###!!!###"

def read_yaml(yaml_dir : pathlib.Path):
    '''
    read yaml file and parse it to object
    '''
    if not os.path.exists(yaml_dir.absolute()):
        raise ValueError(f"yaml_dir can not find in :{yaml_dir.absolute()}")

    try:
        with open(yaml_dir.absolute(), 'r', encoding='utf-8') as r_f:
            yaml = YAML()
            data = yaml.load(r_f.read())
            return data
    except Exception as e_p:
        raise e_p


def write_yaml(yaml_dir : pathlib.Path, data):
    '''
    write data to yaml file
    '''
    if not os.path.exists(yaml_dir.absolute()):
        if not os.path.exists(os.path.dirname(yaml_dir.absolute())):
            os.makedirs(os.path.dirname(yaml_dir.absolute()))
        os.mknod(yaml_dir)

    with open(yaml_dir, 'w', encoding='utf-8') as w_f:
        yaml = YAML()
        yaml.dump(data, w_f)

def get_git_repo_name(remote_url : str):
    '''
    return repo name
    '''
    url = remote_url.replace(".git","")
    return os.path.basename(url)

def add_git_suffix(remote : str):
    '''
    add .git suffix to remote if needed
    '''
    if remote.endswith(".git"):
        return remote

    return remote + ".git"

def get_base_oebuild():
    '''
    return oebuild base dir
    '''
    return os.path.abspath(os.path.dirname(__file__))

def get_config_yaml_dir():
    '''
    return config yaml dir
    '''
    return os.path.join(get_base_oebuild(), 'app/conf', CONFIG_YAML)

def get_compile_yaml_dir():
    '''
    return compile.yaml.sample yaml dir
    '''
    return os.path.join(get_base_oebuild(), 'app/conf', COMPILE_YAML)

def get_upgrade_yaml_dir():
    '''
    return upgrade yaml dir
    '''
    return os.path.join(get_base_oebuild(), 'app/conf', UPGRADE_YAML)

def generate_random_str(randomlength=16):
    '''
    generate a random string by length
    '''
    random_str = ''
    base_str = 'ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789'
    length = len(base_str) - 1
    for _ in range(randomlength):
        random_str += base_str[random.randint(0, length)]
    return random_str

def get_time_stamp():
    '''
    get current timestamp
    '''
    return time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))

def get_oebuild_version():
    '''
    return oebuild version
    '''
    return __version__

def check_docker():
    '''
    check docker had be installed or not
    '''
    try:
        DockerProxy()
    except DockerException as exc:
        raise ValueError(f'''
please install docker first, and run follow commands in root:
1, groupadd docker
2, usermod -a -G docker {getpass.getuser()}
3, systemctl daemon-reload && systemctl restart docker
4, chmod o+rw /var/run/docker.sock
''') from exc

def get_instance(factory):
    '''
    Instantiate a class
    '''
    return factory()

def restore_bashrc_content(old_content):
    '''
    restore .bashrc
    '''
    new_content = ''
    for line in old_content.split('\n'):
        line: str = line
        if line.endswith(BASH_END_FLAG) or line.replace(" ", '') == '':
            continue
        new_content = new_content + line + '\n'
    return new_content

def init_bashrc_content(old_content, init_command: list):
    '''
    init bashrc
    '''
    new_content = restore_bashrc_content(old_content=old_content)

    for command in init_command:
        new_content = new_content + command + BASH_END_FLAG + '\n'

    return new_content

def add_bashrc(content: str, line: str):
    '''
    add command line to bashrc
    '''
    if not content.endswith('\n'):
        content = content + '\n'
    content = content + line + BASH_END_FLAG + '\n'

    return content
