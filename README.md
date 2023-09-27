#### 总体介绍

oebuild是openEuler Embedded孵化的一个开源项目，是为了辅助开发openEuler Embedded项目而衍生的辅助开发工具，是openEuler Embedded项目健康运行的一个催化剂，目前oebuild主要实现了主体框架，业务只涵盖了构建，将来会涉及到CICD，本地测试，云构建等等，oebuild的使用将不仅仅限于命令行窗口，还会搭载上层IDE来使用。yocto实现了构建的灵活性，但是做应用的定制与实现需要有较高的学习成本与环境成本，oebuild将完全摒弃这些开发羁绊，解放你的双手，只需要几个指令，即可获得你要的应用镜像，你不需要去下载代码，不需要去准备编译环境，如果你要的应用不是特有定制的，甚至不要求你去学习如何修改bb文件，一切都可以交给oebuild来做，而oebuild需要的，仅仅是一个网络而已。对，就这么简单！！！

#### 如何编译一个标准镜像

这里将介绍如何使用oebuild来进行基于openEuler Embedded项目编译标准的aarch64的qemu应用

##### 安装python3和pip

oebuild由python语言编写而成，通过pip命令来完成安装，python3与pip的安装会根据运行系统的不同而不同，如果时ubuntu类系统，则通过如下命令安装：

```
apt-get install python3 python3-pip
```

如果是centos，则通过如下命令安装：

```
yum install python3 python3-pip
```

如果时suse，则通过如下命令安装：

```
zepper install python3 python3-pip
```

注1：由于版本或名称可能会有所不同，因此在各系统安装python3或pip时，请根据实际环境来安装，例如：有些系统会默认python即python3，有些系统则需要使用python-is-python3包来安装。

注2：如果该系统没有pip包，则可以通过离线方式来安装，预先下载pip包，然后再通过python安装，通过如下命令来完成pip的安装：

```
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py   # 下载安装脚本
python get-pip.py	# python is python3
```

##### 下载oebuild.wheel

安装完pip后则可以通过以下命令来完成oebuild的安装

```
pip install oebuild
```

