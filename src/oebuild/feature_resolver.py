"""
Helper classes for loading and resolving feature YAML declarations.

The loader builds a global registry keyed by full IDs (<category>/<leaf>[/<sub>]),
and the resolver walks the dependency graph, enforces visibility rules, and
outputs the deterministic set to inject into ParseTemplate.
"""

from __future__ import annotations

import pathlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

import oebuild.util as oebuild_util


class FeatureError(Exception):
    """Base error for feature parsing and resolution."""  # noqa: D401


class ResolutionError(FeatureError):
    """Raised when the resolver cannot satisfy a requested feature merge."""  # noqa: D401


class ConflictError(ResolutionError):
    """Raised when conflicting features are enabled simultaneously."""


class FeatureNotFoundError(ResolutionError):
    """Raised when a requested feature identifier cannot be resolved."""


class FeatureAmbiguousError(ResolutionError):
    """Raised when a feature identifier matches multiple candidates."""


@dataclass
class FeatureConfig:
    # frequently used fields
    repos: List[str] = field(default_factory=list)
    layers: List[str] = field(default_factory=list)
    local_conf: List[str] = field(default_factory=list)
    # Store any additional config fields
    other_fields: Dict[str, any] = field(default_factory=dict)


@dataclass
class Feature:
    category: str
    leaf_id: str
    full_id: str
    name: str
    prompt: Optional[str]
    machines: Optional[List[str]]
    machine_set: Optional[Set[str]]
    dependencies: List[str]
    selects: List[str]
    one_of: List[str]
    default_one_of: Optional[str]
    choice: List[str]
    config: FeatureConfig
    parent_full_id: Optional[str]
    child_full_ids: List[str] = field(default_factory=list)
    is_subfeature: bool = False
    aliases: List[str] = field(default_factory=list)

    def supports_machine(self, machine: str) -> bool:
        normalized = machine.strip().lower()
        if self.machine_set and normalized not in self.machine_set:
            return False
        return True


@dataclass
class ResolutionResult:
    features: List[Feature]


