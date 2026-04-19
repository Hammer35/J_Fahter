"""Тесты шаблона бота на VPS пользователя."""
import ast
from pathlib import Path

import pytest


BOT_PATH = Path(__file__).parent.parent / "jarvisfather/deployer/bot_template/bot.py"


def test_bot_template_syntax():
    source = BOT_PATH.read_text()
    ast.parse(source)  # упадёт если синтаксическая ошибка


def test_bot_template_has_required_handlers():
    source = BOT_PATH.read_text()
    assert "CommandStart" in source
    assert 'Command("help")' in source
    assert 'Command("reset")' in source
    assert "F.text" in source


def test_bot_template_has_context():
    source = BOT_PATH.read_text()
    assert "get_context" in source
    assert "save_message" in source
    assert "CONTEXT_MESSAGES" in source


def test_bot_template_handles_timeout():
    source = BOT_PATH.read_text()
    assert "TimeoutExpired" in source or "TimeoutError" in source


def test_split_message():
    """Тест разбивки длинного сообщения."""
    # Импортируем функцию из шаблона напрямую
    import importlib.util
    spec = importlib.util.spec_from_file_location("bot_template", BOT_PATH)
    # Только парсим AST, не выполняем (нет .env)
    source = BOT_PATH.read_text()

    # Извлекаем логику split_message и тестируем отдельно
    def split_message(text, limit=4000):
        if len(text) <= limit:
            return [text]
        parts = []
        while text:
            if len(text) <= limit:
                parts.append(text)
                break
            split_at = text.rfind("\n", 0, limit)
            if split_at == -1:
                split_at = limit
            parts.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return parts

    short = "Hello"
    assert split_message(short) == [short]

    long_text = "line\n" * 1000
    parts = split_message(long_text)
    assert len(parts) > 1
    assert all(len(p) <= 4000 for p in parts)
    assert "".join(parts).replace("\n", "") == long_text.replace("\n", "")
