# oebuild

#### General introduction

oebuild is a tool for building and configuring openEuler Embedded,  which can simplify the build process of openEuler Embedded and automate  the generation of customized openEuler Embedded distributions

Key features of OEBUILD include: 

- Automatically download build dependencies for different versions, including  yocto-meta-openeuler, yocto-poky, yocto-meta-openembedded, etc.
- Depending on the user's build options (machine type, features, etc.), a customized build environment profile is created. 
- Use containers to create an isolated build environment, reduce the risk of  host contamination, and simplify the configuration and dependency  management of your build system. 
- Start the openEuler Embedded image build. 
- Manage the compilation environment for SDKs with different feature environments. 
- The QEMU image is simulated online. 
- Deploy and uninstall current packages online. 

#### Installation Steps

OEbuild is implemented based on Python language, supports Python 3.8 at least,  and can be installed through pip, as described in the following command: 

```
pip3 install oebuild
```

If you want to install a specific version of OEBUILD, run the following command: 

```
pip3 install oebuild==<version>
```

If you want to upgrade the OEBUILD version to the latest version, run the following command: 

```
pip3 install oebuild --upgrade
```

After the installation is complete, run the help command to check whether  OEBUILD is added to the path path by default, refer to the following  command: 

```
oebuild -h
```

If the message indicates that the OEBUILD command cannot be found, you  need to add the OEBUILD execution path to the path, as follows: 

1. Open the .bashrc file in the root directory with the editor 
2. Add `export PATH=~/.local/bin:$PATH` at the end
3. Close the current terminal and reopen a terminal before executing the `oebuild -h` command

#### How to compile a standard image

##### Initialize the OEBUILD directory

Run the following command to initialize OEBUILD: 

```
oebuild init <directory>
```

This operation initializes the directory of OEBUILD, which indicates the name of the `<directory>` directory to be initialized

Note: Since the operation of OEbuild depends on the operation of the Docker  environment, if you do not have a Docker application installed locally,  please follow the prompts given by OEbuild 

##### Update the OEBUILD runtime environment

Run the following command to complete the initial environment preparation: 

```
oebuild update
```

There are three main points in the update work: 

Pull related running container images

Download the yocto-meta-openeuler repository code from gitee 

Download the basic layer from Gitee 

##### Create a compilation profile

Run the following command to generate the compilation configuration file: 

```
oebuild generate
```

The image corresponding to the default configuration file is the qemu  standard image of aarch64, and the /build/qemu-aarch64 build working  directory is created, and the compile.yaml build configuration file is  generated in this directory 

##### Perform a build operation

Go to the /build/qemu-aarch64 build directory and run the following command to enter the image builder: 

```
oebuild bitbake openeuler-image
```

Please wait 20 minutes and you will get a standard openEuler Embedded aarch64 architecture 

#### Introduction to commands

##### oebuild init

The workspace initialization command is mainly used to initialize the  OEBUILD project workspace, and it needs to be followed by the name of  the directory to be initialized, as follows: 

```
oebuild init [directory] [-u yocto_remote_url] [-b branch]
```

directory: Indicates the name of the directory to be initialized (note: we cannot  perform the initialization operation again in the directory that has  already been initialized) 

yocto_remote_url: The remote link of yocto-meta-openeuler, which is  https://gitee.com/openeuler/yocto-meta-openeuler.git by default

branch: a branch of yocto-meta-openeuler, which is the master by default 

(Note: OEBUILD relies on the repository of yocto-meta-openeuler that has been  adapted to OEBUILD when executing the build task, which means that if  yocto-meta-openeuler does not support OEBUILD, you cannot use OEBUILD to build yocto-meta-openeuler) 

For example, to initialize the demo directory, you only need to run the following command: 

```
oebuild init demo
```

After the init command is executed, two tasks are performed: one is to create the src source code directory, create the .oebuild directory, copy the  config configuration file to the .oebuild, and the other is to modify  the config file accordingly if the -u or -b parameter is set 

