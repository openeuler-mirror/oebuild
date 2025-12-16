"""
Menuconfig generator for neo-generate nightly features.
"""

from __future__ import annotations

import os
import re
import tempfile
import textwrap
import warnings
from collections import OrderedDict, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List, Optional

from kconfiglib import Kconfig
from menuconfig import menuconfig

import oebuild.const as oebuild_const
import oebuild.util as oebuild_util
from oebuild.nightly_features import Feature, FeatureRegistry


@dataclass(frozen=True)
class MenuconfigSelection:
    """Result set produced by a completed menuconfig session."""

    platform: str
    """Machine name currently selected."""

    features: List[str]
    """Full feature IDs that ended up enabled."""

    build_in: str
    """Resolved build environment (docker/host)."""

    no_fetch: bool
    """Whether source fetching is disabled."""

    no_layer: bool
    """Whether layer updates are skipped."""

    sstate_mirrors: Optional[str]
    """Optional SSTATE_MIRRORS override."""

    sstate_dir: Optional[str]
    """Optional SSTATE_DIR override."""

    tmp_dir: Optional[str]
    """Optional TMPDIR path for host builds."""

    toolchain_dir: Optional[str]
    """Optional external GCC toolchain path."""

    llvm_toolchain_dir: Optional[str]
    """Optional external LLVM toolchain path."""

    nativesdk_dir: Optional[str]
    """Optional nativesdk root path for host builds."""

    datetime: Optional[str]
    """Optional DATETIME value for local.conf."""

    cache_src_dir: Optional[str]
    """Optional cache_src_dir path override."""

    directory: Optional[str]
    """Optional build directory name override."""


