# 总体介绍：

`oebuild`作为openEuler Embedded项目的开发工具，一直以来承担着openEuler Embedded入门的导引角色，目前oebuild已经集成了相当多的功能，例如OS构建，交叉编译链构建，oebuild插件管理，软件包在线部署等等功能，然后对于一个嵌入式系统的发布，测试这一环节必不可少，openEuler Embedded对于系统版本的发布有着严格测试要求，因此对于OS系统开发者来说，本地化测试就显得尤为重要，而对于openEuler生态的系统来说，mugen是openEuler社区开放的测试框架，提供公共配置和方法以便社区开发者进行测试代码的编写和执行，其中就包括了openEuler Embedded,此次设计的插件可以使oebuild能够通过mugen来实现嵌入式OS的本地化测试。

## 功能概述

该插件主要用于通过`oebuild`工具实现以下功能：

- 自动化本地化Mugen测试集成。
- 支持`qemu`与BSP等嵌入式环境的选择。
- 配置远程环境以便使用`qemu`进行测试。
- 提供多种测试套件选择，包括：
  1. Tiny镜像测试
  2. OS基础测试
  3. 嵌入式安全配置测试
  4. 嵌入式基础开发测试

## 使用方法

该插件提供了通过`oebuild`命令行工具来运行`mugen`测试的能力。以下是一个典型的使用示例：

### 1. 运行测试

```bash
bash oebuild mugen-test --env bsp --mugen-path /path/to/mugen
```

--env 参数用于指定测试环境，可以是qemu或者bsp。
--mugen-path 指定mugen工具的安装路径。

### 2. 选择测试套件

执行上述命令后，您将能够选择需要运行的测试套件：

- Tiny镜像测试
- OS基础测试
- 嵌入式安全配置测试
- 嵌入式基础开发测试

根据测试需求，选择对应的测试套件。

### 3. QEMU远程测试配置

如果选择了`qemu`环境，则需要提供远程测试的详细信息，例如IP地址、用户名、密码等：

```bash
bash oebuild mugen-test --env qemu --mugen-path /path/to/mugen --ip 192.168.0.100 --user root --password your_password --port 22
```
--ip 指定远程测试机器的IP地址
--user 指定远程测试机器的用户名
--password 指定远程测试机器的密码


停止QEMU
在OS基础测试、嵌入式安全配置测试或嵌入式基础开发测试完成后，可以使用以下命令停止QEMU：

```bash
bash bash qemu_ctl.sh stop
```


