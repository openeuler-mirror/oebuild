"""
Menuconfig generator for generate features.
"""

from __future__ import annotations

import os
import re
import tempfile
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
from oebuild.app.plugins.generate.kconfig_writer import KconfigWriter
from oebuild.feature_resolver import Feature, FeatureRegistry


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


class MenuconfigGenerator:
    """Builds a feature menuconfig that mirrors the catalog hierarchy."""

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
                    warnings.warn(
                        f'Failed to delete temporary config file {saved_filename[0]}: {e}'
                    )

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
        writer = KconfigWriter()
        writer.line('# Auto-generated feature menuconfig')
        writer.line('# Updating this file manually is not supported.')
        writer.blank()
        self._write_platform_choice(writer)
        writer.blank()
        self._write_features(writer)
        writer.blank()
        self._write_common_options(writer)
        if not writer.validate():
            raise RuntimeError(
                f'Kconfig writer validation failed: {writer.errors()}'
            )
        return writer.text()

    def _list_platforms(self) -> List[str]:
        result = []
        for entry in sorted(self.platform_dir.iterdir()):
            if not entry.is_file():
                continue
            if entry.suffix not in ('.yaml', '.yml'):
                continue
            result.append(entry.stem)
        return result

    def _write_platform_choice(self, writer: KconfigWriter) -> None:
        default_symbol = self._symbol_for_platform(self.default_platform)
        writer.choice(prompt='Select target platform', default=default_symbol)
        for machine in self.platforms:
            symbol = self._symbol_for_platform(machine)
            writer.config(symbol, prompt=machine)
            self.platform_symbol_map[symbol] = machine
        writer.end_choice()

    def _write_common_options(self, writer: KconfigWriter) -> None:
        writer.choice(
            prompt='Select build environment', default='BUILD_IN-DOCKER'
        )
        writer.config('BUILD_IN-DOCKER', prompt='docker')
        writer.config('BUILD_IN-HOST', prompt='host')
        writer.end_choice()
        writer.blank()

        writer.config(
            'COMMON_NO-FETCH',
            prompt='no_fetch (disable source fetching)',
            default='n',
        )
        writer.blank()

        writer.config(
            'COMMON_NO-LAYER',
            prompt='no_layer (skip layer repo update on env setup)',
            default='n',
        )
        writer.blank()

        writer.config(
            'COMMON_SSTATE-MIRRORS',
            prompt='SSTATE_MIRRORS value',
            type_='string',
            default='""',
        )
        writer.blank()

        writer.config(
            'COMMON_SSTATE-DIR',
            prompt='SSTATE_DIR path',
            type_='string',
            default='""',
        )
        writer.blank()

        writer.config(
            'COMMON_TMP-DIR',
            prompt='TMPDIR path',
            type_='string',
            default='""',
            depends_on='BUILD_IN-HOST',
        )
        writer.blank()

        writer.config(
            'COMMON_TOOLCHAIN-DIR',
            prompt='toolchain_dir (External GCC toolchain directory [your own toolchain])',
            type_='string',
            default='""',
        )
        writer.blank()

        writer.config(
            'COMMON_LLVM-TOOLCHAIN-DIR',
            prompt='llvm_toolchain_dir (External LLVM toolchain directory [your own toolchain])',
            type_='string',
            default='""',
        )
        writer.blank()

        writer.config(
            'COMMON_NATIVESDK-DIR',
            prompt='nativesdk_dir (External nativesdk directory [used when building on host])',
            type_='string',
            default='""',
            depends_on='BUILD_IN-HOST',
        )
        writer.blank()

        writer.config(
            'COMMON_DATETIME',
            prompt='datetime',
            type_='string',
            default='""',
        )
        writer.blank()

        writer.config(
            'COMMON_CACHE_SRC_DIR',
            prompt='cache_src_dir (src directory)',
            type_='string',
            default='""',
        )
        writer.blank()

        writer.config(
            'COMMON_DIRECTORY',
            prompt='directory (build directory name)',
            type_='string',
            default='""',
        )

    def _write_features(self, writer: KconfigWriter) -> None:
        writer.menu('Select Features', indent_body=False)
        emitted_features: set[str] = set()
        for category, features in self._root_features_by_category():
            writer.menu(
                self._format_category_label(category), indent_body=False
            )
            writer.indent()
            for feature in features:
                self._emit_feature_block(writer, feature, 1, emitted_features)
            writer.dedent()
            writer.end_menu()
            writer.blank()
        writer.end_menu()

    def _root_features_by_category(self):
        grouped: Dict[str, List[Feature]] = {}
        for feature in self.registry.features_by_full_id.values():
            if feature.is_subfeature:
                continue
            # Note: We no longer skip _dependency_child_ids here.
            # Features that depend on other root features should still be emitted
            # as root features, not skipped. This prevents circular dependencies.
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
        writer: KconfigWriter,
        feature: Feature,
        depth: int,
        emitted_features: set[str],
    ) -> None:
        if depth > self.MAX_RECURSION_DEPTH:
            raise RuntimeError(
                f'Recursion depth exceeded for feature {feature.full_id}. '
                f'Maximum allowed depth is {self.MAX_RECURSION_DEPTH}.'
            )
        if feature.full_id in emitted_features:
            return
        emitted_features.add(feature.full_id)
        symbol = self._symbol_for_feature(feature.full_id)
        self.feature_symbol_map[symbol] = feature.full_id
        help_lines = self._build_help(feature)
        depends_expr = self._build_dependency_expression(feature)
        selects = [
            self._symbol_for_feature(selects_id)
            for selects_id in self._sorted_selects(feature.full_id)
        ]
        writer.config(
            symbol,
            prompt=feature.name,
            depends_on=depends_expr,
            select=selects,
            help_lines=help_lines,
        )
        writer.blank()
        self._emit_subfeature_sections(writer, feature, depth, emitted_features)

    def _emit_subfeature_sections(
        self,
        writer: KconfigWriter,
        feature: Feature,
        depth: int,
        emitted_features: set[str],
    ) -> None:
        one_of_children = self._sorted_one_of(feature.full_id)
        choice_children = self._sorted_choice(feature.full_id)
        sorted_child_ids = self._sorted_child_ids(feature.full_id)
        remaining_children = [
            child_id
            for child_id in sorted_child_ids
            if child_id not in one_of_children
            and child_id not in choice_children
        ]
        # Note: We do NOT include _dependency_children here to avoid circular dependencies.
        # Features that depend on this feature should be emitted as independent features
        # with their own 'depends on' statements, not wrapped in this feature's 'if' block.
        if not (one_of_children or choice_children or remaining_children):
            return
        parent_symbol = self._symbol_for_feature(feature.full_id)
        writer.if_(parent_symbol)
        if one_of_children:
            writer.choice(
                prompt=f'Select mode for {feature.name}',
                depends_on=parent_symbol,
                default=(
                    self._symbol_for_feature(feature.default_one_of)
                    if feature.default_one_of
                    else None
                ),
            )
            writer.blank()
            for child_id in one_of_children:
                child = self.registry.features_by_full_id.get(child_id)
                if child is None:
                    continue
                self._emit_feature_block(
                    writer, child, depth + 1, emitted_features
                )
            writer.end_choice()
            writer.blank()
        if choice_children:
            writer.menu(f'Optional {feature.name} add-ons')
            for child_id in choice_children:
                child = self.registry.features_by_full_id.get(child_id)
                if child is None:
                    continue
                self._emit_feature_block(
                    writer, child, depth + 1, emitted_features
                )
            writer.end_menu()
            writer.blank()
        for child_id in remaining_children:
            child = self.registry.features_by_full_id.get(child_id)
            if child is None:
                continue
            self._emit_feature_block(writer, child, depth + 1, emitted_features)
        writer.end_if()
        writer.blank()

    def _build_help(self, feature: Feature) -> List[str]:
        help_lines: List[str] = []
        if feature.prompt:
            help_lines += feature.prompt.strip().splitlines()
        if feature.machines:
            help_lines.append(f'Supports: {", ".join(feature.machines)}')
        if feature.dependencies:
            help_lines.append(
                'Depends on: '
                + ', '.join(self._sorted_dependencies(feature.full_id))
            )
        return help_lines

    def _build_dependency_expression(self, feature: Feature) -> Optional[str]:
        terms: List[str] = []
        if feature.parent_full_id:
            terms.append(self._symbol_for_feature(feature.parent_full_id))
        # Add non-parent, non-child dependencies from feature.dependencies
        # Note: We exclude parent_full_id and child_full_ids to avoid circular dependencies
        child_ids = set(feature.child_full_ids)
        for dep_id in feature.dependencies:
            if dep_id != feature.parent_full_id and dep_id not in child_ids:
                terms.append(self._symbol_for_feature(dep_id))
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

    def _format_category_label(self, category: str) -> str:
        return category.replace('_', ' ').title()