class FeatureRegistry:
    """Indexes features defined under .oebuild/<feat_root_dir>."""

    def __init__(self, features_dir_path: pathlib.Path):
        self.features_dir = pathlib.Path(features_dir_path)
        if not self.features_dir.exists():
            raise FeatureError(
                f'Feature directory not found: {self.features_dir}'
            )
        self.features_by_full_id: Dict[str, Feature] = {}
        self.leaf_index: Dict[str, List[Feature]] = defaultdict(list)
        self.features_with_one_of: List[Feature] = []
        self.category_roots: Dict[str, Feature] = {}
        self.long_alias_index: Dict[str, Feature] = {}
        self._load_features()
        self._compute_category_roots()
        self._build_long_alias_index()
        self._validate_refs()
        self._apply_machine_constraints()

    # a demo logic,
    # we need more effective approach to load features
    def _load_features(self) -> None:
        for category_dir in sorted(self.features_dir.iterdir()):
            if not category_dir.is_dir():
                continue
            category = category_dir.name.strip()
            if not category:
                continue
            for feature_file in sorted(category_dir.iterdir()):
                if not feature_file.is_file():
                    continue
                if feature_file.suffix not in ('.yaml', '.yml'):
                    continue
                data = oebuild_util.read_yaml(feature_file)
                if not isinstance(data, dict):
                    raise FeatureError(
                        f'{feature_file} must contain at least one YAML mapping'
                    )
                self._parse_feature_file(category, data, feature_file)

    def _parse_feature_file(
        self,
        category: str,
        data: dict,
        origin: pathlib.Path,
    ) -> None:
        leaf_id = self._normalize_leaf(data.get('id'))
        if not leaf_id:
            raise FeatureError(f'{origin}: missing feature "id" field')
        if leaf_id == 'self':
            raise FeatureError(f'{origin}: feature "id" may not be "self"')
        full_id = self._make_full_id(category, leaf_id)
        config = self._parse_config(data.get('config'))
        machines, machine_set = self._parse_machines(data.get('machines'))
        feature = Feature(
            category=category,
            leaf_id=leaf_id,
            full_id=full_id,
            name=str(data.get('name') or leaf_id),
            prompt=data.get('prompt'),
            machines=machines,
            machine_set=machine_set,
            dependencies=self._normalize_ref_list(
                data.get('dependencies'), full_id
            ),
            selects=self._normalize_ref_list(data.get('selects'), full_id),
            one_of=self._normalize_ref_list(data.get('one_of'), full_id),
            default_one_of=self._normalize_ref(
                data.get('default_one_of'), full_id
            )
            if data.get('default_one_of')
            else None,
            choice=self._normalize_ref_list(data.get('choice'), full_id),
            config=config,
            parent_full_id=None,
            is_subfeature=False,
            aliases=self._parse_aliases(data.get('aliases'), origin),
        )
        self._register_feature(feature)
        sub_feats = data.get('sub_feats') or []
        if not isinstance(sub_feats, list):
            raise FeatureError(f'{origin}: "sub_feats" must be a sequence')
        for sub in sub_feats:
            if not isinstance(sub, dict):
                raise FeatureError(
                    f'{origin}: each entry of "sub_feats" must be a mapping'
                )
            self._parse_sub_feature(feature, sub, origin)

    def _parse_sub_feature(
        self, parent: Feature, data: dict, origin: pathlib.Path
    ) -> None:
        if 'sub_feats' in data:
            raise FeatureError(
                f'{origin}: sub-features may not define nested "sub_feats"'
            )
        sub_id = self._normalize_leaf(data.get('id'))
        if not sub_id:
            raise FeatureError(f'{origin}: sub-feature is missing "id"')
        if sub_id == 'self':
            raise FeatureError(
                f'{origin}: sub-feature "id" may not be "self"'
            )
        # Apply syntax sugar for sub-features: if parent is a category root feature,
        # sub-feature full_id should be parent.category/sub_id instead of parent.full_id/sub_id
        if parent.category == parent.leaf_id:
            full_id = f'{parent.category}/{sub_id}'
        else:
            full_id = f'{parent.full_id}/{sub_id}'
        config = self._parse_config(data.get('config'))
        machines, machine_set = self._parse_machines(data.get('machines'))
        feature = Feature(
            category=parent.category,
            leaf_id=sub_id,
            full_id=full_id,
            name=str(data.get('name') or sub_id),
            prompt=data.get('prompt'),
            machines=machines,
            machine_set=machine_set,
            dependencies=self._normalize_ref_list(
                data.get('dependencies'), full_id
            ),
            selects=self._normalize_ref_list(data.get('selects'), full_id),
            one_of=self._normalize_ref_list(data.get('one_of'), full_id),
            default_one_of=self._normalize_ref(
                data.get('default_one_of'), full_id
            )
            if data.get('default_one_of')
            else None,
            choice=self._normalize_ref_list(data.get('choice'), full_id),
            config=config,
            parent_full_id=parent.full_id,
            is_subfeature=True,
            aliases=self._parse_aliases(data.get('aliases'), origin),
        )
        self._register_feature(feature)
        parent.child_full_ids.append(feature.full_id)

    def _parse_config(self, config_block: Optional[dict]) -> FeatureConfig:
        """
        _parse_config() will normalize three most frequently used fields:
        * repos
        * layers
        * local_conf

        Fourtunetly, for other fields, which are all defined as a simple k:v map, hence just load them directly
        """
        if not isinstance(config_block, dict):
            config_block = {}

        repos = self._normalize_sequence(
            config_block.get('repos', config_block.get('repo'))
        )
        layers = self._normalize_sequence(config_block.get('layers'))
        local_conf = self._normalize_local_conf(config_block.get('local_conf'))

        other_fields = {}
        for key, value in config_block.items():
            if key not in ('repos', 'layers', 'local_conf'):
                other_fields[key] = value

        return FeatureConfig(
            repos=repos,
            layers=layers,
            local_conf=local_conf,
            other_fields=other_fields,
        )

    def _parse_machines(
        self, value
    ) -> Tuple[Optional[List[str]], Optional[Set[str]]]:
        if value is None:
            return None, None
        if isinstance(value, str):
            normalized = [value.strip()]
        elif isinstance(value, Iterable):
            normalized = [
                str(item).strip() for item in value if item is not None
            ]
        else:
            normalized = [str(value).strip()]
        normalized = [m for m in normalized if m]
        if not normalized:
            return None, None
        return normalized, {m.lower() for m in normalized}

    def _parse_aliases(
        self, value, origin: pathlib.Path
    ) -> List[str]:
        """Parse the optional top-level ``aliases`` field into normalized ids.

        Aliases are plain alternative identifiers (e.g. legacy flat feature
        names), not feature references, so they are only lowercased/stripped
        like ``_normalize_identifier`` instead of going through ref resolution.
        """
        if value is None:
            return []
        if isinstance(value, str):
            raw = [value]
        elif isinstance(value, Iterable):
            raw = list(value)
        else:
            raise FeatureError(
                f'{origin}: "aliases" must be a string or a sequence of strings'
            )
        aliases: List[str] = []
        for item in raw:
            if item is None:
                continue
            normalized = self._normalize_identifier(str(item))
            if not normalized:
                continue
            if normalized not in aliases:
                aliases.append(normalized)
        return aliases

    def _normalize_sequence(self, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, Iterable):
            return [str(item) for item in value if item is not None]
        return [str(value)]

    def _normalize_local_conf(self, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, Iterable):
            return [str(item) for item in value if item is not None]
        return [str(value)]

    def _normalize_ref_list(self, entries, parent_full_id: str) -> List[str]:
        if entries is None:
            return []
        if isinstance(entries, str):
            entries = [entries]
        if not isinstance(entries, Iterable):
            return []
        normalized = []
        for entry in entries:
            if entry is None:
                continue
            normalized.append(self._normalize_ref(entry, parent_full_id))
        return normalized

    def _normalize_ref(self, entry, parent_full_id: str) -> str:
        value = str(entry).strip()
        if not value:
            raise FeatureError(f'Empty reference found in {parent_full_id}')
        if value == 'self':
            return parent_full_id
        if value.startswith('self/'):
            remainder = value[5:].strip()
            if not remainder:
                raise FeatureError(
                    f'Invalid self reference "{value}" in {parent_full_id}'
                )
            value = f'{parent_full_id}/{remainder}'
        return self._normalize_identifier(value)

    def _register_feature(self, feature: Feature) -> None:
        if feature.full_id in self.features_by_full_id:
            raise FeatureError(
                f'Duplicate feature id detected: {feature.full_id}'
            )
        self.features_by_full_id[feature.full_id] = feature
        self.leaf_index[feature.leaf_id].append(feature)
        if feature.one_of:
            self.features_with_one_of.append(feature)

    def _make_full_id(self, category: str, leaf_id: str) -> str:
        # Apply syntax sugar rule: when category equals leaf_id,
        # the feature becomes the category root feature with full_id = category
        if category == leaf_id:
            return category
        return f'{category}/{leaf_id}'

    def _normalize_leaf(self, value) -> str:
        if value is None:
            return ''
        return str(value).strip().lower()

    def _normalize_identifier(self, value: str) -> str:
        return value.strip().lower()

    def _build_long_alias_index(self) -> None:
        for root in self.category_roots.values():
            long_root = f'{root.category}/{root.leaf_id}'
            self._register_alias(self.long_alias_index, long_root, root)
            for child_id in root.child_full_ids:
                child = self.features_by_full_id.get(child_id)
                if child is None:
                    continue
                long_child = f'{root.category}/{root.leaf_id}/{child.leaf_id}'
                self._register_alias(self.long_alias_index, long_child, child)
        # User-declared aliases (e.g. legacy flat feature names) are registered
        # after the path-derived aliases so that a data author can map an old
        # identifier to a renamed feature. _register_alias keeps the first
        # winner, so path aliases take precedence over aliases declared later.
        for feature in self.features_by_full_id.values():
            for alias in feature.aliases:
                self._register_alias(
                    self.long_alias_index, alias, feature
                )

    def _register_alias(
        self, alias_map: Dict[str, Feature], key: str, feature: Feature
    ) -> None:
        if key in alias_map and alias_map[key].full_id != feature.full_id:
            raise FeatureError(
                f'Ambiguous alias "{key}" for '
                f'{alias_map[key].full_id} and {feature.full_id}'
            )
        alias_map[key] = feature

    def _validate_refs(self) -> None:
        for feature in self.features_by_full_id.values():
            feature.dependencies = self._canonicalize_reference_list(
                feature, feature.dependencies
            )
            feature.selects = self._canonicalize_reference_list(
                feature, feature.selects
            )
            feature.one_of = self._canonicalize_reference_list(
                feature, feature.one_of
            )
            feature.choice = self._canonicalize_reference_list(
                feature, feature.choice
            )
            if feature.default_one_of:
                feature.default_one_of = self._canonicalize_ref(
                    feature, feature.default_one_of
                )

    def _canonicalize_reference_list(
        self, feature: Feature, entries: List[str]
    ) -> List[str]:
        return [self._canonicalize_ref(feature, entry) for entry in entries]

    def _canonicalize_ref(self, feature: Feature, entry: str) -> str:
        if entry in self.features_by_full_id:
            return entry
        try:
            resolved = self.resolve_id(entry)
        except ResolutionError as err:
            raise FeatureError(
                f'{feature.full_id} references unknown feature {entry}'
            ) from err
        return resolved.full_id

    def _apply_machine_constraints(self) -> None:
        cache: Dict[str, Optional[Set[str]]] = {}

        def compute(feature: Feature) -> Optional[Set[str]]:
            if feature.full_id in cache:
                return cache[feature.full_id]
            candidate_sets: List[Optional[Set[str]]] = []
            if feature.machine_set is not None:
                candidate_sets.append(set(feature.machine_set))
            if feature.parent_full_id:
                parent_feature = self.features_by_full_id[
                    feature.parent_full_id
                ]
                candidate_sets.append(compute(parent_feature))
            for dep_id in feature.dependencies:
                dep_feature = self.features_by_full_id[dep_id]
                candidate_sets.append(compute(dep_feature))
            result = self._intersect_machine_sets(candidate_sets)
            cache[feature.full_id] = result
            feature.machine_set = result
            if result is None:
                feature.machines = (
                    feature.machines if feature.machines else None
                )
            else:
                feature.machines = sorted(result)
            return result

        for feature_obj in list(self.features_by_full_id.values()):
            compute(feature_obj)

    def _intersect_machine_sets(
        self, sets: List[Optional[Set[str]]]
    ) -> Optional[Set[str]]:
        result: Optional[Set[str]] = None
        for entry in sets:
            if entry is None:
                continue
            if result is None:
                result = set(entry)
            else:
                result &= entry
            if result is not None and not result:
                break
        if result is None:
            return None
        return set(result)

    def _compute_category_roots(self) -> None:
        for feature in self.features_by_full_id.values():
            if (
                not feature.is_subfeature
                and feature.category == feature.leaf_id
            ):
                self.category_roots[feature.category] = feature

    def _raise_ambiguity(
        self, identifier: str, candidates: List[Feature]
    ) -> None:
        lines = [
            f"[Error] Ambiguous feature ID: '{identifier}'",
            'Candidates:',
        ]
        for candidate in candidates:
            lines.append(f'  - {candidate.full_id}')
        if candidates:
            lines.append(
                f'Please use the Full ID (e.g., -f {candidates[0].full_id}).'
            )
        raise FeatureAmbiguousError('\n'.join(lines))

    def _match_leaf_candidates(
        self, identifier: str, leaf_candidates: List[Feature]
    ) -> Optional[Feature]:
        if not leaf_candidates:
            return None
        if len(leaf_candidates) == 1:
            return leaf_candidates[0]
        top_level = [feat for feat in leaf_candidates if not feat.is_subfeature]
        if len(top_level) == 1:
            return top_level[0]
        if top_level:
            self._raise_ambiguity(identifier, top_level)
        sub_candidates = [
            feat for feat in leaf_candidates if feat.is_subfeature
        ]
        if len(sub_candidates) == 1:
            return sub_candidates[0]
        if sub_candidates:
            self._raise_ambiguity(identifier, sub_candidates)
        return None

    def resolve_id(self, identifier: str) -> Feature:
        normalized = self._normalize_identifier(identifier)

        full_match = self.features_by_full_id.get(normalized)
        if full_match:
            if (
                full_match.category == full_match.leaf_id
                and '/' not in normalized
            ):
                leaf_candidates = self.leaf_index.get(normalized, [])
                leaf_match = self._match_leaf_candidates(
                    identifier, leaf_candidates
                )
                if leaf_match and leaf_match.full_id != full_match.full_id:
                    self._raise_ambiguity(identifier, [full_match, leaf_match])
            return full_match

        alias_match = self.long_alias_index.get(normalized)
        if alias_match:
            return alias_match

        leaf_key = normalized.split('/')[-1]
        leaf_candidates = self.leaf_index.get(leaf_key, [])
        leaf_match = self._match_leaf_candidates(identifier, leaf_candidates)
        if leaf_match:
            return leaf_match

        raise FeatureNotFoundError(
            f"Unknown feature '{identifier}'. Use --list to see available features."
        )

    def list_features(self) -> List[Feature]:
        return sorted(
            self.features_by_full_id.values(), key=lambda feat: feat.full_id
        )


