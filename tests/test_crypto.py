"""Тесты шифрования credentials."""
import os

import pytest
from cryptography.fernet import Fernet


def test_encrypt_decrypt(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("BOT_TOKEN", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ENCRYPTION_KEY", key)

    # Импортируем после установки env
    import importlib
    import jarvisfather.config
    import jarvisfather.crypto.fernet as fernet_module

    importlib.reload(jarvisfather.config)
    importlib.reload(fernet_module)

    from jarvisfather.crypto.fernet import decrypt, encrypt

    secret = "my_ssh_password_123"
    encrypted = encrypt(secret)

    assert encrypted != secret
    assert decrypt(encrypted) == secret


def test_different_values_produce_different_ciphertexts(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("BOT_TOKEN", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ENCRYPTION_KEY", key)

    import importlib
    import jarvisfather.config
    import jarvisfather.crypto.fernet as fernet_module

    importlib.reload(jarvisfather.config)
    importlib.reload(fernet_module)

    from jarvisfather.crypto.fernet import encrypt

    assert encrypt("value1") != encrypt("value2")
