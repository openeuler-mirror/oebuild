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
from queue import Queue
import threading

import docker
from docker.errors import ImageNotFound, NotFound
from docker.models.containers import Container
from reprint import output

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

    def pull_image(self, image_name : str):
        '''
        pull image like command 'docker pull'
        args:
            image_name (str): docker image name, if no tag, the default tag is latest
        '''
        repository,tag = self._get_image_name_tag(image_name=image_name)

        self._docker.images.pull(repository=repository, tag=tag)

    def pull_image_with_progress(self, image_name: str):
        '''
        pull docker image and print progress
        '''
        def flush_print(in_q:Queue):
            with output(output_type='dict') as output_lines:
                while True:
                    data = in_q.get()
                    if data == "over":
                        break
                    if 'foot_msg' in data:
                        output_lines.append(data['foot_msg'])
                        continue
                    output_lines[data['id']] = data['message']

        client = docker.APIClient()
        repository,tag = self._get_image_name_tag(image_name=image_name)
        p_q = Queue()
        f_p = threading.Thread(target=flush_print, args=(p_q,))
        f_p.start()
        resp = client.pull(repository=repository, tag=tag, stream=True, decode=True)
        for line in resp:
            if 'id' in line:
                if "progressDetail" in line:
                    tmp_data = {
                        'id': line['id'],
                        'message': f"{line['status']}"
                    }
                    if line['progressDetail'] != {}:
                        tmp_data['message'] = f"{tmp_data['message']} {line['progress']}"
                    p_q.put(tmp_data)
            else:
                if 'status' in line:
                    if 'status' in line:
                        tmp_data = {'foot_msg': line['status']}
                        p_q.put(tmp_data)

        p_q.put("over")

    def _get_image_name_tag(self, image_name: str):
        repository = image_name.split(':')[0]
        tag = "latest"
        if len(image_name.split(':'))==2:
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
    def delete_container(container: Container):
        '''
        rm a container which not running like command 'docker rm'
        args:
            container (Container): container object
        '''
        container.remove()

    @staticmethod
    def start_container(container: Container):
        '''
        start a container like command 'docker start'
        args:
            container (Container): container object
        '''
        container.start()

    @staticmethod
    def is_container_running(container : Container):
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
        if os.path.exists(path = path_dir):
            pw_tarstream = BytesIO()
            with tarfile.TarFile(fileobj=pw_tarstream, mode='w') as pw_tar:
                pw_tar.add(name = path_dir, arcname=os.path.basename(path_dir))
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
        return container.put_archive(path = to_path,data = tar)

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
        with tarfile.open(fileobj = pw_tarstream) as tar:
            res = tar.extractall(path = dst_path)
        return res is None

    def container_exec_command(self,
                               container: Container,
                               command: str or list,
                               user: str = '',
                               work_space = None,
                               stream = True):
        '''
        run command like 'docker run exec', other param
        will be default and just use a little params
        returns a data stream
        '''
        res = container.exec_run(
            cmd=command,
            user=user,
            workdir=work_space,
            stderr=True,
            stdout=True,
            stream=stream
        )

        return res

    def container_run_command(self,
                              image:str,
                              command: str,
                              user: str,
                              volumes: list,
                              work_space: str):
        '''
        run command like 'docker run' with tty being true
        to keep container alive and then run command in
        docker container
        '''
        container = self._docker.containers.run(
            image=image,
            command="bash",
            volumes=volumes,
            detach=True,
            tty=True
        )
        if isinstance(container, Container):
            res = self.container_exec_command(
            container=container,
            command=command,
            user=user,
            work_space=work_space)
            return container, res.output
        else:
            raise ValueError("docker start faild")

    def container_run_simple(self, image:str, volumes: list, network="host", is_priv=False):
        '''
        it's just create a tty docker container to do some thing next
        '''
        container = self._docker.containers.run(
            image=image,
            command="bash",
            volumes=volumes,
            network_mode=network,
            detach=True,
            tty=True,
            privileged=is_priv
        )
        container_name = str(container.attrs.get('Name')).lstrip("/")
        container.rename(f"oebuild_{container_name}")
        return container

    def container_exec_with_tty(self,
                                container: Container,
                                user:str,
                                work_space: str):
        '''
        run docker container with tty, you can has a tty terminal
        '''
        cli = container.exec_run(
            cmd="bash",
            stdout=True,
            stderr=True,
            stdin=True,
            user=user,
            workdir=work_space,
            tty=True,
            socket=True,
            ).output

        return cli.fileno()
