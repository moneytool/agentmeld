import pytest

from agentmeld.transform import frontmatter as fm


def test_split_returns_mapping_and_body():
    front, body = fm.split("---\ndescription: hi\nglobs:\n  - src/**\n---\n\nBody\n")
    assert front == {"description": "hi", "globs": ["src/**"]}
    assert body == "Body\n"


def test_split_without_frontmatter():
    assert fm.split("just a body\n") == ({}, "just a body\n")


def test_crlf_is_normalised():
    front, body = fm.split("---\r\na: 1\r\n---\r\nbody\r\n")
    assert front == {"a": 1}
    assert "\r" not in body


def test_render_is_idempotent():
    original = fm.render({"a": 1, "b": ["x"]}, "text")
    assert fm.render(*fm.split(original)) == original


def test_render_preserves_key_order():
    assert fm.render({"z": 1, "a": 2}, "b").index("z") < fm.render({"z": 1, "a": 2}, "b").index("a")


def test_unterminated_block_raises():
    with pytest.raises(fm.FrontmatterError):
        fm.split("---\nbroken: yes\n")


def test_non_mapping_frontmatter_raises():
    with pytest.raises(fm.FrontmatterError):
        fm.split("---\n- a\n- b\n---\nx\n")


class TestMapKeys:
    def test_rename(self):
        assert fm.map_keys({"globs": ["a"]}, {"globs": "applyTo"}) == {"applyTo": ["a"]}

    def test_drop(self):
        assert fm.map_keys({"description": "d"}, {"description": fm.DROP}) == {}

    def test_comma_join(self):
        out = fm.map_keys({"globs": ["a", "b"]}, {"globs": "applyTo:comma"})
        assert out == {"applyTo": "a, b"}

    def test_flag_literal_wins_over_rename(self):
        out = fm.map_keys(
            {"globs": ["src/**"], "always": True},
            {"globs": "applyTo:comma", "always": "applyTo!**"},
        )
        assert out == {"applyTo": "**"}

    def test_falsey_flag_leaves_rename_intact(self):
        out = fm.map_keys(
            {"globs": ["src/**"], "always": False},
            {"globs": "applyTo:comma", "always": "applyTo!**"},
        )
        assert out == {"applyTo": "src/**"}

    def test_unmapped_canonical_key_is_dropped(self):
        assert fm.map_keys({"model": "opus"}, {}) == {}

    def test_unknown_user_key_passes_through(self):
        assert fm.map_keys({"mine": 1}, {}) == {"mine": 1}

    def test_defaults_do_not_override(self):
        out = fm.map_keys({"always": True}, {"always": "alwaysApply!true"}, {"alwaysApply": False})
        assert out == {"alwaysApply": True}
