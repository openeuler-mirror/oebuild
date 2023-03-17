import os

import setuptools

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
os.chdir(SCRIPT_DIR)

with open('README.rst', 'r') as f:
    long_description = f.read()

with open('src/oebuild/version.py', 'r') as f:
    __version__ = None
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
    long_description_content_type="text/x-rst",
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
        'reprint'
    ],
    python_requires='>=3.8',
    entry_points={'console_scripts': ('oebuild = oebuild.app.main:main',)},
)
