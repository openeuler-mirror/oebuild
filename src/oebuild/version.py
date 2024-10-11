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

# release log:
# 1, Mugentest is an open-source Linux-OS testing framework developed by openEuler.
# Oebuild integrates Mugentest, making it more convenient to test the operating system.
# 2, The handling of the openEuler build template has been optimized. The original
# repos field contained necessary repository download information for the build
# environment. However, since all repository information related to the build is now
# managed by manifest.yaml, the processing of the repos field will be done in list
# form rather than as a dictionary.
__version__ = '0.1.0.7'
