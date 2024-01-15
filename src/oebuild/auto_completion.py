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
import hashlib
import re
import sys
import textwrap
import logging
from os.path import abspath, expanduser, expandvars, join

logger = logging.getLogger()


class AutoCompletion():
    """
        code hint
    """

    def run(self):
        """
            Subclasses must implement; called to run the command.
        Returns:

        """
        oebuild_rc = textwrap.dedent("""
        ###!###>>>>>>>>>>>oebuild_complete>>>>>>>>>>>>>>> 
        if pip list | grep oebuild &> /dev/null ; then
            export oebuild_sh=$(pip show oebuild | grep Location | awk -F" " '{print $2}')/oebuild/app/conf/oebuild.sh
            if [ -f $oebuild_sh ] ; then
                    . $oebuild_sh
            fi
        fi
        ###!###<<<<<<<<<<<oebuild_complete<<<<<<<<<<<<<<<""").lstrip()
        on_win = bool(sys.platform == "win32")
        on_mac = bool(sys.platform == "darwin")
        bashrc_path = abspath(expanduser(
            expandvars(join("~", ".bash_profile" if (on_mac or on_win) else ".bashrc"))))
        try:
            with open(bashrc_path, encoding='utf-8') as fh:
                rc_content = fh.read()
        except FileNotFoundError:
            rc_content = ""
        except:
            raise

        pattern_bashrc = (
            r'(?=###!###>>>>>>>>>>>oebuild_complete>>>>>>>>>>>>>>>)[\W\w]+(?<=###!###<<<<<<<<<<<'
            'oebuild_complete<<<<<<<<<<<<<<<)')

        re_info = re.search(pattern_bashrc, rc_content)

        if re_info is None:
            rc_content += f"\n{oebuild_rc}\n"
            with open(bashrc_path, 'w', encoding='utf-8') as fh:
                fh.write(rc_content)
        else:
            bashrc_data = textwrap.dedent(re_info.group()).lstrip()
            bashrc_ma5 = self.md5_string(bashrc_data)
            rc_content_md5 = self.md5_string(oebuild_rc)
            if bashrc_ma5 != rc_content_md5:
                rc_content = re.sub(pattern_bashrc, f"\n{oebuild_rc}\n", rc_content)
                with open(bashrc_path, 'w', encoding='utf-8') as fh:
                    fh.write(rc_content)

    def md5_string(self, in_str):
        """
            md5 str
        Args:
            in_str:

        Returns:

        """
        md5 = hashlib.md5()
        md5.update(in_str.encode("utf8"))
        result = md5.hexdigest()
        return result
