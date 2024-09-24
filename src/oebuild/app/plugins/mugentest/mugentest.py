"""
MugenTest module to run Mugen test cases for openEuler Embedded OS.
Supports running tests in remote environments.
"""

import argparse
import os
import subprocess
import logging
import textwrap
import sys

from oebuild.command import OebuildCommand

logger = logging.getLogger()


class MugenTest(OebuildCommand):
    """
    MugenTest class allows running Mugen test cases for openEuler Embedded OS.
    It supports remote environments.
    """
    name = 'mugentest'
    help_msg = 'This command allows you to run Mugen test cases for openEuler Embedded OS.'
    description = textwrap.dedent('''\
        Run Mugen test cases for openEuler Embedded systems.
        Configure remote testing and specify the test case from a predefined list.
    ''')

    def __init__(self):
        """
        Initializes the MugenTest class with command name, help message, and description.
        """
        super().__init__(
            name=self.name,
            help_msg=self.help_msg,
            description=self.description
        )

    def do_add_parser(self, parser_adder) -> argparse.ArgumentParser:
        """
        Adds arguments to the parser for Mugen path and remote testing.
        """
        parser = self._parser(
            parser_adder,
            usage=textwrap.dedent('''\
                %(prog)s --mugen-path <path_to_mugen> --ip <remote_ip>
                --user <remote_user> --password <remote_password> [other options]
                Then select the test suite from the following options:
                  1 -- Tiny Image Test
                  2 -- OS Basic Test
                  3 -- Embedded Security Config Test
                  4 -- Embedded Application Development Test
            ''')
        )

        parser.add_argument('--mugen-path', required=True,
                            help='Specify the path to the Mugen installation')
        parser.add_argument('--ip', required=True,
                            help='IP address for remote testing')
        parser.add_argument('--user', required=True,
                            help='Username for remote login')
        parser.add_argument('--password', required=True,
                            help='Password for remote login')
        parser.add_argument('--port', required=False, default=22,
                            help='SSH port (default is 22)')
        # 注释掉的参数
        # parser.add_argument('--env', choices=['qemu', 'bsp'], required=True,
        #                     help='Specify the test environment: qemu or bsp')
        # parser.add_argument('--kernal_img_path', required=False,
        #                     help='Path to the QEMU kernel image')
        # parser.add_argument('--initrd_path', required=False,
        #                     help='Path to the QEMU initrd image')
        return parser

    def do_run(self, args: argparse.Namespace, unknown=None):
        """
        Main function to handle argument parsing and running the appropriate test suite.
        """
        if '-h' in unknown or '--help' in unknown:
            self.print_help_msg()
            sys.exit(0)

        args = args.parse_args(unknown)
        mugen_path = self.get_mugen_path(args.mugen_path)

        self.check_and_install_lshw()

        self.setup_mugen_environment(mugen_path)

        if not self.is_mugen_installed(mugen_path):
            print(f"Mugen not found at {mugen_path}. Please install Mugen first "
                  f"or specify the correct path.")
            sys.exit(1)

        if not args.ip or not args.user or not args.password:
            logger.error("For remote testing, --ip, --user, and --password are required.")
            return

        self.select_test_suite(mugen_path, args)

    def check_and_install_lshw(self):
        """
        Check if lshw is installed, if not, install it.
        """
        try:
            subprocess.run(['lshw', '-version'], check=True)
            print("lshw is already installed.")
        except subprocess.CalledProcessError:
            print("lshw is not installed. Installing lshw...")
            sys.exit(0)

    def setup_mugen_environment(self, mugen_path):
        """
        Sets up the Mugen environment by switching to the correct directory
        and cleaning up old configurations.
        """
        os.chdir(mugen_path)
        env_file = os.path.join(mugen_path, 'conf', 'env.json')
        if os.path.exists(env_file):
            print(f"Removing existing {env_file}")
            os.remove(env_file)
        else:
            print(f"No env.json found in {mugen_path}/conf.")

    def get_mugen_path(self, custom_path=None):
        """
        Returns the Mugen installation path, either custom or default.
        """
        if custom_path:
            return custom_path
        return os.getenv('MUGEN_HOME', os.path.expanduser("~/.local/mugen"))

    def is_mugen_installed(self, mugen_path):
        """
        Checks if Mugen is installed at the given path.
        """
        return os.path.exists(mugen_path)

    def select_test_suite(self, mugen_path, args):
        """
        Allows the user to select and run a test suite.
        """
        test_suites = {
            1: "embedded_tiny_image_test",
            2: "embedded_os_basic_test",
            3: "embedded_security_config_test",
            4: "embedded_application_develop_tests"
        }

        print("Select a test suite to run:")
        for i, suite in test_suites.items():
            print(f"{i} -- {suite.replace('_', ' ').capitalize()}")

        choice = int(input(f"Enter the number of the test suite to run "
                           f"(1-{len(test_suites)}): "))

        if choice not in test_suites:
            print("Invalid choice. Exiting.")
            return

        selected_suite = test_suites[choice]
        self.run_mugen_test(mugen_path, selected_suite, args)

    def run_mugen_test(self, mugen_path, suite, args):
        """
        Runs the selected Mugen test suite based on the user input.
        """
        cmd = None
        try:
            print(f"Running {suite} with Mugen...")