或者点击[该地址](https://gitee.com/alichinese/oebuild-bin)进入oebuild二进制仓，在该仓下有最新的二进制包，运行以下命令来完成oebuild的安装

```
pip install <oebuild.wheel>
```

oebuild会依赖一些第三方库辅助运行，因此相关的第三方库也会直接被安装，如果在安装过程中显示错误，或报第三方库安装请求失败等，请再次重新运行安装oebuild的命令即可。

注： 如果安装在安装oebuild时是以root用户执行，则在安装后可以直接运行，如果是以普通用户安装的，则需要注意将普通用户执行路径添加到环境变量中，可以参考以下方式来完成添加：

1，以普通用户身份打开.bashrc

```
cd ~ && vim .bashrc
```

2, 在文件末尾查看是否将命令执行路径添加到环境变量中，该路径一般为`/home/<user>/.local/bin`,如果没有，则将以下语句添加到文件末尾

```
export PATH=/home/<user>/.local/bin:$PATH
```

在以上命令行中，`<user>`表示是你此时的用户名，如果不确定，则可以通过执行`whoami`来确定

3，在添加完成后保存退出，vim编辑板的保存退出按键为：先按`esc`，再按`shift + :`, 最后输入`wq`然后按回车键即可

4，退出后还需要刷新以下环境变量，执行以下命令完成环境变量的刷新

```
source ~/.bashrc
```

这样你就可以使用oebuild这个工具了，试着执行一下`oebuild -h`，看看能否显示oebuild的帮助信息

##### 初始化oebuild目录

运行如下命令完成oebuild的初始化工作：

```
oebuild init <directory>
```

该操作会初始化oebuild的目录，`<directory>`表示要初始化目录的名称

注：由于oebuild的运行整体依赖docker环境的运行，因此，如果你本地没有安装docker应用，则请按照oebuild给出的提示进行操作，或者按以下给出的方式完成docker的安装

1，确定你本机的系统类型，这里以ubuntu为例讲解，执行以下命令完成docker的安装

```
sudo apt install docker docker.io -y
```

2, 添加docker用户组

```
sudo groupadd docker
```

3, 将本用户添加到docker组内

```
sudo usermod -a -G docker $(whoami)
```

4, 重新启动docker

```
sudo systemctl-reload && systemctl restart docker 
```

5, 修改docker.sock读写权限

```
sudo chmod o+rw /var/run/docker.sock
```

其他操作系统请参考ubuntu方式进行

##### 更新oebuild运行环境

运行如下命令来完成初期环境的准备工作：

```
oebuild update
```

更新工作主要有两点：一，pull相关的运行容器镜像；二，从gitee上下载yocto-meta-openeuler仓代码，如果本地没有openeuler相关容器，则在这一步执行会比较漫长，请耐心等待。

##### 创建编译配置文件

运行如下命令来产生编译配置文件：

```
oebuild generate
```

默认配置文件对应的镜像是aarch64标准镜像

##### 执行构建操作

执行如下命令会进入镜像构建程序：

```
oebuild bitbake openeuler-image
```

请耐心等待20分钟，你就可以得到一个标准的openEuler Embedded aarch64架构的镜像

#### 命令介绍

##### oebuild init

目录初始化指令，主要用于初始化oebuild项目目录，运行该指令在后面需要跟要初始化的目录名，如下：

```
oebuild init [directory] [-u yocto_remote_url] [-b branch]
```

directory: 表示要初始化的目录名称（注意：我们无法在已经初始化的目录内再次执行初始化操作）

yocto_remote_url：yocto-meta-openeuler的remote远程链接

branch：yocto-meta-openeuler的分支

（注意：oebuild在执行构建任务时是依赖已经适配oebuild的yocto-meta-openeuler的仓的）

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

基础环境更新指令，在执行初始化目录指令后，在执行构建环节之前必须要先执行该命令。

```
oebuild update [-t docker_tag] [-l list] [-i ignore] [-e enable]
```

-t: 指更新哪个tag的容器

-l: 表示列出可选资源列表，目前只有docker这一项

-i: 表示在更新时忽略哪一项，可选的有docker与meta，docker代表容器镜像，meta代表yocto-meta-openeuler仓

-e: 表示在更新时使能哪一项，可选范围与解释同上

执行更新操作如下命令：

```
oebuild update
```

oebuild执行构建有两个必要的前提，一是构建需要的容器，二是主构建仓（yocto-meta-openeuler）。所以更新命令主要以这两部分展开

另外，如果我们有自己的oebuild适配仓，可以在`config`配置文件中修改（该文件在`<workspace>/.oebuild`目录下），如果已经先执行过更新操作，然后再次执行`oebuild update`会将原有的`yocto-meta-openeuler`做备份，将在工作空间根目录下创建yocto-bak备份目录，然后将备份后的`yocto-meta-openeuler`移动到该目录。更改基础仓在config中的如下字段修改：

```
basic_repo:
  yocto_meta_openeuler:
    path: yocto-meta-openeuler
    remote_url: https://gitee.com/openeuler/yocto-meta-openeuler.git
    branch: master
```

basic_repo与yocto-meta-openeuler是两个key键，不可以更改，remote_url与branch可以更改成自己已经适配的`yocto-meta-openeuler`仓的参数

注：如果我们不输入任何参数，即直接执行`oebuild update`，则默认更新容器镜像和基础仓

##### oebuild generate

创建配置文件指令，而该命令就是用来产生配置文件的。

```
oebuild generate [-p platform] [-f features] [-t toolchain_dir] [-d build_directory] [-l list]
```

-p：cpu类型参数，全称`platform`，生成配置文件需要的一个参数，默认为aarch64-std

-f：特性参数，全称`feature`，生成配置文件需要的一个参数，没有默认值

-t：外部编译链参数，全称`toolchain_dir`，生成配置文件需要的一个参数，没有默认值，该值表示如果我们不需要系统提供的交叉编译链而选择自己的交叉编译链，则可以选择该参数。

-d：初始化的编译目录，如果不设置该参数，则初始化的编译目录和-p参数保持一致

-l: list参数，有两个可选范围，platform和feature，platform则会列出支持的platform列表，feature则会列出支持的feature列表

oebuild在构建时依赖compile.yaml配置文件来完成构建操作，创建配置文件指令已经属于构建指令内容，该操作将会检查`yocto-meta-openeuler`是否适配了oebuild，检查是否适配的规则便是是否在`yocto-meta-openeuler`根目录创建了`.oebuild`隐藏目录，而`-p`则会解析`.oebuild/platform`下相应的平台配置文件，`-f`参数则会解析`.oebuild/feature`下相应的配置文件，该参数是可以多值传入的，例如如下范例：

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

一般来说，启动后的容器挂在的目录映射关系如下：

```
<workspace>/src:/usr1/openeuler/src
<workspace>/build/:/usr1/openeuler/build
```

如果在`compile.yaml`中有`toolchain_dir`参数，即有用户自定义外部工具链，则会增加一个挂载目录，如下：

```
<toolchain_dir>：/usr1/openeuler/native_gcc
```

##### oebuild upgrade

在线升级指令，该指令会请求远程oebuild版本信息，通过和本地oebuild版本对比来判断是否进行升级

由于oebuild二进制包存放在gitee仓库中，因此oebuild在升级时会先克隆最新的二进制仓到用户根目录，并以一个随机文件名命名，然后执行`sudo pip install <oebuild*.whl>`来完成升级，在这之中会要求用户输入root密码，在完成升级后会自动删除oebuild二进制包

##### oebuild compile

对指定C或者C++文件，进行交叉编译的指令。执行后，静态编译过的二进制文件将被复制到用户当前目录下。

```
oebuild compile [-d source_directory] [-p platform]
```

source_directory: 表示目标源代码文件目录。

platform：表示交叉编译的目标架构。可选项：arm, aarch64, riscv64, x86_64。此值默认为aarch64。

##### oebuild qemu_run

运行二进制文件的指令。在容器内一键执行交叉编译过的二进制文件，并返回执行结果。使用qemu user模式实现。

```
oebuild compile [-d target_directory] [-p platform]
```

target_directory: 表示目标二进制文件目录。

platform：表示可执行文件运行目标平台架构。可选项：arm, aarch64, riscv64, x86_64。此值默认为aarch64。

##### oebuild deploy

将openEuler镜像部署到指定平台的指令。该指令将编译或者下载的镜像文件，部署到指定平台。命令自动配置qemu的网络功能，实现传送文件的可能。目前仅支持qemu-system平台。
一键执行后，命令行将直接跳转到qemu用户登录界面。

```
oebuild deploy [-d target_directory] [-p platform] [-m mode]
```

target_directory: 表示目标镜像文件夹的目录。程序会将整个文件夹复制到容器内，再在容器端进行部署。

platform：表示部署目标平台的架构。可选项：arm, aarch64, riscv64, x86_64。此值默认为aarch64。

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