class FeatureResolver:
    """Resolves machine-aware dependency trees for features."""

    def __init__(self, registry: FeatureRegistry, machine: str):
        self.registry = registry
        self.machine = machine.strip()
        self.enabled: Dict[str, Feature] = {}
        self.enabled_order: List[str] = []
        self.explicit_features: Set[str] = set()
        self._visiting: Set[str] = set()
        self._context_stack: List[tuple[Feature, str]] = []

    def resolve(self, requested: Iterable[str]) -> ResolutionResult:
        for identifier in requested or []:
            feature = self.registry.resolve_id(identifier)
            self._enable_feature(feature, source='user')
        self._resolve_one_of_groups()
        return ResolutionResult(
            features=[self.enabled[full_id] for full_id in self.enabled_order]
        )

    def _enable_feature(self, feature: Feature, source: str) -> None:
        if feature.full_id in self.enabled:
            return
        if feature.full_id in self._visiting:
            self._raise_cycle_error(feature)
        self._visiting.add(feature.full_id)
        frame = (feature, source)
        self._context_stack.append(frame)
        try:
            self._ensure_machine_support(feature)
            self.enabled[feature.full_id] = feature
            self.enabled_order.append(feature.full_id)
            if source == 'user':
                self.explicit_features.add(feature.full_id)
            for dependency in feature.dependencies:
                dep_feature = self.registry.features_by_full_id[dependency]
                self._enable_feature(dep_feature, source='dependency')
            for selection in feature.selects:
                sel_feature = self.registry.features_by_full_id[selection]
                self._enable_feature(sel_feature, source='select')
            if feature.is_subfeature and feature.parent_full_id:
                parent_feature = self.registry.features_by_full_id[
                    feature.parent_full_id
                ]
                self._enable_feature(parent_feature, source='parent')
        finally:
            self._context_stack.pop()
            self._visiting.discard(feature.full_id)

    def _raise_cycle_error(self, feature: Feature) -> None:
        chain = [
            frame_feature.full_id for frame_feature, _ in self._context_stack
        ]
        chain.append(feature.full_id)
        detail = ' -> '.join(chain)
        raise ResolutionError(f'[Error] Circular dependency detected: {detail}')

    def _ensure_machine_support(self, feature: Feature) -> None:
        current = feature
        while current:
            if (
                current.machine_set
                and self.machine.lower() not in current.machine_set
            ):
                self._raise_machine_error(current)
            if not current.parent_full_id:
                break
            current = self.registry.features_by_full_id[current.parent_full_id]

    def _raise_machine_error(self, feature: Feature) -> None:
        trace_lines = []
        reason_labels = {
            'user': 'Requested',
            'dependency': 'Dependency',
            'select': 'Selected',
            'parent': 'Parent',
            'default': 'Default',
        }
        detail_labels = {
            'user': ' (User Input)',
            'select': ' (Auto Select)',
            'dependency': ' (Dependency)',
            'parent': ' (Parent Auto)',
            'default': ' (Default)',
        }
        for frame_feature, source in self._context_stack:
            label = reason_labels.get(source, 'Activated')
            detail = detail_labels.get(source, '')
            trace_lines.append(f'  - {label}: {frame_feature.full_id}{detail}')
        machines = (
            f'[{", ".join(feature.machines)}]' if feature.machines else '[]'
        )
        lines = [
            f"[Error] Feature '{feature.full_id}' is not supported on machine "
            f"'{self.machine}'.",
            'Trace:',
            *trace_lines,
            f'  - Constraint: {feature.leaf_id} requires machine {machines}',
        ]
        raise ResolutionError('\n'.join(lines))

    def _resolve_one_of_groups(self) -> None:
        changed = True
        while changed:
            changed = False
            for feature in self.registry.features_with_one_of:
                if feature.full_id not in self.enabled:
                    continue
                if not feature.one_of:
                    continue
                selected = [
                    option
                    for option in feature.one_of
                    if self._is_one_of_option_satisfied(option)
                ]
                if len(selected) > 1:
                    self._raise_one_of_conflict(feature, selected)
                if not selected and feature.default_one_of:
                    default_id = feature.default_one_of
                    if default_id not in self.enabled:
                        default_feature = self.registry.features_by_full_id[
                            default_id
                        ]
                        self._enable_feature(default_feature, source='default')
                        changed = True

    def _is_one_of_option_satisfied(self, option_full_id: str) -> bool:
        """Whether a one_of option counts as already chosen.

        An option is satisfied when it is enabled directly, OR when something
        the user explicitly requested is part of the option's ``selects``
        closure. The second case matters for backward compatibility: a legacy
        ``-f xen`` resolves to ``hypervisor/xen`` (a top-level feature) while
        the parent ``mcs`` one_of option is ``mcs/xen`` (a subfeature that
        ``selects`` ``hypervisor/xen``). Without this check the resolver would
        see no one_of option selected and wrongly fall back to the baremetal
        default, which then strips ``xen`` from MCS_FEATURES.
        """
        if option_full_id in self.enabled:
            return True
        option = self.registry.features_by_full_id.get(option_full_id)
        if option is None:
            return False
        return bool(
            self._selects_closure(option) & self.explicit_features
        )

    def _selects_closure(self, feature: Feature) -> Set[str]:
        """Transitive set of full ids reachable via ``selects`` edges."""
        seen: Set[str] = set()
        stack = list(feature.selects)
        while stack:
            current_id = stack.pop()
            if current_id in seen:
                continue
            seen.add(current_id)
            current = self.registry.features_by_full_id.get(current_id)
            if current is not None:
                stack.extend(current.selects)
        return seen

    def _raise_one_of_conflict(
        self, feature: Feature, selected: List[str]
    ) -> None:
        leaf_names = [
            self.registry.features_by_full_id[opt].leaf_id for opt in selected
        ]
        if len(leaf_names) == 2 and all(
            opt in self.explicit_features for opt in selected
        ):
            detail = 'You requested both '
        else:
            detail = 'These options '
        detail += "'" + "' and '".join(leaf_names) + "'" if leaf_names else ''
        raise ConflictError(
            f"[Error] Conflict in feature '{feature.full_id}':\n"
            f"{detail} cannot be enabled together (one_of)."
        )
