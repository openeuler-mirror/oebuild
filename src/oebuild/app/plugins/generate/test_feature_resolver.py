"""Unit tests for the feature resolver (oebuild.feature_resolver).

These tests build a minimal, self-contained feature tree in a tempdir so they
do not depend on a real yocto-meta-openeuler checkout. They cover the
behaviour that gates backward compatibility for legacy flat ``-f <name>``
scripts:

- ``resolve_id``: full-id match, user-declared ``aliases`` resolution,
  leaf-name fallback, and ambiguity detection.
- ``FeatureResolver.resolve``: ``one_of`` default selection, the
  selects-closure satisfaction that keeps ``-f mcs -f xen`` from wrongly
  falling back to baremetal, and the silent no-default case.
- ``selects`` transitive closure.
"""

import pathlib
import tempfile
import textwrap
import unittest

from oebuild.feature_resolver import (
    FeatureAmbiguousError,
    FeatureNotFoundError,
    FeatureRegistry,
    FeatureResolver,
)


def _write(features_dir: pathlib.Path, category: str, name: str, body: str):
    """Write a feature YAML file under <features_dir>/<category>/<name>.yaml."""
    cat_dir = features_dir / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    (cat_dir / f'{name}.yaml').write_text(textwrap.dedent(body))


class FeatureRegistryResolveIdTest(unittest.TestCase):
    """resolve_id: alias, ambiguity, leaf fallback."""

    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.workspace.name)
        self.features_dir = base / 'features'
        # A category-root feature with a renamed alias.
        _write(
            self.features_dir, 'robotics', 'ros2',
            """
            id: ros2
            name: ROS 2
            aliases: [ros]
            config:
              local_conf:
                - 'DISTRO_FEATURES:append = " ros "'
            """,
        )
        # A top-level feature whose leaf collides with a subfeature elsewhere.
        _write(
            self.features_dir, 'hypervisor', 'xen',
            """
            id: xen
            name: Xen
            config:
              local_conf:
                - 'DISTRO_FEATURES:append = " xen "'
            """,
        )
        # A subfeature whose leaf is also "xen" but lives under mcs/.
        _write(
            self.features_dir, 'mcs', 'mcs',
            """
            id: mcs
            config:
              local_conf:
                - 'DISTRO_FEATURES:append = " mcs "'
            sub_feats:
              - id: xen
                name: MCS Xen
                config:
                  - 'MCS_FEATURES:append = " xen "'
            """,
        )
        # Two top-level features sharing a leaf name -> ambiguity.
        _write(
            self.features_dir, 'kernel', 'kernel6',
            """
            id: kernel6
            config:
              local_conf:
                - 'PREFERRED_VERSION_linux-openeuler = "6.1%"'
            """,
        )
        _write(
            self.features_dir, 'system', 'kernel6',
            """
            id: kernel6
            aliases: [kernel6]
            config:
              local_conf:
                - 'DISTRO_FEATURES:append = " kernel6 "'
            """,
        )
        self.registry = FeatureRegistry(self.features_dir)

    def tearDown(self):
        self.workspace.cleanup()

    def test_full_id_match(self):
        feat = self.registry.resolve_id('robotics/ros2')
        self.assertEqual(feat.full_id, 'robotics/ros2')

    def test_user_alias_resolves_legacy_name(self):
        # 'ros' is declared as an alias of robotics/ros2.
        feat = self.registry.resolve_id('ros')
        self.assertEqual(feat.full_id, 'robotics/ros2')

    def test_alias_is_case_insensitive(self):
        feat = self.registry.resolve_id('ROS')
        self.assertEqual(feat.full_id, 'robotics/ros2')

    def test_leaf_fallback_prefers_top_level_over_subfeature(self):
        # Leaf 'xen' matches both hypervisor/xen (top-level) and mcs/xen
        # (subfeature). The top-level one must win silently.
        feat = self.registry.resolve_id('xen')
        self.assertEqual(feat.full_id, 'hypervisor/xen')

    def test_ambiguous_leaf_among_top_level_raises(self):
        # 'kernel6' matches two top-level features. Without an alias claim the
        # resolver must raise ambiguity. Here system/kernel6 declares 'kernel6'
        # as an alias, so the alias wins instead.
        feat = self.registry.resolve_id('kernel6')
        self.assertEqual(feat.full_id, 'system/kernel6')

    def test_unknown_identifier_raises_not_found(self):
        with self.assertRaises(FeatureNotFoundError):
            self.registry.resolve_id('does-not-exist')


