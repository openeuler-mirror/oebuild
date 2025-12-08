"""
Menuconfig generator for neo-generate nightly features.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List, Optional

from kconfiglib import Kconfig
from menuconfig import menuconfig

import oebuild.util as oebuild_util
from oebuild.nightly_features import Feature, FeatureRegistry


@dataclass(frozen=True)
class MenuconfigSelection:
    """Result set produced by a completed menuconfig session."""

    platform: str
    """Machine name currently selected."""

    features: List[str]
    """Full feature IDs that ended up enabled."""


class NeoMenuconfigGenerator:
    """Builds a nightly-feature menuconfig that mirrors the catalog hierarchy."""

    PLATFORM_PREFIX = 'PLATFORM_'
    FEATURE_PREFIX = 'FEATURE_'

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
        self._emitted_features: set[str] = set()

    def run_menuconfig(self) -> Optional[MenuconfigSelection]:
        """Generate a Kconfig, run menuconfig, and translate the selections."""
        kconfig_text = self.build_kconfig_text()
        with tempfile.TemporaryDirectory() as tmpdir:
            kconfig_path = Path(tmpdir, 'Kconfig')
            kconfig_path.write_text(kconfig_text, encoding='utf-8')
            kconf = Kconfig(str(kconfig_path))
            previous_style = os.environ.get('MENUCONFIG_STYLE')
            os.environ['MENUCONFIG_STYLE'] = 'aquatic selection=fg:white,bg:blue'

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
                except OSError:
                    pass

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
        self._emitted_features.clear()
        lines: List[str] = [
            '# Auto-generated nightly-feature menuconfig',
            '# Updating this file manually is not supported.',
            '',
        ]
        lines += self._platform_block()
        lines.append('')
        lines += self._features_block()
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

    def _platform_block(self) -> List[str]:
        block = ['menu "Platform"']
        block.append('choice')
        block.append('    prompt "Select target platform"')
        default_symbol = self._symbol_for_platform(self.default_platform)
        block.append(f'    default {default_symbol}')
        for machine in self.platforms:
            symbol = self._symbol_for_platform(machine)
            block.append(f'    config {symbol}')
            block.append(f'        bool "{machine}"')
            self.platform_symbol_map[symbol] = machine
        block.append('endchoice')
        block.append('endmenu')
        return block

    def _features_block(self) -> List[str]:
        lines: List[str] = ['menu "Nightly Features"']
        for category, features in self._root_features_by_category():
            lines.append(f'menu "{self._format_category_label(category)}"')
            for feature in features:
                lines += self._emit_feature_block(feature, indent=1)
            lines.append('endmenu')
            lines.append('')
        lines.append('endmenu')
        return lines

    def _root_features_by_category(self):
        grouped: Dict[str, List[Feature]] = {}
        for feature in self.registry.features_by_full_id.values():
            if feature.is_subfeature:
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

    def _emit_feature_block(
        self,
        feature: Feature,
        indent: int,
    ) -> List[str]:
        if feature.full_id in self._emitted_features:
            return []
        self._emitted_features.add(feature.full_id)
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
        selects = sorted(set(feature.selects))
        for selects_id in selects:
            lines.append(
                f'{prefix}    select {self._symbol_for_feature(selects_id)}'
            )
        lines.append('')
        lines += self._emit_subfeature_sections(feature, indent + 1)
        return lines

    def _emit_subfeature_sections(
        self, feature: Feature, indent: int
    ) -> List[str]:
        lines: List[str] = []
        prefix = '    ' * indent
        one_of_children = sorted(feature.one_of)
        if one_of_children:
            lines.append(f'{prefix}choice')
            lines.append(
                f'{prefix}    prompt "Select mode for {feature.name}"'
            )
            lines.append(
                f'{prefix}    depends on {self._symbol_for_feature(feature.full_id)}'
            )
            if feature.default_one_of:
                lines.append(
                    f'{prefix}    default {self._symbol_for_feature(feature.default_one_of)}'
                )
            lines.append('')
            for child_id in one_of_children:
                child = self.registry.features_by_full_id.get(child_id)
                if child is None:
                    continue
                lines += self._emit_feature_block(child, indent + 1)
            lines.append(f'{prefix}endchoice')
            lines.append('')
        choice_children = sorted(feature.choice)
        if choice_children:
            lines.append(f'{prefix}menu "Optional {feature.name} add-ons"')
            for child_id in choice_children:
                child = self.registry.features_by_full_id.get(child_id)
                if child is None:
                    continue
                lines += self._emit_feature_block(child, indent + 1)
            lines.append(f'{prefix}endmenu')
            lines.append('')
        remaining_children = [
            child_id
            for child_id in feature.child_full_ids
            if child_id not in one_of_children
            and child_id not in choice_children
        ]
        for child_id in sorted(remaining_children):
            child = self.registry.features_by_full_id.get(child_id)
            if child is None:
                continue
            lines += self._emit_feature_block(child, indent + 1)
        return lines

    def _build_help(self, feature: Feature) -> List[str]:
        help_lines: List[str] = []
        if feature.prompt:
            help_lines += feature.prompt.strip().splitlines()
        if feature.machines:
            help_lines.append(
                f'Supports: {", ".join(feature.machines)}'
            )
        if feature.dependencies:
            help_lines.append(
                'Depends on: ' + ', '.join(sorted(feature.dependencies))
            )
        return help_lines

    def _build_dependency_expression(self, feature: Feature) -> Optional[str]:
        terms: List[str] = []
        if feature.parent_full_id:
            terms.append(self._symbol_for_feature(feature.parent_full_id))
        for dependency in sorted(set(feature.dependencies)):
            terms.append(self._symbol_for_feature(dependency))
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
        return MenuconfigSelection(
            platform=selected_platform,
            features=selected_features,
        )

    def _symbol_for_feature(self, full_id: str) -> str:
        normalized = re.sub(r'[^A-Z0-9]', '_', full_id.upper())
        return f'{self.FEATURE_PREFIX}{normalized}'

    def _symbol_for_platform(self, machine: str) -> str:
        normalized = re.sub(r'[^A-Z0-9]', '_', machine.upper())
        symbol = f'{self.PLATFORM_PREFIX}{normalized}'
        self.platform_symbol_map.setdefault(symbol, machine)
        return symbol

    def _escape(self, value: str) -> str:
        return value.replace('"', '\\"')

    def _format_category_label(self, category: str) -> str:
        return category.replace('_', ' ').title()
