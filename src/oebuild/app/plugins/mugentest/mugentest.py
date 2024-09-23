"""
MugenTest module to run Mugen test cases for openEuler Embedded OS.
Supports running tests in qemu and BSP environments.
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
    It supports both qemu and BSP environments.
    """
    name = 'mugentest'
    help_msg = 'This command allows you to run Mugen test cases for openEuler Embedded OS.'
    description = textwrap.dedent('''\
        Run Mugen test cases for openEuler Embedded systems.
        Select the environment (qemu or BSP) and specify the test case from a predefined list.
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
        Adds arguments to the parser for environment, Mugen path, and remote testing.
        """
        parser = self._parser(
            parser_adder,
            usage=textwrap.dedent('''\
                %(prog)s --env <qemu|bsp> --mugen-path <path_to_mugen> [other options]
                Then select the test suite from the following options:
                  1 -- Tiny Image Test
                  2 -- OS Basic Test
                  3 -- Embedded Security Config Test
                  4 -- Embedded Application Development Test
            ''')
        )

        parser.add_argument('--env', choices=['qemu', 'bsp'], required=True,
                            help='Specify the test environment: qemu or bsp')
        parser.add_argument('--mugen-path', required=False,
                            help='Specify the path to the Mugen installation')
        parser.add_argument('--kernal_img_path', required=False,
                            help='Path to the QEMU kernel image')
        parser.add_argument('--initrd_path', required=False,
                            help='Path to the QEMU initrd image')
        parser.add_argument('--ip', required=False,
                            help='IP address for remote testing (required for qemu)')
        parser.add_argument('--user', required=False,
                            help='Username for remote login (required for qemu)')
        parser.add_argument('--password', required=False,
                            help='Password for remote login (required for qemu)')
        parser.add_argument('--port', required=False, default=22,
                            help='SSH port (default is 22, required for qemu)')
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

        if not self.is_mugen_installed(mugen_path):
            print(f"Mugen not found at {mugen_path}. Please install Mugen first "
                  f"or specify the correct path.")
            sys.exit(1)

        if args.env == "qemu" and (not args.ip or not args.user or not args.password):
            logger.error("For qemu environment, --ip, --user, and --password are required.")
            return

        self.select_test_suite(mugen_path, args)

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
        Runs the selected Mugen test suite based on the environment and user input.
        """
        cmd = None
        try:
            print(f"Running {suite} with Mugen...")

            if args.env == "qemu":
                if suite == "embedded_tiny_image_test":
                    cmd = (
                        f"bash {mugen_path}/mugen.sh -c --ip {args.ip} --password {args.password} "
                        f"--user {args.user} --port {args.port} --put_all --run_remote"
                    )
                else:
                    if not args.kernal_img_path or not args.initrd_path:
                        logger.error(
                            "For this test, --kernal_img_path and --initrd_path are required."
                        )
                        return
                    qemu_start_cmd = (
                        f"sh qemu_ctl.sh start --put_all --kernal_img_path {args.kernal_img_path} "
                        f"--initrd_path {args.initrd_path}"
                    )
                    if suite in {
                        "embedded_os_basic_test", "embedded_security_config_test",
                        "embedded_application_develop_tests"
                    }:
                        qemu_start_cmd += " --qemu_type arm"
                    subprocess.run(qemu_start_cmd, shell=True, check=True)

                    if suite == "embedded_application_develop_tests":
                        compile_cmd = f"bash {mugen_path}/mugen.sh -b {suite}"
                        subprocess.run(compile_cmd, shell=True, check=True)

                    cmd = f"bash {mugen_path}/mugen.sh -f {suite} -s"

            elif args.env == "bsp":
                cmd = f"bash {mugen_path}/mugen.sh -f {suite} -s"

            if cmd:
                subprocess.run(cmd, shell=True, check=True)
                print(f"Test suite {suite} completed successfully.")

                if args.env == "qemu" and suite != "embedded_tiny_image_test":
                    subprocess.run("sh qemu_ctl.sh stop", shell=True, check=True)

        except subprocess.CalledProcessError as e:
            logger.error("Failed to run test suite %s: %s", suite, e)
            sys.exit(1)
