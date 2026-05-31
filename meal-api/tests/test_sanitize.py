"""Tests for server-side input sanitization (stored-XSS / operator-key guards)."""

import pytest
from src.sanitize import clean_text, reject_operator_keys


class TestCleanText:
    def test_strips_script_tags(self):
        assert clean_text("<script>alert(1)</script>Salt") == "alert(1)Salt"

    def test_strips_img_onerror(self):
        assert clean_text('<img src=x onerror=alert(1)>') == ""

    def test_keeps_plain_text(self):
        assert clean_text("Chicken breast 500g") == "Chicken breast 500g"

    def test_strips_control_chars(self):
        assert clean_text("ab\x00\x07c") == "abc"

    def test_collapses_whitespace_and_trims(self):
        assert clean_text("  too   many   spaces  ") == "too many spaces"

    def test_none_becomes_empty(self):
        assert clean_text(None) == ""

    def test_truncates_to_max_len(self):
        assert len(clean_text("x" * 5000)) == 2000

    def test_neutralises_unicode_line_separators(self):
        # U+2028/U+2029 are replaced with spaces so they cannot act as line
        # breaks (e.g. to break out of a JS string context on render).
        assert clean_text("a b c") == "a b c"


class TestRejectOperatorKeys:
    def test_allows_clean_dict(self):
        doc = {"name": "x", "nested": {"a": 1}}
        assert reject_operator_keys(doc) is doc

    def test_rejects_dollar_key(self):
        with pytest.raises(ValueError):
            reject_operator_keys({"$where": "true"})

    def test_rejects_dotted_key(self):
        with pytest.raises(ValueError):
            reject_operator_keys({"a.b": 1})

    def test_rejects_nested_operator(self):
        with pytest.raises(ValueError):
            reject_operator_keys({"ok": {"$ne": None}})

    def test_rejects_operator_in_list(self):
        with pytest.raises(ValueError):
            reject_operator_keys([{"ok": 1}, {"$gt": ""}])