After initializing the directory, the directory structure of the demo is as follows: 

```
.oebuild
	config
src
```

src: This directory is used to store the source code related to compilation 

.oebuild: The directory is used to store the global configuration file, after the initialization of the OEBUILD, you will see a config configuration  file, which will be applied when building the compilation base  environment. 

##### oebuild update

After the basic environment update command is executed, it is generally  necessary to execute this command before executing the build link. 

```
oebuild update [yocto docker layer] [-tag]
```

The update command can be used to update yocto, docker, and layer, and for  docker updates, there is a -tag option, which is used to specify which  container image to update 

For a separate usage, please refer to the following example: 

```
oebuild update yocto   // Update Yocto, if there is no download according to the configuration in .oebuild/config, update if available, or backup and re-download if changes have been made
oebuild update docker [-tag]  // Update the build container image, the -tag parameter is optional, this operation can be skipped if you want to build the host mode later
oebuild update layer   // Update the layer, the layer is a fundamental metadata layer required for openEuler building, therefore it needs to be prepared in advance.
```

The execution of the update command depends on the configuration file of  the oebuild workspace, which is located in /.oebuild/config, and the  configuration file content is as follows: 

```
docker:
  repo_url: swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container
  tag_map:
    openEuler-23.03: "23.03"
    master: latest
    openEuler-22.03-LTS-SP2: 22.03-lts-sp2
    openEuler-23.09: "23.09"
    openEuler-24.03: "24.03"
basic_repo:
  yocto_meta_openeuler:
    path: yocto-meta-openeuler
    remote_url: https://gitee.com/openeuler/yocto-meta-openeuler.git
    branch: master
```

As you can see from the configuration file, it is mainly divided into two  parts, which are docker and basic_repo. The docker directory records the container information of the openEuler build, including the remote  image address and the mapping between each version of openEuler Embedded and the build container. The basic_repo record is the source code  repository of openEuler Embedded, named yocto-meta-openeuler, which  contains path, which indicates the local name after downloading,  remote_url indicates the remote repository address, and branch indicates branch information. 

Therefore, if we want to specify a source code repository, we can directly modify  the relevant information under yocto-meta-openeuler. If we want to  specify the mapping between the build version and the build container,  we can modify the relevant information under docker. 

> Note: docker, basic_repo and yocto-meta-openeuler are two key keys, which  cannot be changed, remote_url and branch can be changed to the  parameters of the `yocto-meta-openeuler` warehouse that they have adapted

##### oebuild generate

The Create Profile directive, which is used to generate the profile. 

```
oebuild generate [-p platform] [-f features] [-t toolchain_dir] [-d build_directory] [-l list] [-b_in build_in]
```

-p: the name of `platform` the board, the full name, a parameter required to generate a configuration file, which is qemu-aarch64 by default

-f: Attribute parameter, full name, `feature` an optional parameter for generating a configuration file, without a default value

-t: The external compilation chain parameter, full name `toolchain_dir` , is an optional parameter in the generation configuration file,  without a default value, which means that we can select this parameter  if we do not need the cross-compilation chain provided by the system and choose our own.

-n: external nativesdk parameter, full name, an optional parameter for  generating configuration files, without a default value, which means  that if we do not need the nativesdk provided by the system and choose  the nativesdk we specify `nativesdk_dir` , we can select this parameter.

-s: sstate_mirrors value, full name `sstate_cache` , an optional parameter for the build configuration file, without a  default value, which means that if we want to apply the host-side  sstate-cache to the build, we can use that parameter to specify.

-s_dir: the address of the generated sstate-cache, the full name `sstate_dir` , an optional parameter of the generation configuration file, there is  no default value, this value can specify where the sstate-cache is  stored at the time of construction

-m: the address of the generated tmp, the full name `tmp_dir` , an optional parameter of the generation configuration file, there is  no default value, this value can specify where the tmp is stored at the  time of construction.

