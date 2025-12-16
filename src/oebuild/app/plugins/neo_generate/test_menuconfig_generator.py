import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

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
        self.assertIn('select FEATURE_SYSTEM', kconfig)
        self.assertIn('if FEATURE_CONTAINERS', kconfig)
        self.assertIn('if FEATURE_SYSTEM', kconfig)
        self.assertIn('config FEATURE_CONTAINERS_PODMAN', kconfig)
        if_block_start = kconfig.index('    if FEATURE_CONTAINERS')
        podman_pos = kconfig.index('    config FEATURE_CONTAINERS_PODMAN')
        endif_pos = kconfig.index('    endif', podman_pos)
        self.assertTrue(if_block_start < podman_pos < endif_pos)


if __name__ == '__main__':
    unittest.main()
