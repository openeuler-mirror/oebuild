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

import colorama

#: Color used (when applicable) for printing with successful()
INFO_COLOR = colorama.Fore.WHITE

#: Color used (when applicable) for printing with successful()
SUCCESS_COLOR = colorama.Fore.LIGHTGREEN_EX

#: Color used (when applicable) for printing with wrn()
WRN_COLOR = colorama.Fore.LIGHTYELLOW_EX

#: Color used (when applicable) for printing with err() and die()
ERR_COLOR = colorama.Fore.LIGHTRED_EX

class MyLog:
    '''
    Simple log output is implemented, including info, successful, warning, err four output types
    '''

    @staticmethod
    def info(msg):
        '''
        normal message print
        '''
        print(INFO_COLOR + msg)

    @staticmethod
    def successful(msg):
        '''
        successful message print
        '''
        print(SUCCESS_COLOR + msg)

    @staticmethod
    def warning(msg):
        '''
        warning messaage print
        '''
        print(WRN_COLOR + msg)

    @staticmethod
    def err(msg):
        '''
        err message print
        '''
        print(ERR_COLOR + msg)