-tag: based on the container tag enabled when the container is built `--docker_tag` , the full name is an optional parameter of the generation  configuration file, there is no default value, usually enabling the  build container will automatically match the build container image, but  the user can also specify which container tag to use

-dt: timestamp, full name, there is no default value, usually the DATETIME  variable will be used when building yocto, if the variable is not set,  the current timestamp is used by default, it can also be set `--datetime` , this parameter is the set timestamp parameter

-df: whether to disable the openeuler_fetch function `disable_fetch` , the full name is enable, which is consistent with the default value  in yocto, and the function of this value is to prohibit the execution of the openeuler_fetch, and openeuler_fetch is the upstream software  package download function implemented by openEuler, and its execution  can be disabled through this parameter

-d: the initialized compilation directory, if this parameter is not set,  the initialized compilation directory is the same as the -p parameter 

-l: list parameter, full name, which lists both the supported boards and features `--list` , and indicates the boards it supports

OEbuild relies on the compile.yaml build configuration file to complete the  preparation of the build environment when building, and the command to  create the configuration file is already part of the build instruction  content, which will check whether OEBUILD is adapted, and the rule to  check whether it is adapted is `yocto-meta-openeuler` whether a `.oebuild` hidden directory is created in the `yocto-meta-openeuler` root directory, and `-p` it will be parsed `.oebuild/platform` The corresponding platform configuration file will be parsed, `-f` and the parameter can be `.oebuild/feature` passed in with multiple values, such as the following example:

```
oebuild generate -p aarch64-std -f systemd -f openeuler-qt
```

The resulting build profile will cover `systemd openeuler-qt` the characteristics of both

Finally, the build configuration file will be generated in the compilation directory (the path given by `oebuild generate` the prompts is the compilation directory after the execution is completed `compile.yaml` ), please refer to the configuration file introduction for a detailed introduction `compile.yaml` to the configuration file. In the next step of the build process, the  configuration file will be parsed, before that, the user can modify the  configuration file according to their specific scene environment,  because the configuration file generated according to the `oebuild generate` instruction is only counted as a reference template, the purpose is to  give the user a basic template reference, reduce the cost of user  learning, and enable the user to get started quickly.

##### oebuild bitbake

Build the directive, which parses `compile.yaml` (generated by the `oebuild generate` directive) and then initializes the build environment. The parameters of this command are as follows:

-h: Help command, executed 

```
oebuild bitbake -h
```

to get help 

In general, the directory mapping relationship of the container mount after startup is as follows: 

```
<workspace>/src:/usr1/openeuler/src
<workspace>/build/xxx:/usr1/openeuler/build/xxx
```

If there is a `toolchain_dir` parameter in , that is, `compile.yaml` there is a user-defined external toolchain, a mount directory will be added, as follows:

```
<toolchain_dir>：/usr1/openeuler/native_gcc
```

If you run directly, you will enter the interactive environment built by openEuler, and `oebuild bitbake` you can freely execute any bitbake-related commands, such as `bitbake zlib -c do_fetch` etc., and if you directly execute `oebuild bitbake zlib -c do_fetch` , the build log will be directly output in the console

##### oebuild manifest

The purpose of the baseline file management command is to download the  upstream software packages that openEuler depends on or to version the  existing software packages. 

```
oebuild manifest [create / download] [-f manifest_dir]
```

create: To create a baseline file, specify the path of the manifest.yaml baseline file with the -f parameter 

download: To download the upstream software package based on the baseline file,  the -f parameter specifies the path of the manifest.yaml baseline file 

##### oebuild clear

The Clear Cache command, which can be used to clean up some of the content  generated by the execution of OEBUILD, including container images 

```
oebuild clear [docker]
```

After the command is executed, OEBUILD will traverse each build space, read  the container ID in the .env file, and then execute the stop operation,  and then the rm operation 

##### oebuild menv

SDK development environment management command, which is used to manage the initial SDK environment, is used to meet the requirements of the  development environment faced by openEuler upper-layer application  developers 

