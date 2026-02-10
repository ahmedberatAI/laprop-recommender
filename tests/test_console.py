"""Unit tests for laprop.utils.console — safe_str / safe_print helpers."""

import io
import pytest

from laprop.utils.console import safe_str, safe_print, _get_encoding


class TestGetEncoding:
    def test_stream_with_encoding(self):
        stream = io.StringIO()
        enc = _get_encoding(stream)
        assert isinstance(enc, str)

    def test_none_stream(self):
        enc = _get_encoding(None)
        assert isinstance(enc, str)


class TestSafeStr:
    def test_normal_string(self):
        assert safe_str("hello") == "hello"

    def test_unicode_string(self):
        result = safe_str("Türkçe karakterler: ğüşıöç")
        assert isinstance(result, str)

    def test_bytes_input(self):
        result = safe_str(b"hello bytes")
        assert result == "hello bytes"

    def test_non_string(self):
        result = safe_str(42)
        assert result == "42"

    def test_none(self):
        result = safe_str(None)
        assert result == "None"


class TestSafePrint:
    def test_prints_to_stream(self):
        stream = io.StringIO()
        safe_print("hello", file=stream)
        assert "hello" in stream.getvalue()

    def test_prints_multiple_args(self):
        stream = io.StringIO()
        safe_print("a", "b", "c", file=stream)
        assert "a b c" in stream.getvalue()

    def test_custom_separator(self):
        stream = io.StringIO()
        safe_print("a", "b", sep="-", file=stream)
        assert "a-b" in stream.getvalue()

    def test_custom_end(self):
        stream = io.StringIO()
        safe_print("hello", end="!", file=stream)
        assert stream.getvalue() == "hello!"

    def test_flush_flag(self):
        stream = io.StringIO()
        safe_print("hello", file=stream, flush=True)
        assert "hello" in stream.getvalue()

    def test_unexpected_kwargs_raises(self):
        with pytest.raises(TypeError, match="unexpected"):
            safe_print("x", bad_arg=True)

    def test_unicode_output(self):
        stream = io.StringIO()
        safe_print("Ğ Ü Ş İ Ö Ç", file=stream)
        assert "Ğ" in stream.getvalue()
