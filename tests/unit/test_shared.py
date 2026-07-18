"""
tests/unit/test_shared.py — Unit tests for econflow.commands._shared.

Covers:
- STATUS_ICONS contains all five expected keys with Rich markup
- deep_get navigates nested dicts correctly
- deep_get returns None on missing keys or non-dict intermediates
- load_yaml_safe loads a valid YAML file
- load_yaml_safe returns (None, error) on missing file
- load_yaml_safe returns (None, error) on YAML parse error
- load_yaml_safe returns (None, error) when YAML is not a dict
"""

from __future__ import annotations

from pathlib import Path

from econflow.commands._shared import STATUS_ICONS, deep_get, load_yaml_safe

# ---------------------------------------------------------------------------
# STATUS_ICONS
# ---------------------------------------------------------------------------

class TestStatusIcons:
    def test_has_all_five_statuses(self) -> None:
        for key in ("pass", "warn", "fail", "skip", "info"):
            assert key in STATUS_ICONS, f"Missing status key: {key!r}"

    def test_pass_contains_checkmark(self) -> None:
        assert "✔" in STATUS_ICONS["pass"]

    def test_warn_contains_warning_symbol(self) -> None:
        assert "⚠" in STATUS_ICONS["warn"]

    def test_fail_contains_cross(self) -> None:
        assert "✘" in STATUS_ICONS["fail"]

    def test_all_values_are_strings(self) -> None:
        for key, val in STATUS_ICONS.items():
            assert isinstance(val, str), f"STATUS_ICONS[{key!r}] is not a str"

    def test_pass_has_green_markup(self) -> None:
        assert "green" in STATUS_ICONS["pass"]

    def test_warn_has_yellow_markup(self) -> None:
        assert "yellow" in STATUS_ICONS["warn"]

    def test_fail_has_red_markup(self) -> None:
        assert "red" in STATUS_ICONS["fail"]

    def test_info_has_blue_markup(self) -> None:
        assert "blue" in STATUS_ICONS["info"]


# ---------------------------------------------------------------------------
# deep_get
# ---------------------------------------------------------------------------

class TestDeepGet:
    def test_single_key(self) -> None:
        assert deep_get({"a": 1}, "a") == 1

    def test_nested_two_levels(self) -> None:
        assert deep_get({"a": {"b": 2}}, "a", "b") == 2

    def test_nested_three_levels(self) -> None:
        data = {"x": {"y": {"z": "found"}}}
        assert deep_get(data, "x", "y", "z") == "found"

    def test_missing_key_returns_none(self) -> None:
        assert deep_get({"a": 1}, "b") is None

    def test_missing_nested_key_returns_none(self) -> None:
        assert deep_get({"a": {"b": 1}}, "a", "c") is None

    def test_non_dict_intermediate_returns_none(self) -> None:
        # "a" maps to a string, not a dict — second key navigation must return None
        assert deep_get({"a": "string"}, "a", "b") is None

    def test_none_value_is_returned(self) -> None:
        assert deep_get({"a": None}, "a") is None

    def test_empty_dict(self) -> None:
        assert deep_get({}, "a") is None

    def test_no_keys_returns_root(self) -> None:
        data = {"a": 1}
        assert deep_get(data) is data

    def test_list_value_preserved(self) -> None:
        data = {"a": {"b": [1, 2, 3]}}
        assert deep_get(data, "a", "b") == [1, 2, 3]

    def test_zero_value_not_confused_with_none(self) -> None:
        assert deep_get({"a": {"b": 0}}, "a", "b") == 0

    def test_false_value_not_confused_with_none(self) -> None:
        assert deep_get({"a": {"b": False}}, "a", "b") is False


# ---------------------------------------------------------------------------
# load_yaml_safe
# ---------------------------------------------------------------------------

class TestLoadYamlSafe:
    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "config.yaml"
        p.write_text("key: value\nnested:\n  a: 1\n", encoding="utf-8")
        data, err = load_yaml_safe(p)
        assert err == ""
        assert data == {"key": "value", "nested": {"a": 1}}

    def test_missing_file_returns_none_and_error(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.yaml"
        data, err = load_yaml_safe(p)
        assert data is None
        assert "not found" in err.lower() or "File not found" in err

    def test_invalid_yaml_returns_none_and_error(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("key: [\nunclosed bracket", encoding="utf-8")
        data, err = load_yaml_safe(p)
        assert data is None
        assert "YAML" in err or "parse" in err.lower()

    def test_yaml_that_is_not_a_dict_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n", encoding="utf-8")
        data, err = load_yaml_safe(p)
        assert data is None
        assert err != ""

    def test_empty_yaml_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        data, err = load_yaml_safe(p)
        assert data is None

    def test_valid_yaml_returns_empty_error_string(self, tmp_path: Path) -> None:
        p = tmp_path / "ok.yaml"
        p.write_text("a: 1\n", encoding="utf-8")
        data, err = load_yaml_safe(p)
        assert err == ""

    def test_yaml_with_unicode(self, tmp_path: Path) -> None:
        p = tmp_path / "unicode.yaml"
        p.write_text("name: \"Ångström\"\nvalue: 42\n", encoding="utf-8")
        data, err = load_yaml_safe(p)
        assert data is not None
        assert data["name"] == "Ångström"