#            if args.env == "qemu":
#                if suite == "embedded_tiny_image_test":
#                    cmd = (
#                        f"bash {mugen_path}/mugen.sh -c --ip {args.ip} --password {args.password} "
#                        f"--user {args.user} --port {args.port} --put_all --run_remote"
#                    )
#                else:
#                    if not args.kernal_img_path or not args.initrd_path:
#                        logger.error(
#                            "For this test, --kernal_img_path and --initrd_path are required."
#                        )
#                        return
#                    qemu_start_cmd = (
#                        f"sh qemu_ctl.sh start --put_all --kernal_img_path {args.kernal_img_path} "
#                        f"--initrd_path {args.initrd_path}"
#                    )
#                    if suite in {
#                        "embedded_os_basic_test", "embedded_security_config_test",
#                        "embedded_application_develop_tests"
#                    }:
#                        qemu_start_cmd += " --qemu_type arm"
#                    subprocess.run(qemu_start_cmd, shell=True, check=True)
#
#                    if suite == "embedded_application_develop_tests":
#                        compile_cmd = f"bash {mugen_path}/mugen.sh -b {suite}"
#                        subprocess.run(compile_cmd, shell=True, check=True)
#
#                    cmd = f"bash {mugen_path}/mugen.sh -f {suite} -s"
#
#            elif args.env == "bsp":
#                cmd = f"bash {mugen_path}/mugen.sh -f {suite} -s"
#
#            if cmd:
#                subprocess.run(cmd, shell=True, check=True)

            os.chdir(mugen_path)

            # Constructing the remote environment setup command
            cmd = (
                f"bash mugen.sh -c --ip {args.ip} --password {args.password} "
                f"--user {args.user} --port {args.port}"
            )
            result = subprocess.run(cmd, shell=True, check=True)

            if result.returncode == 0:
                print("Successfully configured and connected to the remote environment.")
            else:
                print(f"Failed to configure the remote environment."
                      f"Return code: {result.returncode}.")
                sys.exit(result.returncode)

            # Running the selected test suite
            cmd = f"bash mugen.sh -f {suite} -s"
            result = subprocess.run(cmd, shell=True, check=True)
            if result.returncode == 0:
                print(f"Test suite {suite} completed successfully.")
            else:
                print(f"Test suite {suite} failed with return code {result.returncode}.")

        except subprocess.CalledProcessError as e:
            logger.error("Failed to run test suite %s: %s", suite, e)
            sys.exit(1)
