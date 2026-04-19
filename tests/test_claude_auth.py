"""Тесты извлечения кода авторизации Claude."""
import pytest

from jarvisfather.deployer.claude_auth import extract_claude_auth_code


def test_code_from_query_string():
    url = "https://claude.ai/callback?code=abc123&state=xyz"
    assert extract_claude_auth_code(url) == "abc123"


def test_code_from_fragment():
    url = "https://claude.ai/callback#code=def456"
    assert extract_claude_auth_code(url) == "def456"


def test_no_code_returns_none():
    assert extract_claude_auth_code("https://claude.ai/login") is None
    assert extract_claude_auth_code("https://claude.ai/chat?session=abc") is None


def test_long_code():
    code = "a" * 128
    url = f"https://claude.ai/callback?code={code}&state=xyz"
    assert extract_claude_auth_code(url) == code


def test_query_takes_priority_over_fragment():
    url = "https://claude.ai/callback?code=query_code#code=fragment_code"
    assert extract_claude_auth_code(url) == "query_code"
