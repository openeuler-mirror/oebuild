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

import logging
import colorama

#: Color used (when applicable) for printing with successful()
INFO_COLOR = colorama.Fore.WHITE

#: Color used (when applicable) for printing with successful()
SUCCESS_COLOR = colorama.Fore.LIGHTGREEN_EX

#: Color used (when applicable) for printing with wrn()
WRN_COLOR = colorama.Fore.LIGHTYELLOW_EX

#: Color used (when applicable) for printing with err() and die()
ERR_COLOR = colorama.Fore.LIGHTRED_EX

# 创建logger对象
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 创建文件处理器
fh = logging.FileHandler('oebuild.log')
fh.setLevel(logging.INFO)

# 创建控制台处理器
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 将格式化器添加到文件处理器和控制台处理器
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# 将处理器添加到logger对象
logger.addHandler(fh)
logger.addHandler(ch)
