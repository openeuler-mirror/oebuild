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

import git

from oebuild.my_log import MyLog as log

(
    BEGIN,
    END,
    COUNTING,
    COMPRESSING,
    WRITING,
    RECEIVING,
    RESOLVING,
    FINDING_SOURCES,
    CHECKING_OUT,
) = [1 << x for x in range(9)]

class OGit:
    '''
    owner git to print progress in clone action
    '''
    def __init__(self, repo_dir, remote_url, branch) -> None:
        self._repo_dir = repo_dir
        self._remote_url = remote_url
        self._branch = branch
        self._last_code = 0
        try:
            _, self._screen_width = os.popen('stty size', 'r').read().split()
        except ValueError as v_e:
            log.warning(str(v_e))

    @property
    def repo_dir(self):
        '''
        return repo dir
        '''
        return self._repo_dir

    @property
    def remote_url(self):
        '''
        return remote url
        '''
        return self._remote_url

    @property
    def branch(self):
        '''
        return branch
        '''
        return self.branch

    def clone_or_pull_repo(self, ):
        '''
        clone or pull git repo
        '''
        if os.path.exists(self._repo_dir):
            try:
                repo = git.Repo(self._repo_dir)
                remote = repo.remote()
                if repo.head.is_detached:
                    repo.git.checkout(self._branch)
                if repo.active_branch.name != self._branch:
                    log.info(f"Fetching into '{self._repo_dir}'...")
                    remote.fetch(progress=self.clone_process)
                    repo.git.checkout(self._branch)
                log.info(f"Pulling into '{self._repo_dir}'...")
                remote.pull(progress=self.clone_process)
            except Exception as e_p:
                raise e_p
        else:
            try:
                log.info(f"Cloning into '{self._repo_dir}'...")
                git.Repo.clone_from(
                    url=self._remote_url,
                    to_path=self._repo_dir,
                    branch=self._branch,
                    progress=self.clone_process)
            except Exception as e_p:
                raise e_p

    def clone_process(self, op_code, cur_count, max_count, message):
        '''
        print clone or pull progress
        '''
        if op_code % 2 == BEGIN:
            print("")
            return
        op_title = ''
        pmsg = ''
        if op_code == COUNTING:
            op_title = "remote: Counting objects"
            pmsg = f"{op_title}: {int(cur_count/max_count*100)}% \
                ({cur_count}/{max_count}), {message}"

        elif op_code == COMPRESSING:
            op_title = "remote: Compressing objects"
            pmsg = f"{op_title}: {int(cur_count/max_count*100)}% \
                ({cur_count}/{max_count}), {message}"

        elif op_code == RECEIVING:
            op_title = "Receiving objects"
            pmsg = f"{op_title}: {int(cur_count/max_count*100)}% \
                ({cur_count}/{max_count}), {message}"

        elif op_code == RESOLVING:
            op_title = "Resolving deltas"
            pmsg = f"{op_title}: {int(cur_count/max_count*100)}% ({cur_count}/{max_count})"
        else:
            return

        pmsg = "\r" + pmsg
        if hasattr(self, '_screen_width'):
            pmsg = pmsg.ljust(int(self._screen_width), ' ')
        print(pmsg, end='', flush=True)

    @staticmethod
    def get_repo_info(repo_dir: str):
        '''
        return git repo info: remote_url, branch
        '''
        try:
            repo = git.Repo(repo_dir)
            remote_url = repo.remote().url
            branch = repo.active_branch.name
            return remote_url, branch
        except TypeError:
            return remote_url, ''
        except git.GitError:
            return "",""
        except ValueError:
            return "",""
