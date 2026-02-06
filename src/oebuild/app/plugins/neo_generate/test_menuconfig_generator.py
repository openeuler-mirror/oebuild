import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from kconfiglib import Kconfig
from oebuild.nightly_features import FeatureRegistry

sys.path.insert(0, os.path.dirname(__file__))
from menuconfig_generator import NeoMenuconfigGenerator  # noqa: E402


class MenuconfigGeneratorTest(unittest.TestCase):
    """Smoke tests that validate the generated Kconfig structure."""

    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        base = Path(self.workspace.name)
        self.nightly_dir = base / 'nightly-features'
        self.platform_dir = base / 'platform'
        (self.nightly_dir / 'system').mkdir(parents=True)
        (self.nightly_dir / 'containers').mkdir(parents=True)
        self.platform_dir.mkdir(parents=True)
        (self.platform_dir / 'qemu-aarch64.yaml').write_text('')
        self._write_feature(
            'system',
            'system',
            textwrap.dedent(
                """\
                id: system
                name: System Services
                prompt: >
                  System services backbone
                machines:
                  - qemu-aarch64
                sub_feats:
                  - id: ssh
                    name: SSH Access
                  - id: console
                    name: Console Access
                one_of:
                  - self/ssh
                  - self/console
                default_one_of: self/ssh
                """
            ),
        )
        self._write_feature(
            'containers',
            'containers',
            textwrap.dedent(
                """\
                id: containers
                name: Container Platform
                prompt: Container tooling stack
                dependencies:
                  - system/system
                sub_feats:
                  - id: containerd
                    name: containerd runtime
                  - id: isulad
                    name: Isulad runtime
                choice:
                  - self/containerd
                  - self/isulad
                """
            ),
        )
        self._write_feature(
            'containers',
            'podman',
            textwrap.dedent(
                """\
                id: podman
                name: Podman runtime
                dependencies:
                  - containers
                """
            ),
        )

    def tearDown(self):
        self.workspace.cleanup()
        # Cleanup any temporary workspace created by _build_kconfig_with_custom_features
        if hasattr(self, '_workspace_to_cleanup'):
            self._workspace_to_cleanup.cleanup()

    def _write_feature(self, category: str, file_name: str, content: str) -> None:
        target = self.nightly_dir / category / f'{file_name}.yaml'
        target.write_text(content)

    def _build_kconfig(self) -> str:
        registry = FeatureRegistry(self.nightly_dir)
        generator = NeoMenuconfigGenerator(
            registry=registry,
            platform_dir=self.platform_dir,
            default_platform='qemu-aarch64',
        )
        return generator.build_kconfig_text()

    def _build_kconfig_with_custom_features(
        self, features: dict[str, tuple[str, str]]
    ) -> Kconfig:
        """Build a Kconfig object with custom features.

        Args:
            features: A dict mapping category to (filename, content) tuples.

        Returns:
            A kconfiglib Kconfig object loaded with the generated Kconfig file.
        """
        # Create workspace and setup directories
        workspace = tempfile.TemporaryDirectory()
        base = Path(workspace.name)
        nightly_dir = base / 'nightly-features'
        platform_dir = base / 'platform'
        platform_dir.mkdir(parents=True)
        (platform_dir / 'qemu-aarch64.yaml').write_text('')

        # Write feature files
        for category, files in features.items():
            for filename, content in files:
                (nightly_dir / category).mkdir(parents=True, exist_ok=True)
                target = nightly_dir / category / f'{filename}.yaml'
                target.write_text(content)

        # Build Kconfig text
        registry = FeatureRegistry(nightly_dir)
        generator = NeoMenuconfigGenerator(
            registry=registry,
            platform_dir=platform_dir,
            default_platform='qemu-aarch64',
        )
        kconfig_text = generator.build_kconfig_text()

        # Write Kconfig to file and load with kconfiglib
        kconfig_file = base / 'Kconfig'
        kconfig_file.write_text(kconfig_text)

        # Suppress warnings and load
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            kconf = Kconfig(str(kconfig_file), warn_to_stderr=False)

        # Store workspace for cleanup
        self._workspace_to_cleanup = workspace
        return kconf

    def test_categories_and_feature_blocks_are_emitted(self):
        kconfig = self._build_kconfig()
        self.assertIn('menu "System"', kconfig)
        self.assertIn('config FEATURE_SYSTEM', kconfig)
        self.assertIn('menu "Containers"', kconfig)

    def test_one_of_and_choice_layout_and_dependencies(self):
        kconfig = self._build_kconfig()
        self.assertIn('prompt "Select mode for System Services"', kconfig)
        self.assertIn('default FEATURE_SYSTEM_SSH', kconfig)
        self.assertIn('menu "Optional Container Platform add-ons"', kconfig)
        self.assertIn('depends on PLATFORM_QEMU_AARCH64', kconfig)
        # dependencies should generate 'depends on', not 'select'
        self.assertIn('depends on FEATURE_SYSTEM', kconfig)
        self.assertIn('if FEATURE_CONTAINERS', kconfig)
        self.assertIn('if FEATURE_SYSTEM', kconfig)
        self.assertIn('config FEATURE_CONTAINERS_PODMAN', kconfig)
        if_block_start = kconfig.index('    if FEATURE_CONTAINERS')
        podman_pos = kconfig.index('    config FEATURE_CONTAINERS_PODMAN')
        endif_pos = kconfig.index('    endif', podman_pos)
        self.assertTrue(if_block_start < podman_pos < endif_pos)