```
oebuild menv [create list remove active] [-d directory] [-f file] [-n env_name]
```

-d: SDK directory parameter, full name `directory` , is used to specify the initialized SDK directory, which can be directly specified when creating an SDK environment

-f: SDK script path parameter, full name `file` , is used to specify the uninitialized SDK-shell file, which can be  specified when creating the SDK environment, and OEBUILD will start the  initialization operation

-n: the name of the SDK environment, the full name of the SDK environment, the user determines the name `env_name` of the SDK environment, and the SDK environment can be managed by this name

This function has four secondary commands, which are as follows: 

create: This command can create an SDK compilation environment, using `oebuild menv [-d xxx / -f xxx] -n x` either -d or -f parameters

list: lists the SDK environment, this command can list all the SDK  environments that have been installed so far, and use the following  method `oebuild menv list` :

remove: remove: removes the SDK environment, this command can remove the  specified SDK environment, and the command can be used in `oebuild menv remove -n xxx` the following way

Active: Activate the SDK environment, this command can activate the specified  SDK environment, so you can use SDK-related libraries at compile time,  using `oebuild menv active -n xxx` 

> Note: The SDK here refers to the SDK developed based on the application that  accompanies the construction of the openEuler image, through which you  can develop a variety of binary applications that can run in the image 

##### oebuild runqemu

The qemu simulation command can be used to implement qemu simulation  locally, and the user can directly run this function to implement qemu  simulation after executing the qemu image build 

```
oebuild runqemu nographic
```

Through the above command, you can call qemu to run the qemu image, this  command is the encapsulation of poky's runqemu, the operation of the  qemu tool is based on the container, so you need to add nographic, that  is, non-graphical start, otherwise an error will be reported, the  parameters of the command are the same as the parameters of the original runqemu, and the specific parameters are as follows: 

```
Usage: you can run this script with any valid combination
of the following environment variables (in any order):
  KERNEL - the kernel image file to use
  BIOS - the bios image file to use
  ROOTFS - the rootfs image file or nfsroot directory to use
  DEVICE_TREE - the device tree blob to use
  MACHINE - the machine name (optional, autodetected from KERNEL filename if unspecified)
  Simplified QEMU command-line options can be passed with:
    nographic - disable video console
    novga - Disable VGA emulation completely
    sdl - choose the SDL UI frontend
    gtk - choose the Gtk UI frontend
    gl - enable virgl-based GL acceleration (also needs gtk or sdl options)
    gl-es - enable virgl-based GL acceleration, using OpenGL ES (also needs gtk or sdl options)
    egl-headless - enable headless EGL output; use vnc (via publicvnc option) or spice to see it
    (hint: if /dev/dri/renderD* is absent due to lack of suitable GPU, 'modprobe vgem' will create
    one suitable for mesa llvmpipe software renderer)
    serial - enable a serial console on /dev/ttyS0
    serialstdio - enable a serial console on the console (regardless of graphics mode)
    slirp - enable user networking, no root privilege is required
    snapshot - don't write changes back to images
    kvm - enable KVM when running x86/x86_64 (VT-capable CPU required)
    kvm-vhost - enable KVM with vhost when running x86/x86_64 (VT-capable CPU required)
    publicvnc - enable a VNC server open to all hosts
    audio - enable audio
    [*/]ovmf* - OVMF firmware file or base name for booting with UEFI
  tcpserial=<port> - specify tcp serial port number
  qemuparams=<xyz> - specify custom parameters to QEMU
  bootparams=<xyz> - specify custom kernel parameters during boot
  help, -h, --help: print this text
  -d, --debug: Enable debug output
  -q, --quiet: Hide most output except error messages

Examples:
  runqemu
  runqemu qemuarm
  runqemu tmp/deploy/images/qemuarm
  runqemu tmp/deploy/images/qemux86/<qemuboot.conf>
  runqemu qemux86-64 core-image-sato ext4
  runqemu qemux86-64 wic-image-minimal wic
  runqemu path/to/bzImage-qemux86.bin path/to/nfsrootdir/ serial
  runqemu qemux86 iso/hddimg/wic.vmdk/wic.vhd/wic.vhdx/wic.qcow2/wic.vdi/ramfs/cpio.gz...
  runqemu qemux86 qemuparams="-m 256"
  runqemu qemux86 bootparams="psplash=false"
  runqemu path/to/<image>-<machine>.wic
  runqemu path/to/<image>-<machine>.wic.vmdk
  runqemu path/to/<image>-<machine>.wic.vhdx
  runqemu path/to/<image>-<machine>.wic.vhd
```