class NeoMenuconfigGenerator:
    """Builds a nightly-feature menuconfig that mirrors the catalog hierarchy."""

    PLATFORM_PREFIX = 'PLATFORM_'
    FEATURE_PREFIX = 'FEATURE_'
    MAX_RECURSION_DEPTH = 20
    BUILD_IN_CHOICES = (
        ('BUILD_IN-DOCKER', oebuild_const.BUILD_IN_DOCKER),
        ('BUILD_IN-HOST', oebuild_const.BUILD_IN_HOST),
    )
    COMMON_STRING_SYMBOLS = OrderedDict(
        [
            ('COMMON_SSTATE-MIRRORS', 'sstate_mirrors'),
            ('COMMON_SSTATE-DIR', 'sstate_dir'),
            ('COMMON_TMP-DIR', 'tmp_dir'),
            ('COMMON_TOOLCHAIN-DIR', 'toolchain_dir'),
            ('COMMON_LLVM-TOOLCHAIN-DIR', 'llvm_toolchain_dir'),
            ('COMMON_NATIVESDK-DIR', 'nativesdk_dir'),
            ('COMMON_DATETIME', 'datetime'),
            ('COMMON_CACHE_SRC_DIR', 'cache_src_dir'),
            ('COMMON_DIRECTORY', 'directory'),
        ]
    )

    def __init__(
        self,
        registry: FeatureRegistry,
        platform_dir: Path,
        default_platform: Optional[str] = None,
    ):
        if not platform_dir.exists() or not platform_dir.is_dir():
            raise ValueError(f'Platform directory not found: {platform_dir}')
        self.registry = registry
        self.platform_dir = platform_dir
        self.platforms = self._list_platforms()
        if not self.platforms:
            raise ValueError(f'No platforms found under {platform_dir}')
        self.default_platform = (
            default_platform
            if default_platform in self.platforms
            else self.platforms[0]
        )
        self.platform_symbol_map: Dict[str, str] = OrderedDict()
        self.feature_symbol_map: Dict[str, str] = OrderedDict()
        self._dependency_children = self._build_dependency_children()
        self._dependency_child_ids = {
            child.full_id
            for children in self._dependency_children.values()
            for child in children
        }
        # Precompute sorted data for all features
        self._sorted_deps_map: Dict[str, List[str]] = {}
        self._sorted_selects_map: Dict[str, List[str]] = {}
        self._sorted_one_of_map: Dict[str, List[str]] = {}
        self._sorted_choice_map: Dict[str, List[str]] = {}
        self._sorted_child_ids_map: Dict[str, List[str]] = {}
        self._feature_to_symbol_map: Dict[str, str] = {}
        self._platform_to_symbol_map: Dict[str, str] = {}

        # Precompute feature data
        for feature in self.registry.features_by_full_id.values():
            full_id = feature.full_id
            # Symbol mapping (forward and reverse)
            normalized = re.sub(r'[^A-Z0-9]', '_', full_id.upper())
            symbol = f'{self.FEATURE_PREFIX}{normalized}'
            self._feature_to_symbol_map[full_id] = symbol
            self.feature_symbol_map[symbol] = full_id
            # Sorted lists
            self._sorted_deps_map[full_id] = sorted(set(feature.dependencies))
            self._sorted_selects_map[full_id] = sorted(set(feature.selects))
            self._sorted_one_of_map[full_id] = sorted(feature.one_of)
            self._sorted_choice_map[full_id] = sorted(feature.choice)
            self._sorted_child_ids_map[full_id] = sorted(feature.child_full_ids)

        # Precompute platform symbol mappings (forward and reverse)
        for machine in self.platforms:
            normalized = re.sub(r'[^A-Z0-9]', '_', machine.upper())
            symbol = f'{self.PLATFORM_PREFIX}{normalized}'
            self._platform_to_symbol_map[machine] = symbol
            self.platform_symbol_map[symbol] = machine

    def run_menuconfig(self) -> Optional[MenuconfigSelection]:
        """Generate a Kconfig, run menuconfig, and translate the selections."""
        kconfig_text = self.build_kconfig_text()
        with tempfile.TemporaryDirectory() as tmpdir:
            kconfig_path = Path(tmpdir, 'Kconfig')
            kconfig_path.write_text(kconfig_text, encoding='utf-8')
            kconf = Kconfig(str(kconfig_path))
            previous_style = os.environ.get('MENUCONFIG_STYLE')
            os.environ['MENUCONFIG_STYLE'] = (
                'aquatic selection=fg:white,bg:blue'
            )

            with self._hook_write_config() as saved_filename:
                try:
                    with oebuild_util.suppress_print():
                        menuconfig(kconf)
                finally:
                    if previous_style is None:
                        os.environ.pop('MENUCONFIG_STYLE', None)
                    else:
                        os.environ['MENUCONFIG_STYLE'] = previous_style

                if saved_filename[0] is None:
                    return None

                selection = self._collect_selections(kconf)

                try:
                    Path(saved_filename[0]).unlink()
                except OSError as e:
                    warnings.warn(f"Failed to delete temporary config file {saved_filename[0]}: {e}")

                return selection

    @staticmethod
    @contextmanager
    def _hook_write_config() -> Generator[list[str | None], None, None]:
        """
        Context manager that hooks Kconfig.write_config to capture saved filename.
        User may save .config as another name, we have to fetch the filename and check the file existance
        If there is no a saved config file, it is considered that user did not wanna create build directory
        """
        import kconfiglib

        saved_filename: list[str | None] = [None]
        original_write_config = kconfiglib.Kconfig.write_config

        def hooked_write_config(self, filename=None, *args, **kwargs):
            result = original_write_config(self, filename, *args, **kwargs)
            if result and 'saved to' in result:
                saved_filename[0] = result.split('saved to ')[-1].strip()
            return result

        kconfiglib.Kconfig.write_config = hooked_write_config

        try:
            yield saved_filename
        finally:
            kconfiglib.Kconfig.write_config = original_write_config

    def build_kconfig_text(self) -> str:
        """Return the textual Kconfig representation without launching menuconfig."""
        lines: List[str] = [
            '# Auto-generated nightly-feature menuconfig',
            '# Updating this file manually is not supported.',
            '',
        ]
        lines += self._platform_choice_block()
        lines.append('')
        lines += self._features_block()
        lines.append('\n')
        lines += self._common_options_block()
        return '\n'.join(lines)

    def _list_platforms(self) -> List[str]:
        result = []
        for entry in sorted(self.platform_dir.iterdir()):
            if not entry.is_file():
                continue
            if entry.suffix not in ('.yaml', '.yml'):
                continue
            result.append(entry.stem)
        return result

    def _platform_choice_block(self) -> List[str]:
        block = ['choice']
        block.append('    prompt "Select target platform"')
        default_symbol = self._symbol_for_platform(self.default_platform)
        block.append(f'    default {default_symbol}')
        for machine in self.platforms:
            symbol = self._symbol_for_platform(machine)
            block.append(f'    config {symbol}')
            block.append(f'        bool "{machine}"')
            self.platform_symbol_map[symbol] = machine
        block.append('endchoice')
        return block

    def _common_options_block(self) -> List[str]:
        block = textwrap.dedent("""
        choice
            prompt "Select build environment"
            default BUILD_IN-DOCKER
            config BUILD_IN-DOCKER
                bool "docker"
            config BUILD_IN-HOST
                bool "host"
        endchoice

        config COMMON_NO-FETCH
            bool "no_fetch (disable source fetching)"
            default n

        config COMMON_NO-LAYER
            bool "no_layer (skip layer repo update on env setup)"
            default n

        config COMMON_SSTATE-MIRRORS
            string "SSTATE_MIRRORS value"
            default ""

        config COMMON_SSTATE-DIR
            string "SSTATE_DIR path"
            default ""

        config COMMON_TMP-DIR
            string "TMPDIR path"
            default ""
            depends on BUILD_IN-HOST

        config COMMON_TOOLCHAIN-DIR
            string "toolchain_dir (External GCC toolchain directory [your own toolchain])"
            default ""

        config COMMON_LLVM-TOOLCHAIN-DIR
            string "llvm_toolchain_dir (External LLVM toolchain directory [your own toolchain])"
            default ""

        config COMMON_NATIVESDK-DIR
            string "nativesdk_dir (External nativesdk directory [used when building on host])"
            default ""
            depends on BUILD_IN-HOST

        config COMMON_DATETIME
            string "datetime"
            default ""

        config COMMON_CACHE_SRC_DIR
            string "cache_src_dir (src directory)"
            default ""

        config COMMON_DIRECTORY
            string "directory (build directory name)"
            default ""
        """)
        return [line for line in block.strip().splitlines()]

    def _features_block(self) -> List[str]:
        lines: List[str] = ['menu "Select Features"']
        emitted_features: set[str] = set()
        for category, features in self._root_features_by_category():
            lines.append(f'menu "{self._format_category_label(category)}"')
            for feature in features:
                lines += self._emit_feature_block(feature, 1, emitted_features)
            lines.append('endmenu')
            lines.append('')
        lines.append('endmenu')
        return lines

    def _root_features_by_category(self):
        grouped: Dict[str, List[Feature]] = {}
        for feature in self.registry.features_by_full_id.values():
            if feature.is_subfeature:
                continue
            if feature.full_id in self._dependency_child_ids:
                continue
            grouped.setdefault(feature.category, []).append(feature)
        sorted_groups = []
        for category in sorted(grouped):
            sorted_groups.append(
                (
                    category,
                    sorted(
                        grouped[category],
                        key=lambda feat: feat.full_id,
                    ),
                )
            )
        return sorted_groups

    def _build_dependency_children(self) -> Dict[str, List[Feature]]:
        # Build mapping from dependency ID to features that depend on it
        dep_to_features: Dict[str, List[Feature]] = defaultdict(list)
        for feature in self.registry.features_by_full_id.values():
            if feature.is_subfeature:
                continue
            for dep_id in feature.dependencies:
                dep_to_features[dep_id].append(feature)

        # Only keep category roots that are dependencies
        result: Dict[str, List[Feature]] = defaultdict(list)
        for parent in self.registry.category_roots.values():
            if parent.full_id in dep_to_features:
                # Filter features that belong to same category
                for feature in dep_to_features[parent.full_id]:
                    if feature.full_id == parent.full_id:
                        continue
                    if feature.category != parent.category:
                        continue
                    result[parent.full_id].append(feature)
                # Sort by full_id for deterministic output
                result[parent.full_id].sort(key=lambda feat: feat.full_id)
        return result

    def _emit_feature_block(
        self,
        feature: Feature,
        indent: int,
        emitted_features: set[str],
    ) -> List[str]:
        if indent > self.MAX_RECURSION_DEPTH:
            raise RuntimeError(
                f"Recursion depth exceeded for feature {feature.full_id}. "
                f"Maximum allowed depth is {self.MAX_RECURSION_DEPTH}."
            )
        if feature.full_id in emitted_features:
            return []
        emitted_features.add(feature.full_id)
        lines: List[str] = []
        prefix = '    ' * indent
        symbol = self._symbol_for_feature(feature.full_id)
        self.feature_symbol_map[symbol] = feature.full_id
        lines.append(f'{prefix}config {symbol}')
        lines.append(f'{prefix}    bool "{self._escape(feature.name)}"')
        help_lines = self._build_help(feature)
        if help_lines:
            lines.append(f'{prefix}    help')
            lines += [f'{prefix}    {line}' for line in help_lines]
        depends_expr = self._build_dependency_expression(feature)
        if depends_expr:
            lines.append(f'{prefix}    depends on {depends_expr}')
        dependencies = self._sorted_dependencies(feature.full_id)
        for dependency_id in dependencies:
            lines.append(
                f'{prefix}    select {self._symbol_for_feature(dependency_id)}'
            )
        selects = self._sorted_selects(feature.full_id)
        for selects_id in selects:
            lines.append(
                f'{prefix}    select {self._symbol_for_feature(selects_id)}'
            )
        lines.append('')
        lines += self._emit_subfeature_sections(feature, indent, emitted_features)
        return lines

    def _emit_subfeature_sections(
        self, feature: Feature, indent: int, emitted_features: set[str]
    ) -> List[str]:
        child_lines: List[str] = []
        child_prefix = '    ' * (indent + 1)
        one_of_children = self._sorted_one_of(feature.full_id)
        if one_of_children:
            child_lines.append(f'{child_prefix}choice')
            child_lines.append(
                f'{child_prefix}    prompt "Select mode for {feature.name}"'
            )
            child_lines.append(
                f'{child_prefix}    depends on {self._symbol_for_feature(feature.full_id)}'
            )
            if feature.default_one_of:
                child_lines.append(
                    f'{child_prefix}    default {self._symbol_for_feature(feature.default_one_of)}'
                )
            child_lines.append('')
            for child_id in one_of_children:
                child = self.registry.features_by_full_id.get(child_id)
                if child is None:
                    continue
                child_lines += self._emit_feature_block(child, indent + 1, emitted_features)
            child_lines.append(f'{child_prefix}endchoice')
            child_lines.append('')
        choice_children = self._sorted_choice(feature.full_id)
        if choice_children:
            child_lines.append(
                f'{child_prefix}menu "Optional {feature.name} add-ons"'
            )
            for child_id in choice_children:
                child = self.registry.features_by_full_id.get(child_id)
                if child is None:
                    continue
                child_lines += self._emit_feature_block(child, indent + 1, emitted_features)
            child_lines.append(f'{child_prefix}endmenu')
            child_lines.append('')
        sorted_child_ids = self._sorted_child_ids(feature.full_id)
        remaining_children = [
            child_id
            for child_id in sorted_child_ids
            if child_id not in one_of_children
            and child_id not in choice_children
        ]
        for child_id in remaining_children:
            child = self.registry.features_by_full_id.get(child_id)
            if child is None:
                continue
            child_lines += self._emit_feature_block(child, indent + 1, emitted_features)
        for child in self._dependency_children.get(feature.full_id, []):
            child_lines += self._emit_feature_block(child, indent + 1, emitted_features)
        if not child_lines:
            return []
        prefix = '    ' * indent
        return [
            f'{prefix}if {self._symbol_for_feature(feature.full_id)}',
            *child_lines,
            f'{prefix}endif',
            '',
        ]

    def _build_help(self, feature: Feature) -> List[str]:
        help_lines: List[str] = []
        if feature.prompt:
            help_lines += feature.prompt.strip().splitlines()
        if feature.machines:
            help_lines.append(f'Supports: {", ".join(feature.machines)}')
        if feature.dependencies:
            help_lines.append(
                'Depends on: ' + ', '.join(self._sorted_dependencies(feature.full_id))
            )
        return help_lines

    def _build_dependency_expression(self, feature: Feature) -> Optional[str]:
        terms: List[str] = []
        if feature.parent_full_id:
            terms.append(self._symbol_for_feature(feature.parent_full_id))
        machine_expr = self._build_machine_expression(feature)
        if machine_expr:
            if terms:
                machine_expr = f'({machine_expr})'
            terms.append(machine_expr)
        if not terms:
            return None
        return ' && '.join(terms)

    def _build_machine_expression(self, feature: Feature) -> Optional[str]:
        if not feature.machines:
            return None
        symbols = [
            self._symbol_for_platform(machine) for machine in feature.machines
        ]
        return ' || '.join(symbols)

    def _collect_selections(self, kconf: Kconfig) -> MenuconfigSelection:
        syms = {sym.name: sym for sym in kconf.unique_defined_syms}
        selected_platform: Optional[str] = None
        for symbol_name, machine in self.platform_symbol_map.items():
            sym = syms.get(symbol_name)
            if sym and sym.str_value == 'y':
                selected_platform = machine
                break
        selected_features = []
        for symbol_name, full_id in self.feature_symbol_map.items():
            sym = syms.get(symbol_name)
            if sym and sym.str_value == 'y':
                selected_features.append(full_id)
        if selected_platform is None:
            selected_platform = self.default_platform

        def bool_option(symbol_name: str) -> bool:
            sym = syms.get(symbol_name)
            return bool(sym and sym.str_value == 'y')

        def string_option(symbol_name: str) -> Optional[str]:
            sym = syms.get(symbol_name)
            if sym is None or sym.str_value is None:
                return None
            normalized = sym.str_value.strip()
            if not normalized or normalized.lower() == 'none':
                return None
            return normalized

        build_in = oebuild_const.BUILD_IN_DOCKER
        for symbol_name, env_value in self.BUILD_IN_CHOICES:
            if bool_option(symbol_name):
                build_in = env_value
                break

        string_values = {
            attr_name: string_option(symbol_name)
            for symbol_name, attr_name in self.COMMON_STRING_SYMBOLS.items()
        }

        return MenuconfigSelection(
            platform=selected_platform,
            features=selected_features,
            build_in=build_in,
            no_fetch=bool_option('COMMON_NO-FETCH'),
            no_layer=bool_option('COMMON_NO-LAYER'),
            **string_values,
        )

    def _sorted_dependencies(self, full_id: str) -> List[str]:
        return self._sorted_deps_map.get(full_id, [])

    def _sorted_selects(self, full_id: str) -> List[str]:
        return self._sorted_selects_map.get(full_id, [])

    def _sorted_one_of(self, full_id: str) -> List[str]:
        return self._sorted_one_of_map.get(full_id, [])

    def _sorted_choice(self, full_id: str) -> List[str]:
        return self._sorted_choice_map.get(full_id, [])

    def _sorted_child_ids(self, full_id: str) -> List[str]:
        return self._sorted_child_ids_map.get(full_id, [])

    def _symbol_for_feature(self, full_id: str) -> str:
        symbol = self._feature_to_symbol_map.get(full_id)
        if symbol is None:
            # Fallback calculation (should not happen if precomputed)
            normalized = re.sub(r'[^A-Z0-9]', '_', full_id.upper())
            symbol = f'{self.FEATURE_PREFIX}{normalized}'
            self._feature_to_symbol_map[full_id] = symbol
        return symbol

    def _symbol_for_platform(self, machine: str) -> str:
        symbol = self._platform_to_symbol_map.get(machine)
        if symbol is None:
            # Fallback calculation (should not happen if precomputed)
            normalized = re.sub(r'[^A-Z0-9]', '_', machine.upper())
            symbol = f'{self.PLATFORM_PREFIX}{normalized}'
            self._platform_to_symbol_map[machine] = symbol
        return symbol

    def _escape(self, value: str) -> str:
        return value.replace('"', '\\"')

    def _format_category_label(self, category: str) -> str:
        return category.replace('_', ' ').title()