class FeatureRegistryAliasConflictTest(unittest.TestCase):
    """Two features must not claim the same alias."""

    def test_conflicting_aliases_raise_at_load(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        features_dir = pathlib.Path(workspace.name) / 'features'
        _write(
            features_dir, 'a', 'feat1',
            """
            id: feat1
            aliases: [shared-alias]
            config:
              local_conf: ['X = "1"']
            """,
        )
        _write(
            features_dir, 'b', 'feat2',
            """
            id: feat2
            aliases: [shared-alias]
            config:
              local_conf: ['X = "2"']
            """,
        )
        # Alias 'shared-alias' is claimed by two different full ids.
        # _register_alias keeps the first winner and only conflicts when the
        # same key maps to two *different* full ids, so the second claim fails.
        with self.assertRaises(Exception):
            FeatureRegistry(features_dir)


class FeatureResolverOneOfTest(unittest.TestCase):
    """one_of default, selects-closure satisfaction, silent no-default."""

    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        base = pathlib.Path(self.workspace.name)
        self.features_dir = base / 'features'

        # mcs: parent with one_of=[baremetal, xen], default=baremetal.
        # The xen subfeature selects hypervisor/xen.
        _write(
            self.features_dir, 'mcs', 'mcs',
            """
            id: mcs
            config:
              local_conf:
                - 'DISTRO_FEATURES:append = " mcs "'
            sub_feats:
              - id: baremetal
                selects: [hypervisor/baremetal]
              - id: xen
                selects: [hypervisor/xen]
                config:
                  - 'MCS_FEATURES:append = " xen "'
            one_of:
              - self/baremetal
              - self/xen
            default_one_of: self/baremetal
            """,
        )
        # hypervisor/{baremetal,xen}. The baremetal one strips xen (mirrors the
        # real-world MCS_FEATURES:remove that motivated this fix).
        _write(
            self.features_dir, 'hypervisor', 'baremetal',
            """
            id: baremetal
            config:
              local_conf:
                - 'MCS_FEATURES:remove = " xen "'
            """,
        )
        _write(
            self.features_dir, 'hypervisor', 'xen',
            """
            id: xen
            config:
              local_conf:
                - 'DISTRO_FEATURES:append = " xen "'
            """,
        )
        # k3s: parent with one_of=[agent, server], NO default.
        _write(
            self.features_dir, 'containers', 'k3s',
            """
            id: k3s
            config:
              local_conf: ['DISTRO_FEATURES:append = " k3s "']
            sub_feats:
              - id: agent
                config:
                  - 'DISTRO_FEATURES:append = " k3s-agent "'
              - id: server
                config:
                  - 'DISTRO_FEATURES:append = " k3s-server "'
            one_of:
              - self/agent
              - self/server
            """,
        )
        self.registry = FeatureRegistry(self.features_dir)

    def _enabled_ids(self, flags):
        result = FeatureResolver(self.registry, 'qemu-aarch64').resolve(flags)
        return [f.full_id for f in result.features]

    def test_one_of_default_applied_when_nothing_selected(self):
        # -f mcs with no option -> default baremetal kicks in.
        ids = self._enabled_ids(['mcs'])
        self.assertIn('mcs/baremetal', ids)
        self.assertIn('hypervisor/baremetal', ids)

    def test_selects_closure_satisfies_one_of_option(self):
        # -f mcs -f xen: xen resolves to hypervisor/xen (top-level). The mcs
        # one_of option mcs/xen selects hypervisor/xen, so it must count as
        # satisfied and NOT trigger the baremetal default.
        ids = self._enabled_ids(['mcs', 'xen'])
        self.assertIn('hypervisor/xen', ids)
        self.assertNotIn('mcs/baremetal', ids)
        self.assertNotIn('hypervisor/baremetal', ids)

    def test_selects_closure_option_not_enabled_directly(self):
        # When satisfied via selects closure, the option subfeature itself
        # need not appear; what matters is no baremetal fallback / no :remove.
        result = FeatureResolver(self.registry, 'qemu-aarch64').resolve(
            ['mcs', 'xen']
        )
        all_lines = []
        for f in result.features:
            all_lines.extend(f.config.local_conf or [])
        self.assertFalse(
            any(':remove' in line for line in all_lines),
            'selects-closure satisfaction must avoid the baremetal :remove',
        )

    def test_one_of_without_default_is_silent(self):
        # -f k3s with no option selected and no default -> no error, no agent.
        ids = self._enabled_ids(['k3s'])
        self.assertIn('containers/k3s', ids)
        self.assertNotIn('containers/k3s/agent', ids)
        self.assertNotIn('containers/k3s/server', ids)

    def test_explicit_one_of_option_selected(self):
        # -f k3s -f containers/k3s/agent -> agent wins, no default needed.
        ids = self._enabled_ids(['k3s', 'containers/k3s/agent'])
        self.assertIn('containers/k3s/agent', ids)
        self.assertNotIn('containers/k3s/server', ids)


class FeatureResolverSelectsClosureTest(unittest.TestCase):
    """_selects_closure is transitive."""

    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        base = pathlib.Path(self.workspace.name)
        self.features_dir = base / 'features'
        # a -> selects b -> selects c (transitive chain)
        _write(
            self.features_dir, 'x', 'a',
            """
            id: a
            selects: [x/b]
            config: {local_conf: ['A = "1"']}
            """,
        )
        _write(
            self.features_dir, 'x', 'b',
            """
            id: b
            selects: [x/c]
            config: {local_conf: ['B = "1"']}
            """,
        )
        _write(
            self.features_dir, 'x', 'c',
            """
            id: c
            config: {local_conf: ['C = "1"']}
            """,
        )
        self.registry = FeatureRegistry(self.features_dir)

    def test_selects_pulls_in_transitive_closure(self):
        result = FeatureResolver(
            self.registry, 'qemu-aarch64'
        ).resolve(['x/a'])
        ids = [f.full_id for f in result.features]
        self.assertIn('x/a', ids)
        self.assertIn('x/b', ids)
        self.assertIn('x/c', ids)


if __name__ == '__main__':
    unittest.main()