> Note: The runqemu function needs to be added when the image is built, that is `IMAGE_CLASSES += "qemuboot"` , added in the BB file related to the image, because the runqemu build  is based on qemuboot.conf, and qemuboot.conf is generated by the  qemuboot class, and the specific qemu startup parameters at the time of  construction refer to the configuration file under  yocto-meta-openeuler/conf/machine

##### oebuild deploy-target / undeploy-target

Software package online deployment or uninstallation function, through which the software package can be deployed to a target machine in real time, this command is designed to help developers deploy and debug the developed  software package in real time 

```
oebuild deploy-target/undeploy-target <package> name@ip
```

This command encapsulates the deploy-target and undeploy-target of poky, and the target machine needs to be prepared in advance to use this  function, and the IP address between the target machine and the host  must be connected. 

#### Introduction to the profile

OEBUILD has multiple configuration files after it is built, and each  configuration file has a different scope, and the following describes  where and what each configuration file is stored 

##### config

The configuration file of the oebuild environment in the peripheral  environment is stored in the .oebuild directory in the root directory of the oebuild project, and the configuration file structure is as  follows: 

```
docker:
  repo_url: swr.cn-north-4.myhuaweicloud.com/openeuler-embedded/openeuler-container
  tag_map:
    openEuler-22.09: '22.09'
    openEuler-22.03-lts-sp1: 22.03-lts-sp1
    master: latest
basic_repo:
  yocto_meta_openeuler:
    path: yocto-meta-openeuler
    remote_url: https://gitee.com/openeuler/yocto-meta-openeuler.git
    branch: master
```

docker: indicates the information about building containers, and the container  images listed under this field will download the corresponding  containers `oebuild update` after execution

repo_url: indicates the address of the docker repository of openEuler Embedded 

tag_map: indicates the docker build container tag used for each openEuler Embedded version 

basic_repo: represents the basic repo repository, as the name suggests, it means  that it exists as a base role before the build, and the config  configuration file will be parsed `oebuild update` when executed, and then the corresponding build code repository will be downloaded

yocto-meta-openeuler: currently the only basic warehouse for oebuild 

path: The name of the path to which the repository is downloaded 

remote_url: The remote address of the warehouse 

branch: The branch of the warehouse 

##### .env

The compilation directory configuration file structure is as follows: 

```
container:
	remote: xxxxxxxxxxxx
	branch: xxxxxxxxxxxx
	short_id: xxxxxxxxxx
	volumns:
	- /xxxxxxxxxxx
	- /xxxxxxxxxxx
```

container: indicates the configuration information of the container 

Remote: Indicates `yocto-meta-openeuler` the remote URL
branch: Indicates `yocto-meta-openeuler` branch information

short_id: indicates the ID of the container 

volumns: Represents the directory map in which the container is hanging 

In the process of executing the build, OEBUILD will parse the `.env` configuration file to determine whether to recreate a new container or  enable the old container by comparing other parameters in the  environment, including (remote, branch, volumns) Only these three  parameters are consistent with the corresponding parameters to be built, the old container will continue to be pulled, otherwise a new container will be created. In addition, OEbuild will also check whether the  container used for the set short_id exists, and if it does not exist, it will also create a new container. When a new container is created, the  new configuration information is rewritten to `.env` 

##### compile.yaml

Build a configuration file with the following structure: 

