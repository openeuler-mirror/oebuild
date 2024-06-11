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
from git.repo import Repo
from git import GitCommandError, RemoteProgress

from oebuild.m_log import logger


class OGit:
    '''
    owner git to print progress in clone action
    '''

    def __init__(self, repo_dir, remote_url, branch=None) -> None:
        self._repo_dir = repo_dir
        self._remote_url = remote_url
        self._branch = branch
        try:
            _, self._screen_width = os.popen('stty size', 'r').read().split()
        except ValueError as v_e:
            logger.warning(str(v_e))

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

    def check_out_version(self, version):
        '''
        check out version
        '''
        return self._fetch_upstream(version=version)

    def clone_or_pull_repo(self):
        '''
        clone or pull git repo
        '''
        self._fetch_upstream()

    def _fetch_upstream(self, version=None):
        repo = Repo.init(self._repo_dir)
        remote = None
        for item in repo.remotes:
            if self._remote_url.rstrip(".git") == item.url.rstrip(".git"):
                remote = item
            else:
                continue
        if remote is None:
            remote_name = "upstream"
            remote = git.Remote.add(repo=repo, name=remote_name, url=self._remote_url)
        logger.info("Fetching into %s ...", self._repo_dir)
        try:
            if version is None:
                remote.fetch(self._branch, progress=CustomRemote(), depth=1)
            else:
                repo.commit(version)
        except ValueError:
            try:
                remote.fetch(version, progress=CustomRemote(), depth=1)
            except GitCommandError:
                logger.error("fetch failed")
                return False
        except GitCommandError:
            logger.error("fetch failed")
            return False

        try:
            if version is None:
                repo.git.checkout(self._branch)
            else:
                repo.git.checkout(version)
        except GitCommandError:
            logger.error("update faild")
            return False
        logger.info("Fetching into %s successful\n", self._repo_dir)
        return True

    @staticmethod
    def get_repo_info(repo_dir: str):
        '''
        return git repo info: remote_url, branch
        '''
        try:
            repo = Repo(repo_dir)
            remote_url = repo.remote().url
            branch = repo.active_branch.name
            return remote_url, branch
        except TypeError:
            return "", ''
        except git.GitError:
            return "", ""
        except ValueError:
            return "", ""


class CustomRemote(git.RemoteProgress):
    '''
    Rewrote RemoteProgress to show the process of code updates
    '''

    def update(self, op_code, cur_count, max_count=None, message=''):
        '''
        rewrote update function
        '''
        end_str = "\r"
        if op_code & 2 == RemoteProgress.END:
            end_str = "\r\n"
        print(self._cur_line, end=end_str)
