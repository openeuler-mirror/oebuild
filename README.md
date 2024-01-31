#### 总体介绍

[oebuild](https://gitee.com/openeuler/oebuild) 是一个用于构建和配置 openEuler Embedded 的工具， 能够为用户简化 openEuler Embedded 的构建流程，自动化生成定制化的 openEuler Embedded 发行版

oebuild 的主要功能包括：

- 自动化下载不同版本的构建依赖，包括 [yocto-meta-openeuler](https://gitee.com/openeuler/yocto-meta-openeuler) , [yocto-poky](https://gitee.com/openeuler/yocto-poky) , [yocto-meta-openembedded](https://gitee.com/openeuler/yocto-meta-openembedded) 等。
- 根据用户的构建选项（机器类型，功能特性等等），创建出定制化的构建环境配置文件。
- 使用容器创建一个隔离的构建环境，降低主机污染风险，简化构建系统的配置和依赖管理。
- 启动 openEuler Embedded 镜像构建。
- 对不同特性环境的sdk进行编译环境的管理。
- 对qemu镜像进行在线仿真。
- 对当下软件包进行在线部署以及卸载。

#### 安装步骤

oebuild基于python语言实现，最低支持python3.8版本，通过pip来进行安装，参考如下命令：

```
pip3 install oebuild
```

如果想要安装指定版本的oebuild，参考如下命令：

```
pip3 install oebuild==<version>
```

如果想要升级oebuild版本为最新版，参考如下命令：

```
pip3 install oebuild --upgrade
```

安装完成后执行帮助命令查看oebuild是否被默认添加到path路径中，参考如下命令：

```
oebuild -h
```

如果提示无法找到oebuild命令，则需要添加oebuild执行路径到path中，参考如下方法：

1. 用编辑器打开根目录下的.bashrc文件
2. 在最后面添加`export PATH=~/.local/bin:$PATH`
3. 关闭当前终端重新开启一个终端，然后再执行`oebuild -h`命令

#### 如何编译一个标准镜像

##### 初始化oebuild目录

运行如下命令完成oebuild的初始化工作：

```
oebuild init <directory>
```

该操作会初始化oebuild的目录，`<directory>`表示要初始化目录的名称

注：由于oebuild的运行整体依赖docker环境的运行，因此，如果你本地没有安装docker应用，则请按照oebuild给出的提示进行操作

##### 更新oebuild运行环境

运行如下命令来完成初期环境的准备工作：

```
oebuild update
```

更新工作主要有三点：

​	pull相关的运行容器镜像

​	从gitee上下载yocto-meta-openeuler仓代码

​	从gitee上下载基础的layer层

##### 创建编译配置文件

运行如下命令来产生编译配置文件：

```
oebuild generate
```

默认配置文件对应的镜像是aarch64的qemu标准镜像，此时会创建<oebuild_workspace>/build/qemu-aarch64构建工作目录，在该目录下会产生compile.yaml构建配置文件

##### 执行构建操作

进入<oebuild_workspace>/build/qemu-aarch64构建目录，执行如下命令会进入镜像构建程序：

```
oebuild bitbake openeuler-image
```

请耐心等待20分钟，你就可以得到一个标准的openEuler Embedded aarch64架构的镜像

#### 命令介绍

##### oebuild init

工作空间初始化指令，主要用于初始化oebuild项目工作空间，运行该指令在后面需要跟要初始化的目录名，如下：

```
oebuild init [directory] [-u yocto_remote_url] [-b branch]
```

directory: 表示要初始化的目录名称（注意：我们无法在已经初始化的目录内再次执行初始化操作）

yocto_remote_url：yocto-meta-openeuler的remote远程链接，默认是https://gitee.com/openeuler/yocto-meta-openeuler.git

branch：yocto-meta-openeuler的分支，默认是master

（注意：oebuild在执行构建任务时是依赖已经适配oebuild的yocto-meta-openeuler的仓的，意思是如果yocto-meta-openeuler不支持oebuild，则无法使用oebuild对yocto-meta-openeuler进行构建）

例如初始化demo目录只需要执行如下命令：

```
oebuild init demo
```

init命令执行后主要执行两个任务：一是创建src源码目录，创建.oebuild目录，拷贝config配置文件到.oebuild，二是如果设置了-u或-b参数，则对config文件进行相应的修改

初始化目录后demo的目录结构如下：

```
.oebuild
	config
src
```

src：该目录用于存放跟编译相关的源码

.oebuild：目录用于存放全局性配置文件，在oebuild执行初始化后，会看到有一个config配置文件，该配置文件将在搭建编译基础环境时应用到。

##### oebuild update

基础环境更新指令，在执行初始化目录指令后，一般来说在执行构建环节之前要先执行该命令。

```
oebuild update [yocto docker layer] [-tag]
```

update命令可以更新yocto，docker以及layer，对于docker的更新则有-tag的选项，该选项用来单独指定更新哪个容器镜像

单独的使用方式参考如下范例：

```
oebuild update yocto   // 更新yocto，如果没有根据.oebuild/config中配置的下载，如果有则更新，如果已经做了改动，备份后重新下载
oebuild update docker [-tag]  // 更新构建容器镜像，-tag参数可选，如果以后想要主机模式构建，这个操作可以不执行
oebuild update layer   // 更新layer，所谓的layer是openEuler构建时必须依赖的基础元数据层，因此需要提前准备
```

更新命令的执行依赖oebuild工作空间的配置文件，该配置文件位于<oebuild_workspace>/.oebuild/config，配置文件内容如下：

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

从配置文件中可以看到，主要分为两个部分，分别是docker和basic_repo。docker下记录的是openEuler构建的容器信息，有远程镜像地址和openEuler Embedded每个版本与构建容器的映射关系。basic_repo下记录的是openEuler Embedded的源码仓，名称为yocto-meta-openeuler，里面有path，表示下载后的本地名称，remote_url表示远程仓地址，branch表示分支信息。

因此，如果我们要指定某个源码仓，则直接修改yocto-meta-openeuler下的相关信息即可。如果我们要指定构建版本与构建容器的映射关系，则修改docker下的相关信息即可。

> 注：docker，basic_repo与yocto-meta-openeuler是两个key键，不可以更改，remote_url与branch可以更改成自己已经适配的`yocto-meta-openeuler`仓的参数

##### oebuild generate

创建配置文件指令，而该命令就是用来产生配置文件的。

```
oebuild generate [-p platform] [-f features] [-t toolchain_dir] [-d build_directory] [-l list] [-b_in build_in]
```
当命令行只输入oebuild generate不带其他参数时，会进入菜单选择模式，通过菜单选择来进行下面介绍参数的填充，选择完成且进行保存之后，就会生成对应的compile.yaml文件。

-p：单板名称，全称`platform`，生成配置文件需要的一个参数，默认为qemu-aarch64

-f：特性参数，全称`feature`，生成配置文件可选的一个参数，没有默认值

-t：外部编译链参数，全称`toolchain_dir`，生成配置文件可选的一个参数，没有默认值，该值表示如果我们不需要系统提供的交叉编译链而选择自己的交叉编译链，则可以选择该参数。

-n：外部nativesdk参数，全称`nativesdk_dir`，生成配置文件可选的一个参数，没有默认值，该值表示如果我们不需要系统提供的nativesdk而选择自己指定的nativesdk，则可以选择该参数。

-s：sstate_mirrors值，全称`sstate_cache`，生成配置文件可选的一个参数，没有默认值，该值表示如果我们想要将主机端的sstate-cache应用于构建，则可以使用该参数指定。

-s_dir：生成的sstate-cache存放地址，全称`sstate_dir`，生成配置文件可选的一个参数，没有默认值，该值可以指定在构建时的sstate-cache存放在哪里

-m：生成的tmp存放地址，全称`tmp_dir`，生成配置文件可选的一个参数，没有默认值，该值可以指定在构建时的tmp存放在哪里。

-tag：基于容器构建时启用的容器tag，全称`--docker_tag`，生成配置文件可选的一个参数，没有默认值，通常启用构建容器会自动匹配构建容器镜像，但是用户也可以指定使用哪个容器tag

-dt：时间戳，全称`--datetime`，没有默认值，通常在yocto构建时会使用DATETIME变量，该变量如果不设置则默认采用当前时间戳，也可以进行设置，该参数即为设置时间戳参数

-df：是否禁用openeuler_fetch功能，全称`disable_fetch`，默认为enable，即和yocto中的默认值保持一致，该值的作用为禁止openeuler_fetch的执行，openeuler_fetch为openEuler自我实现的上游软件包下载功能，通过该参数可以禁止其执行

-d：初始化的编译目录，如果不设置该参数，则初始化的编译目录和-p参数保持一致

-l: list参数，全称`--list`，会同时列出当下支持的单板列表以及特性列表，特性列表会标明其支持的单板

oebuild在构建时依赖compile.yaml构建配置文件来完成构建环境准备工作，创建配置文件指令已经属于构建指令内容，该操作将会检查`yocto-meta-openeuler`是否适配了oebuild，检查是否适配的规则便是是否在`yocto-meta-openeuler`根目录创建了`.oebuild`隐藏目录，而`-p`则会解析`.oebuild/platform`下相应的平台配置文件，`-f`参数则会解析`.oebuild/feature`下相应的配置文件，该参数是可以多值传入的，例如如下范例：

```
oebuild generate -p aarch64-std -f systemd -f openeuler-qt
```

则生成的构建配置文件会涵盖`systemd openeuler-qt`两者的特性

最终会在编译目录下（在执行完`oebuild generate`后按提示给出的路径即为编译目录）生成构建配置文件`compile.yaml`,关于该配置文件的详细介绍请参考配置文件介绍中的`compile.yaml`。在下一步的构建流程会解析该配置文件，在此之前，用户可以根据自身特定场景环境来修改配置文件，因为按该`oebuild generate`指令生成的配置文件仅算作一个参考模板，目的是给用户一个最基本的模板参考用，减少用户学习的成本，使用户能够快速上手。

##### oebuild bitbake

构建指令，该指令会解析`compile.yaml`(通过`oebuild generate`指令生成的)，然后完成构建环境的初始化工作。该命令参数如下：

-h：帮助命令，通过执行

```
oebuild bitbake -h
```

来获取帮助

一般来说，启动后的容器挂载的目录映射关系如下：

```
<workspace>/src:/usr1/openeuler/src
<workspace>/build/xxx:/usr1/openeuler/build/xxx
```

如果在`compile.yaml`中有`toolchain_dir`参数，即有用户自定义外部工具链，则会增加一个挂载目录，如下：

```
<toolchain_dir>：/usr1/openeuler/native_gcc
```

如果直接执行`oebuild bitbake`则会进入openEuler构建的交互环境，此时可以自由执行bitbake任何相关的命令，例如`bitbake zlib -c do_fetch`等等，如果直接执行`oebuild bitbake zlib -c do_fetch`等则会直接在控制台输出构建日志

##### oebuild manifest

基线文件管理命令，该指令的目的是为了对openEuler依赖的上游软件包进行下载或者对现有软件包进行版本管理。

```
oebuild manifest [create / download] [-f manifest_dir]
```

create：命令为创建基线文件，-f参数指定manifest.yaml基线文件的路径

download：命令为根据基线文件下载上游软件包，-f参数指定manifest.yaml基线文件的路径

##### oebuild clear

清理缓存命令，该指令可以用来清理执行oebuild而产生的一些内容，包括容器镜像

```
oebuild clear [docker]
```

目前仅限于清理构建时残留的docker容器，该命令执行后，oebuild会遍历每个构建空间，读取.env文件中容器ID，然后执行stop操作，再执行rm操作

##### oebuild menv

sdk开发环境管理命令，该指令用来对各初始化的sdk环境进行管理，其作用是为了应对openEuler 上层应用开发者所面临的开发环境的需求

```
oebuild menv [create list remove active] [-d directory] [-f file] [-n env_name]
```
-d：sdk目录参数，全称`directory`，用于指定已经初始化好的sdk目录，在创建sdk环境时可以直接通过该参数指定

-f：sdk脚本路径参数，全称`file`，用于指定未初始化的sdk-shell文件，在创建sdk环境时可以通过该参数指定，此时oebuild会启动执行初始化操作

-n：sdk环境的命名，全称`env_name`，用户确定sdk环境的名称，通过该名称可以对sdk环境进行管理

该功能有四个二级指令功能如下：

create：创建功能，该命令可以创建一个sdk编译环境，使用方式为`oebuild menv [-d xxx / -f xxx] -n x`，-d与-f两个参数各选其一

list：列出sdk环境，该命令可以将目前已经安装的sdk环境全部列出，使用方式为`oebuild menv list`

remove：移除sdk环境，该命令可以将指定的sdk环境移除，使用方式为`oebuild menv remove -n xxx`

active：激活sdk环境，该命令可以将指定的sdk环境激活，因此可以在编译时使用sdk相关的库，使用方式为`oebuild menv active -n xxx`

> 注：这里的sdk指的是在openEuler镜像构建时都会伴随的基于该镜像的应用开发的sdk，通过该sdk可以开发各种各样能够运行在这个镜像中的二进制应用

##### oebuild runqemu

qemu 仿真命令，通过该命令可以在本地实现qemu仿真，用户可以在执行完qemu镜像构建后直接运行该功能实现qemu仿真

```
oebuild runqemu nographic
```

通过以上命令即可调用qemu来运行qemu镜像，该命令是对poky的runqemu的封装，qemu工具的运行基于容器，因此需要添加nographic，即非图形化启动，否则会报错，该命令的参数和原始runqemu的参数一样，并无不同，具体参数如下：

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

> 注：runqemu功能需要在镜像构建时添加支持，即在镜像相关的bb文件中添加`IMAGE_CLASSES += "qemuboot"`，因为runqemu构建依qemuboot.conf，而qemuboot.conf是由qemuboot类产生的，具体qemu在构建时的启动参数参考yocto-meta-openeuler/conf/machine下的配置文件

##### oebuild deploy-target / undeploy-target

软件包在线部署或卸载功能，通过该命令可以实现软件包实时部署到一个目标机上，该命令旨在帮助开发者对所开发的软件包实时进行部署调试

```
oebuild deploy-target/undeploy-target <package> name@ip
```

该命令是对poky的deploy-target与undeploy-target的封装，这个功能的使用需要提前准备好目标机，并且目标机和主机之间IP要联通。

#### 配置文件介绍

oebuild在生成后有多个配置文件，每个配置文件的作用域不同，下面将介绍各配置文件存放位置以及内容

##### config

oebuild在外围环境的配置文件,该配置文件存放在oebuild项目根目录下的.oebuild目录中，该配置文件结构如下：

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

**docker**: 表示构建容器相关信息，在该字段下面所列的容器镜像，在执行`oebuild update`后会下载相应的容器

​	repo_url: 表示openEuler Embedded的docker远程仓地址

​	tag_map: 表示每个openEuler Embedded版本对用的docker构建容器tag

**basic_repo**:表示基础的repo仓，顾名思义，表示在构建之前是作为底座的角色存在的，在执行`oebuild update`时会解析config配置文件，然后下载相应的构建代码仓

​	yocto-meta-openeuler: 目前oebuild唯一的基础仓

​		path: 该仓下载的路径名称

​		remote_url: 该仓的远程地址

​		branch: 该仓的分支

##### .env

 编译目录配置文件结构如下：

```
container:
	remote: xxxxxxxxxxxx
	branch: xxxxxxxxxxxx
	short_id: xxxxxxxxxx
	volumns:
	- /xxxxxxxxxxx
	- /xxxxxxxxxxx
```

container:表示容器相关配置信息

​	remote: 表示`yocto-meta-openeuler`远程url

​	branch: 表示`yocto-meta-openeuler`分支信息

​	short_id: 表示容器ID

​	volumns: 表示容器挂在的目录映射

oebuild在执行构建过程中，会解析`.env`配置文件，通过对比环境中的其他参数确定是否重新创建一个新的容器还是启用旧容器，比对的内容包括（remote，branch，volumns)只有这三个参数与要构建的对应参数一致，才会继续拉起旧容器，否则就会创建一个新的容器。另外oebuild也会检查设置的short_id对用的容器是否存在，不存在也会创建一个新的容器。在创建新的容器后，新的配置信息会重新写入到`.env`中

##### compile.yaml

构建配置文件，该配置文件结构如下：

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

platform：表示cpu架构，

machine：表示机器类型

toolchain_type: 表示编译链类型

sdk_dir: 保留字段

toolchain_dir：表示自定义外部编译链路径，如果在`oebuild generate`设置了该参数`-t`，则会在`compile.yaml`存在该字段

repos: 表示在初始化构建环境时需要用到的仓

​	url: 表示仓的远程地址

​	path: 表示仓在本地的地址

​	refspec:表示仓的版本分支

local_conf：local.conf替换内容，该值在oebuild执行完oe_init后将替换`build/conf/local.conf`中匹配到的内容

layers: meta层，该值在oebuild执行完oe_init后将通过调用`bitbake-layers add-layer`来添加meta层

#### 开发者帮助

oebuild项目欢迎广大爱好开发者参与贡献oebuild的发展，为了使开发者更快更好的参与到oebuild的开发工作中来，我们专门写了如下指导。

##### oebuild目录介绍

打开oebuild仓我们可以看到，oebuild一级目录有如下内容：

```
docs
src
.gitignore
MANIFEST.in
README.md
setup.py
```

docs：文档目录，该目录用于存放关于oebuild的介绍性信息

src：核心源码目录，我们真正运行oebuild的核心源码就存放在这里，后续介绍关于参与开发oebuild的详细流程将会详细介绍该目录内容

.gitignore：git提交忽略的文件，在该文件中通过设置的内容可以在git提交时自动忽略

MANIFEST.in：该文件为pip在打包时包含额外文件的配置文件，在该文件中的内容将在执行python打包时按规则进行包含 

README.md：简要介绍性文件

setup.py：python打包入口文件 ，我们最终要打包wheel包就要通过该文件来完成



##### 如何使用setup.py进行调试或打包

在我们完成相关的开发性工作并进行调试时，将通过setup.py内的相关设置来完成该工作

打开setup.py文件，我们可以看到其内容如下：

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

可以看到引入的模块儿有`setuptools`,这个是打包的核心模块儿，关于其他的介绍我们暂且不管，因为对于开发者来说几乎没改动，这里我们着重介绍以下`install_requires`，该设置从字面意思理解就是依赖的必要安装，也就是说oebuild运行要依赖的第三方库，如果我们在后续的oebuild开发过程中有一些其他库的依赖，则需要在这里添加。

在进入oebuild目录后，我们可以执行以下命令进入调试状态：

```
pip install -e .
```

注：以上命令的运行如果以普通用户运行，需要先确认是否将本地执行路径添加到环境变量`PATH`中，如果以root用户运行则不需要考虑，这样我们可以直接运行oebuild相关指令

这样在后续开发与调试过程中，我们可以随时改代码随时生效

##### src源码介绍

正在完善中...