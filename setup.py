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

import setuptools

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
os.chdir(SCRIPT_DIR)

with open('README.md', 'r', encoding="utf-8") as f:
    long_description = f.read()

with open('src/oebuild/version.py', 'r', encoding="utf-8") as f:
    __version__ = None
    # pylint: disable=W0122
    exec(f.read())
    assert __version__ is not None

version = os.environ.get('OEBUILD_VERSION', __version__)

setuptools.setup(
    name='oebuild',
    version=version,
    author='alichinese',
    author_email='',
    description='',
    long_description=long_description,
    # http://docutils.sourceforge.net/FAQ.html#what-s-the-official-mime-type-for-restructuredtext-data
    long_description_content_type="text/markdown",
    url='',
    packages=setuptools.find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
    ],
    install_requires=[
        'setuptools',
        'packaging',
        'PyYaml',
        'docker',
        'GitPython',
        'colorama',
        'ruamel.yaml',
        'dataclasses',
        'reprint',
        'prettytable',
        'kconfiglib'
    ],
    python_requires='>=3.8',
    entry_points={'console_scripts': ('oebuild = oebuild.app.main:main',)},
)