```
platform: aarch64-std
machine: qemu-aarch64
toolchain_type: EXTERNAL_TOOLCHAIN_aarch64
sdk_dir:
toolchain_dir:
repos:
  yocto-poky:
    url: https://gitee.com/openeuler/yocto-poky.git
    path: yocto-poky
    refspec: openEuler-22.09

  yocto-meta-openembedded:
    url: https://gitee.com/openeuler/yocto-meta-openembedded.git
    path: yocto-meta-openembedded
    refspec: dev_hardknott

  yocto-meta-ros:
    url: https://gitee.com/openeuler/yocto-meta-ros.git
    path: yocto-meta-ros
    refspec: dev_hardknott
local_conf: |
- xxx
- xxx
layers: 
- xxx
- xxxx
```

platform: indicates the CPU architecture, 

machine: indicates the machine type 

toolchain_type: indicates the compilation chain type 

sdk_dir: Reserved field 

toolchain_dir: indicates a custom external compilation chain path, and if this parameter `-t` is `oebuild generate` set in , this field `compile.yaml` will exist in

repos: Indicates the repository that needs to be used when initializing the build environment 

url: indicates the remote address of the warehouse 

path: indicates the local address of the warehouse 

refspec: indicates the version branch of the repository 

local_conf:local.conf, which will replace the content `build/conf/local.conf` matched in after OEbuild finishes oe_init

layers: meta layer, which will be added by calling `bitbake-layers add-layer` after the OEbuild oe_init is executed

#### Developer Help

The OEbuild project welcomes hobby developers to participate in the  development of OEBUILD, in order to make developers participate in the  development of OEBUILD faster and better, we have written the following  guidelines. 

##### Introduction to the OEbuild directory

Open the OEBUILD repository, we can see that the OEBUILD level 1 directory has the following contents: 

```
docs
src
.gitignore
MANIFEST.in
README.md
setup.py
```

docs: a directory of documents, which is used to store introductory information about OEbuild 

src: the core source code directory, the core source code where we really  run OEBUILD is stored, and the detailed process of participating in the  development of OEBUILD will be introduced in detail in the future 

.gitignore: A file that is ignored by a git commit, and the content in the file can be automatically ignored on git commit 

MANIFEST.in: This file is the configuration file of pip that contains additional  files when packing, and the content in the file will be included  according to the rules when python packaging is executed 

README.md: A brief introductory document 

setup.py: python packaging entry file, we finally need to package the wheel package through this file 

##### How to use setup.py for debugging or packaging

When we complete the relevant development work and debug, we will do this through the relevant settings within the setup.py 

Open setup.py file, we can see its contents as follows: 

```
# Copyright 2018 Open Source Foundries Limited.
# Copyright (c) 2020, Nordic Semiconductor ASA
#
# SPDX-License-Identifier: Apache-2.0

import os

import setuptools

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
os.chdir(SCRIPT_DIR)

with open('README.md', 'r') as f:
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
        'ruamel.yaml'
    ],
    python_requires='>=3.8',
    entry_points={'console_scripts': ('oebuild = oebuild.app.main:main',)},
)
```

You can see that the introduced modules are, this is the core module of the package, we don't care about the other introductions for the time  being, because there are almost no changes for developers, here we focus on the following, the setting is literally understood as the necessary  installation of dependencies, that is to say, the third-party libraries  that OEBUILD runs to depend, if we have some dependencies of other  libraries in the subsequent OEbuild development process `setuptools` `install_requires` , we need to add them here.

After entering the oebuild directory, we can execute the following command to enter the debug state: 

```
pip install -e .
```

Note: If the above command is run as a normal user, you need to confirm whether to add the local execution path `PATH` to the environment variable, if you run it as the root user, you don't  need to consider it, so that we can directly run the OEBUILD related  instructions

In this way, in the subsequent development and debugging process, we can  change the code at any time and take effect at any time 

##### Introduction to the SRC source code

It's being perfected...
