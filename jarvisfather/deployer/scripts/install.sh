#!/bin/bash
# JarvisFather — скрипт установки на VPS пользователя
# Переменные передаются через env: BOT_TOKEN, CLAUDE_AUTH_CODE
set -e

LOG() { echo "[JarvisFather] $*"; }

# --- 1. Системные зависимости ---
LOG "Обновление пакетов..."
apt-get update -qq

LOG "Установка зависимостей..."
apt-get install -y -qq git curl python3 python3-pip python3-venv

# --- 2. Node.js 20 (для Claude Code CLI) ---
if ! command -v node &>/dev/null; then
    LOG "Установка Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
    apt-get install -y -qq nodejs
fi
LOG "Node.js: $(node --version)"

# --- 3. Claude Code CLI ---
if ! command -v claude &>/dev/null; then
    LOG "Установка Claude Code..."
    npm install -g @anthropic-ai/claude-code --silent
fi
LOG "Claude Code: $(claude --version 2>/dev/null || echo 'установлен')"

# --- 4. Авторизация Claude ---
LOG "Авторизация Claude Code..."
claude auth login --code "$CLAUDE_AUTH_CODE" 2>/dev/null || \
    LOG "WARN: авторизация требует ручного подтверждения"

# --- 5. Структура ~/.claude ---
LOG "Настройка ~/.claude..."
mkdir -p ~/.claude/agents ~/.claude/skills ~/.claude/hooks

# --- 6. Python-окружение для бота ---
LOG "Создание Python окружения..."
mkdir -p ~/jarvis_bot
python3 -m venv ~/jarvis_bot/.venv
~/jarvis_bot/.venv/bin/pip install -q --upgrade pip
~/jarvis_bot/.venv/bin/pip install -q aiogram aiosqlite python-dotenv

# --- 7. systemd сервис ---
LOG "Настройка systemd сервиса..."
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/jarvis_bot.service << 'EOF'
[Unit]
Description=JarvisFather personal bot
After=network.target

[Service]
WorkingDirectory=%h/jarvis_bot
ExecStart=%h/jarvis_bot/.venv/bin/python %h/jarvis_bot/bot.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# Включаем lingering чтобы сервис стартовал без логина
loginctl enable-linger "$USER" 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user enable jarvis_bot

LOG "Установка завершена"