class SelectSemanticTest(unittest.TestCase):
    """Tests that verify Kconfig 'select' semantics work correctly.

    These tests use kconfiglib to load the generated Kconfig and verify that
    when a feature is selected, its dependencies (via 'selects') are automatically
    enabled as per Kconfig semantics.
    """

    def tearDown(self):
        if hasattr(self, '_workspace_to_cleanup'):
            self._workspace_to_cleanup.cleanup()

    def _build_kconfig_with_features(
        self, features: dict[str, list[tuple[str, str]]]
    ) -> Kconfig:
        """Build a Kconfig object with custom features.

        Args:
            features: A dict mapping category to list of (filename, content) tuples.

        Returns:
            A kconfiglib Kconfig object loaded with the generated Kconfig file.
        """
        # Create workspace and setup directories
        workspace = tempfile.TemporaryDirectory()
        base = Path(workspace.name)
        nightly_dir = base / 'nightly-features'
        platform_dir = base / 'platform'
        platform_dir.mkdir(parents=True)
        (platform_dir / 'qemu-aarch64.yaml').write_text('')

        # Write feature files
        for category, files in features.items():
            for filename, content in files:
                (nightly_dir / category).mkdir(parents=True, exist_ok=True)
                target = nightly_dir / category / f'{filename}.yaml'
                target.write_text(content)

        # Build Kconfig text
        registry = FeatureRegistry(nightly_dir)
        generator = NeoMenuconfigGenerator(
            registry=registry,
            platform_dir=platform_dir,
            default_platform='qemu-aarch64',
        )
        kconfig_text = generator.build_kconfig_text()

        # Write Kconfig to file and load with kconfiglib
        kconfig_file = base / 'Kconfig'
        kconfig_file.write_text(kconfig_text)

        # Suppress warnings and load
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            kconf = Kconfig(str(kconfig_file), warn_to_stderr=False)

        # Store workspace for cleanup
        self._workspace_to_cleanup = workspace
        return kconf

    def test_basic_select_auto_enables_dependency(self):
        """Test that selecting a feature auto-enables its 'selects' dependency.

        Scenario:
        - feature_a: selects: [feature_b]
        - When FEATURE_A is set to 'y', FEATURE_B should automatically become 'y'
        """
        kconf = self._build_kconfig_with_features({
            'test': [
                ('base', textwrap.dedent('''\
                    id: base
                    name: Base Feature
                    machines:
                      - qemu-aarch64
                    ''')),
                ('dependent', textwrap.dedent('''\
                    id: dependent
                    name: Dependent Feature
                    machines:
                      - qemu-aarch64
                    selects:
                      - test/base
                    ''')),
            ],
        })

        # Initially, both should be 'n' (not set)
        self.assertEqual(kconf.syms['FEATURE_TEST_BASE'].str_value, 'n')
        self.assertEqual(kconf.syms['FEATURE_TEST_DEPENDENT'].str_value, 'n')

        # When we set FEATURE_TEST_DEPENDENT to 'y'
        kconf.syms['FEATURE_TEST_DEPENDENT'].set_value('y')

        # FEATURE_TEST_BASE should be automatically enabled via 'select'
        self.assertEqual(kconf.syms['FEATURE_TEST_DEPENDENT'].str_value, 'y',
                         'DEPENDENT should be enabled')
        self.assertEqual(kconf.syms['FEATURE_TEST_BASE'].str_value, 'y',
                         'BASE should be auto-enabled via select')

    def test_nested_select_transitive_dependency(self):
        """Test that 'select' is transitive across multiple levels.

        Scenario:
        - feature_a: selects: [feature_b]
        - feature_b: selects: [feature_c]
        - When FEATURE_A is set to 'y', both FEATURE_B and FEATURE_C should be 'y'
        """
        kconf = self._build_kconfig_with_features({
            'test': [
                ('base', textwrap.dedent('''\
                    id: base
                    name: Base Feature
                    machines:
                      - qemu-aarch64
                    ''')),
                ('middle', textwrap.dedent('''\
                    id: middle
                    name: Middle Feature
                    machines:
                      - qemu-aarch64
                    selects:
                      - test/base
                    ''')),
                ('top', textwrap.dedent('''\
                    id: top
                    name: Top Feature
                    machines:
                      - qemu-aarch64
                    selects:
                      - test/middle
                    ''')),
            ],
        })

        # Set TOP to 'y'
        kconf.syms['FEATURE_TEST_TOP'].set_value('y')

        # All three should be enabled due to transitive select
        self.assertEqual(kconf.syms['FEATURE_TEST_TOP'].str_value, 'y')
        self.assertEqual(kconf.syms['FEATURE_TEST_MIDDLE'].str_value, 'y',
                         'MIDDLE should be auto-enabled via select from TOP')
        self.assertEqual(kconf.syms['FEATURE_TEST_BASE'].str_value, 'y',
                         'BASE should be auto-enabled via select from MIDDLE')

    def test_select_with_dependencies_and_nested_subfeatures(self):
        """Test a complex scenario mimicking mcs/xen -> hypervisor/xen.

        Scenario:
        - hypervisor/xen: Base hypervisor feature
        - mcs (category): Has sub_feat xen
        - mcs/xen: selects: [hypervisor/xen]
        - When mcs/xen is selected, hypervisor/xen should be auto-enabled
        """
        kconf = self._build_kconfig_with_features({
            'hypervisor': [
                ('xen', textwrap.dedent('''\
                    id: xen
                    name: Xen Hypervisor
                    prompt: Xen hypervisor support
                    machines:
                      - qemu-aarch64
                    ''')),
            ],
            'mcs': [
                ('mcs', textwrap.dedent('''\
                    id: mcs
                    name: MCS Feature
                    prompt: MCS support
                    machines:
                      - qemu-aarch64
                    sub_feats:
                      - id: xen
                        name: MCS Xen
                        selects:
                          - hypervisor/xen
                    ''')),
            ],
        })

        # Initially, hypervisor/xen should not be enabled
        self.assertEqual(kconf.syms['FEATURE_HYPERVISOR_XEN'].str_value, 'n')

        # Enable mcs/xen (note: need to enable parent mcs first due to depends on)
        kconf.syms['FEATURE_MCS'].set_value('y')
        kconf.syms['FEATURE_MCS_XEN'].set_value('y')

        # hypervisor/xen should be auto-enabled via select
        self.assertEqual(kconf.syms['FEATURE_MCS_XEN'].str_value, 'y',
                         'MCS_XEN should be enabled')
        self.assertEqual(kconf.syms['FEATURE_HYPERVISOR_XEN'].str_value, 'y',
                         'HYPERVISOR_XEN should be auto-enabled via select from MCS_XEN')

    def test_select_with_one_of_choice_interaction(self):
        """Test that 'select' works correctly with one_of/choice constructs.

        Scenario:
        - base: has one_of with [opt_a, opt_b]
        - consumer: selects: [base]
        - When consumer is enabled, base should be enabled
        - The one_of default should be selected
        """
        kconf = self._build_kconfig_with_features({
            'test': [
                ('base', textwrap.dedent('''\
                    id: base
                    name: Base Feature
                    machines:
                      - qemu-aarch64
                    sub_feats:
                      - id: opt_a
                        name: Option A
                      - id: opt_b
                        name: Option B
                    one_of:
                      - self/opt_a
                      - self/opt_b
                    default_one_of: self/opt_a
                    ''')),
                ('consumer', textwrap.dedent('''\
                    id: consumer
                    name: Consumer Feature
                    machines:
                      - qemu-aarch64
                    selects:
                      - test/base
                    ''')),
            ],
        })

        # Enable consumer
        kconf.syms['FEATURE_TEST_CONSUMER'].set_value('y')

        # base should be auto-enabled
        self.assertEqual(kconf.syms['FEATURE_TEST_BASE'].str_value, 'y',
                         'BASE should be auto-enabled via select')

        # one_of default (opt_a) should be selected
        self.assertEqual(kconf.syms['FEATURE_TEST_BASE_OPT_A'].str_value, 'y',
                         'BASE_OPT_A (default) should be selected')

    def test_multiple_selects_enables_all_dependencies(self):
        """Test that a feature with multiple 'selects' enables all of them.

        Scenario:
        - dep_a, dep_b, dep_c: Independent dependency features
        - aggregator: selects: [dep_a, dep_b, dep_c]
        - When aggregator is enabled, all three dependencies should be enabled
        """
        kconf = self._build_kconfig_with_features({
            'test': [
                ('dep_a', textwrap.dedent('''\
                    id: dep_a
                    name: Dependency A
                    machines:
                      - qemu-aarch64
                    ''')),
                ('dep_b', textwrap.dedent('''\
                    id: dep_b
                    name: Dependency B
                    machines:
                      - qemu-aarch64
                    ''')),
                ('dep_c', textwrap.dedent('''\
                    id: dep_c
                    name: Dependency C
                    machines:
                      - qemu-aarch64
                    ''')),
                ('aggregator', textwrap.dedent('''\
                    id: aggregator
                    name: Aggregator Feature
                    machines:
                      - qemu-aarch64
                    selects:
                      - test/dep_a
                      - test/dep_b
                      - test/dep_c
                    ''')),
            ],
        })

        # Enable aggregator
        kconf.syms['FEATURE_TEST_AGGREGATOR'].set_value('y')

        # All dependencies should be auto-enabled
        self.assertEqual(kconf.syms['FEATURE_TEST_DEP_A'].str_value, 'y',
                         'DEP_A should be auto-enabled')
        self.assertEqual(kconf.syms['FEATURE_TEST_DEP_B'].str_value, 'y',
                         'DEP_B should be auto-enabled')
        self.assertEqual(kconf.syms['FEATURE_TEST_DEP_C'].str_value, 'y',
                         'DEP_C should be auto-enabled')


if __name__ == '__main__':
    unittest.main()
