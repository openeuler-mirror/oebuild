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

import os
from io import BytesIO
import tarfile
import subprocess
import sys
from typing import List
import re

import docker
from docker.errors import ImageNotFound, NotFound
from docker.models.containers import Container

from oebuild.m_log import logger


class DockerProxy:
    '''
    a object just be wrapper again to run docker command easily
    '''

    def __init__(self):
        self._docker = docker.from_env()

    def is_image_exists(self, image_name):
        '''
        determize if image exist
        args:
            image_name (str): docker image name
        '''
        try:
            self._docker.images.get(image_name)
            return True
        except ImageNotFound:
            return False

    def is_container_exists(self, container_id):
        '''
        determize if container exists
        args:
            container_id (str): docker container short_id or id
        '''
        try:
            self._docker.containers.get(container_id=container_id)
            return True
        except NotFound:
            return False

    def pull_image(self, image_name: str):
        '''
        pull image like command 'docker pull'
        args:
            image_name (str): docker image name, if no tag, the default tag is latest
        '''
        repository, tag = self._get_image_name_tag(image_name=image_name)

        self._docker.images.pull(repository=repository, tag=tag)

    def pull_image_with_progress(self, image_name: str):
        '''
        pull docker image and print progress
        '''
        os.system(f"docker pull {image_name}")

    def _get_image_name_tag(self, image_name: str):
        repository = image_name.split(':')[0]
        tag = "latest"
        if len(image_name.split(':')) == 2:
            tag = image_name.split(':')[1]
        return repository, tag

    def get_image(self, image_name):
        '''
        get a docker image object
        args:
            image_name (str): docker image name
        '''
        return self._docker.images.get(image_name)

    def get_container(self, container_id):
        '''
        get a docker container object
        args:
            container_id (str): docker container short_id or id
        '''
        return self._docker.containers.get(container_id=container_id)

    def get_all_container(self):
        '''
        get all container like command 'docker ps -a'
        args:
            None
        '''
        return self._docker.containers.list(all=True)

    @staticmethod
    def stop_container(container: Container):
        '''
        stop a container if running like command 'docker stop'
        args:
            container (Container): container object
        '''
        container.stop()

    @staticmethod
    def delete_container(container: Container, is_force: bool = False):
        '''
        rm a container which not running like command 'docker rm'
        args:
            container (Container): container object
        '''
        container.remove(force=is_force)

    @staticmethod
    def start_container(container: Container):
        '''
        start a container like command 'docker start'
        args:
            container (Container): container object
        '''
        container.start()

    @staticmethod
    def is_container_running(container: Container):
        '''
        determize if a container in running state
        args:
            container (Container): container object
        '''
        if container.status == "running":
            return True
        return False

    @staticmethod
    def add_tar(path_dir):
        '''
        add a path to tar
        args:
            path_dir (str): the directory that will added to a tar
        '''
        if os.path.exists(path=path_dir):
            pw_tarstream = BytesIO()
            with tarfile.TarFile(fileobj=pw_tarstream, mode='w') as pw_tar:
                pw_tar.add(name=path_dir, arcname=os.path.basename(path_dir))
            pw_tarstream.seek(0)
            return pw_tarstream
        return None

    def copy_to_container(self, container: Container, source_path, to_path):
        '''
        copy file that tar before to container
        args:
            container (Container): docker container object
            source_path (str): which copied file path
            to_path (str): will copy to docker container path
        '''
        tar = self.add_tar(source_path)
        return container.put_archive(path=to_path, data=tar)

    def copy_from_container(self, container: Container, from_path, dst_path):
        '''
        copy file from container to local
        args:
            container (Container): docker container object
            from_path (str): which copied file path
            dst_path (str): will copy from docker container path
        '''
        pw_tarstream = BytesIO()
        bits, _ = container.get_archive(from_path)
        for trunk in bits:
            pw_tarstream.write(trunk)
        pw_tarstream.seek(0)
        with tarfile.open(fileobj=pw_tarstream) as tar:
            res = tar.extractall(path=dst_path)
        return res is None

    def container_exec_command(self, container: Container,
                               command,
                               user: str = '',
                               params=None):
        '''
        run command like 'docker run exec', other param
        will be default and just use a little params
        returns a data stream
        '''
        if params is None:
            params = {}
        res = container.exec_run(
            cmd=command,
            user=user,
            workdir=None if "work_space" not in params else params['work_space'],
            stderr=True,
            stdout=True,
            stream=True if "stream" not in params else params['stream'],
            demux=False if "demux" not in params else params['demux']
        )

        return res

    def create_container(self,
                         image: str,
                         parameters: str,
                         volumes: List,
                         command: str) -> Container:
        '''
        create a new container
        '''
        run_command = f"docker run {parameters}"
        for volume in volumes:
            run_command = f"{run_command} -v {volume}"
        run_command = f"{run_command} {image} {command}"
        res = subprocess.run(run_command, shell=True, capture_output=True, check=True, text=True)
        if res.returncode != 0:
            logger.error(res.stderr.strip())
            sys.exit(res.returncode)
        container_id = res.stdout.strip()
        return self.get_container(container_id=container_id)

    def check_change_ugid(self, container: Container, container_user):
        '''
        the function is to check and change container user uid and gid to same with host's,
        together also alter directory pointed uid and gid
        '''
        res = self.container_exec_command(
            container=container,
            user='root',
            command=f"id {container_user}",
            params={
                "work_space": f"/home/{container_user}",
                "stream": False
            })

        if res.exit_code != 0:
            raise ValueError("check docker user id faild")

        res_cont = res.output.decode()

        cuids = res_cont.split(' ')
        # get uid from container in default user
        pattern = re.compile(r'(?<=uid=)\d{1,}(?=\(' + container_user + r'\))')
        match_uid = pattern.search(cuids[0])
        if match_uid:
            cuid = match_uid.group()
        else:
            raise ValueError(f"can not get container {container_user} uid")
        # get gid from container in default user
        pattern = re.compile(r'(?<=gid=)\d{1,}(?=\(' + container_user + r'\))')
        match_gid = pattern.search(cuids[1])
        if match_gid:
            cgid = match_gid.group()
        else:
            raise ValueError(f"can not get container {container_user} gid")

        # judge host uid and gid are same with container uid and gid
        # if not same and change container uid and gid equal to host's uid and gid
        if os.getuid() != cuid:
            self.change_container_uid(
                container=container,
                uid=os.getuid(),
                container_user=container_user)
        if os.getgid() != cgid:
            self.change_container_gid(
                container=container,
                gid=os.getgid(),
                container_user=container_user)

    def change_container_uid(self, container: Container, uid: int, container_user):
        '''
        alter container user pointed uid
        '''
        self.container_exec_command(
            container=container,
            user='root',
            command=f"usermod -u {uid} {container_user}",
            params={
                "work_space": f"/home/{container_user}",
                "stream": False
            })

    def change_container_gid(self, container: Container, gid: int, container_user):
        '''
        alter container pointed gid
        '''
        self.container_exec_command(
            container=container,
            user='root',
            command=f"groupmod -g {gid} {container_user}",
            params={
                "work_space": f"/home/{container_user}",
                "stream": False
            })
