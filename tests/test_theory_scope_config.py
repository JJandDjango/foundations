"""Scope-config contract for the theory package.

The packaged default scope is the generic ``["**"]`` — every commit is
in scope until a repo narrows it with its own ``theory.config.yaml``.
(The origin harness shipped its repo-specific globs as the package default;
the extraction into foundations replaced them with the generic default —
consumer knowledge must not live in package defaults.)

Covers:
- packaged YAML default == Python dataclass default (EM-SYNC-MISMATCH guard)
- evaluate_scope semantics under ["**"] (everything matches, empty list doesn't)
- a narrowed repo-style config still scopes precisely
- public import contract
"""
from __future__ import annotations

from theory.config import _DEFAULT_CONFIG_PATH


class TestPackagedDefaultScope:
    """The packaged default scope is exactly ["**"], YAML and Python in sync."""

    def test_packaged_yaml_scope_is_everything(self) -> None:
        from theory import load_config
        assert load_config(_DEFAULT_CONFIG_PATH).scope == ["**"]

    def test_python_default_scope_is_everything(self) -> None:
        from theory import TheoryConfig
        assert TheoryConfig().scope == ["**"]

    def test_yaml_and_python_defaults_in_sync(self) -> None:
        """EM-SYNC-MISMATCH: packaged YAML and dataclass defaults must agree."""
        from theory import TheoryConfig, load_config
        yaml_cfg = load_config(_DEFAULT_CONFIG_PATH)
        py_cfg = TheoryConfig()
        assert yaml_cfg.scope == py_cfg.scope
        assert yaml_cfg.mode == py_cfg.mode
        assert yaml_cfg.trivial_classes == py_cfg.trivial_classes
        assert yaml_cfg.banned_phrases == py_cfg.banned_phrases
        assert yaml_cfg.min_length == py_cfg.min_length
        assert yaml_cfg.trivial_max_lines == py_cfg.trivial_max_lines
        assert yaml_cfg.map.path == py_cfg.map.path
        assert yaml_cfg.map.reconcile == py_cfg.map.reconcile


class TestEvaluateScopeUnderDefault:
    """Under ["**"] everything is in scope; only an empty change-set is not."""

    def test_root_file_matches(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(["README.md"], ["**"]) is True

    def test_nested_path_matches(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(["src/pkg/module.py"], ["**"]) is True

    def test_empty_changed_files_does_not_match(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope([], ["**"]) is False


class TestNarrowedRepoConfig:
    """A repo-style narrowed scope still evaluates precisely."""

    _REPO_SCOPE = ["src/**", "designs/**", "THEORY.md", "MAP.md"]

    def test_in_scope_glob_matches(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(["src/app/main.py"], self._REPO_SCOPE) is True

    def test_root_governance_file_matches_exactly(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(["THEORY.md"], self._REPO_SCOPE) is True

    def test_bare_glob_does_not_match_nested_copy(self) -> None:
        """'THEORY.md' is a root-level exact glob; 'docs/THEORY.md' must not match."""
        from theory import evaluate_scope
        assert evaluate_scope(["docs/THEORY.md"], self._REPO_SCOPE) is False

    def test_out_of_scope_file_does_not_match(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(["STATE.md"], self._REPO_SCOPE) is False


class TestImportContract:
    """Public contract symbols importable without error."""

    def test_load_config_importable(self) -> None:
        from theory import load_config  # noqa: F401
        assert callable(load_config)

    def test_theory_config_importable(self) -> None:
        from theory import TheoryConfig  # noqa: F401
        assert callable(TheoryConfig)

    def test_evaluate_scope_importable(self) -> None:
        from theory import evaluate_scope  # noqa: F401
        assert callable(evaluate_scope)

    def test_load_config_returns_theory_config_instance(self) -> None:
        from theory import TheoryConfig, load_config
        assert isinstance(load_config(_DEFAULT_CONFIG_PATH), TheoryConfig)
