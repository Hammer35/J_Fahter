# JarvisFather — Спецификация

## Executive Summary

JarvisFather — SaaS-платформа в Telegram, которая автоматически разворачивает персонализированного AI-агента на VPS пользователя. Целевая аудитория — нетехнические бизнес-пользователи. Монетизация через freemium.

---

## Проблема

Нетехнический предприниматель не может самостоятельно настроить мультиагентную систему на базе Claude Code. JarvisFather берёт на себя весь процесс: интервью → подбор агентов → автоматический деплой → готовый персональный бот в Telegram.

---

## Критерии успеха

- Пользователь получает работающего бота на своём VPS за < 15 минут после интервью
- 500+ активных пользователей
- Система учится на предыдущих установках (RAG)
- Freemium конверсия в платный тариф

---

## Персоны

**Бизнесмен (основной пользователь)**
- Нетехнический, не знает Linux/SSH
- Хочет AI-помощника для своего бизнеса (маркетинг, презентации, аналитика)
- Имеет VPS на Beget или TimeWeb и подписку Claude Pro/Team
- Взаимодействует только через Telegram

---

## Пользовательский путь

```
1. /start в Telegram → ДжарвисФазер приветствует
2. Интервью вопрос за вопросом:
   - Какой бизнес?
   - Какие задачи нужно автоматизировать?
   - Какие результаты важны?
3. ДжарвисФазер подбирает агентов и скилы из RAG-базы
4. Показывает что будет установлено, просит подтверждение
5. Запрашивает данные для деплоя:
   - IP сервера, SSH логин/пароль
   - Токен Telegram бота
   - URL авторизации Claude (OAuth)
6. Фоновый деплой через Celery (SSH на VPS):
   - Установка зависимостей (Node.js 18+, Git, Python, SQLite)
   - Установка Claude Code CLI + OAuth авторизация
   - Настройка ~/.claude/ (агенты, скилы, хуки)
   - Установка и запуск aiogram бота
7. Уведомление: "Ваш бот готов. Напишите ему: @your_bot"
8. Пользователь общается со своим персональным ботом
```

---

## Функциональные требования

### Must Have (P0)

- [ ] Telegram бот с интервью (вопрос-ответ)
- [ ] RAG-подбор агентов и скилов по профилю бизнеса
- [ ] Автоматический деплой на VPS через SSH (Celery-задача)
- [ ] Установка Claude Code CLI с OAuth авторизацией
- [ ] Настройка ~/.claude/ (agents/, skills/, hooks/, settings.json)
- [ ] Установка и запуск персонального aiogram бота на VPS
- [ ] Уведомление о статусе деплоя (успех / ошибка + инструкция)
- [ ] Зашифрованное хранение SSH credentials и токенов
- [ ] Freemium: базовые агенты бесплатно

### Should Have (P1)

- [ ] Повторный деплой / обновление при изменении тарифа
- [ ] Автоисправление ошибок деплоя (retry + диагностика)
- [ ] Платные продвинутые агенты и скилы
- [ ] Накопление успешных конфигураций в RAG
- [ ] Логи деплоев в админ-панели

### Nice to Have (P2)

- [ ] Поддержка других хостингов (не только Beget/TimeWeb)
- [ ] Веб-панель управления агентами
- [ ] Мультиязычность

---

## Техническая архитектура

### Центральный сервер (ДжарвисФазер)

```
jarvisfather/
├── bot/                  # aiogram Telegram бот
│   ├── handlers/         # Обработчики сообщений
│   ├── interview/        # Логика интервью
│   └── keyboards/        # Inline клавиатуры
├── rag/                  # RAG система
│   ├── embeddings.py     # Генерация эмбеддингов
│   ├── retriever.py      # Поиск похожих конфигураций
│   └── indexer.py        # Индексация новых установок
├── deployer/             # Деплой на VPS
│   ├── tasks.py          # Celery задачи
│   ├── ssh_client.py     # SSH через Paramiko
│   ├── scripts/          # Bash-скрипты установки
│   └── templates/        # Шаблоны ~/.claude конфигов
├── catalog/              # Каталог агентов и скилов
│   ├── agents/           # .md файлы агентов
│   └── skills/           # .md файлы скилов
├── db/                   # Модели и миграции
│   └── models.py         # SQLAlchemy модели
├── crypto/               # Шифрование credentials
└── config.py
```

### Стек центрального сервера

| Компонент | Технология |
|-----------|-----------|
| Telegram бот | Python 3.12 + aiogram 3.x |
| Очередь задач | Celery 5.x |
| Брокер/кэш | Redis 7.x |
| База данных | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.x + asyncpg |
| SSH деплой | Paramiko |
| Шифрование | cryptography (Fernet) |
| Эмбеддинги | Claude API (embeddings) или sentence-transformers |

### База данных (PostgreSQL + pgvector)

```sql
-- Пользователи
users (id, telegram_id, username, tier, created_at)

-- Серверы пользователей (credentials зашифрованы)
user_servers (id, user_id, ip, ssh_user, ssh_pass_enc, bot_token_enc, claude_auth_enc, status)

-- Деплои
deployments (id, user_id, server_id, status, log, started_at, finished_at)

-- Конфигурации (RAG)
configurations (id, user_id, business_type, agents[], skills[], embedding vector(1536), success_score)

-- Каталог агентов
agents_catalog (id, name, description, tier, skill_md, embedding vector(1536))
```

### VPS пользователя (после деплоя)

```
~/.claude/
├── settings.json
├── agents/           # Персональные агенты
├── skills/           # Персональные скилы
└── hooks/            # Хуки

~/jarvis_bot/
├── bot.py            # aiogram бот
├── db.sqlite         # История разговоров
├── .env              # TELEGRAM_BOT_TOKEN, CLAUDE_SESSION
└── requirements.txt
```

### Деплой-скрипт (выполняется через SSH)

```bash
# 1. Зависимости
apt update && apt install -y nodejs npm git python3 python3-pip

# 2. Claude Code CLI
curl -fsSL https://claude.ai/install.sh | bash

# 3. OAuth авторизация (код извлечён из URL пользователя)
claude auth --code <extracted_code>

# 4. ~/.claude структура
mkdir -p ~/.claude/agents ~/.claude/skills ~/.claude/hooks
# копирование агентов/скилов/хуков через SFTP

# 5. Telegram бот
mkdir ~/jarvis_bot && cd ~/jarvis_bot
# копирование файлов через SFTP
pip install aiogram aiosqlite
echo "TELEGRAM_BOT_TOKEN=..." > .env

# 6. Запуск как systemd сервис
systemctl --user enable jarvis_bot
systemctl --user start jarvis_bot
```

---

## Модель данных RAG

При каждой успешной установке JarvisFather сохраняет:
- Тип бизнеса + задачи (текст)
- Выбранные агенты и скилы
- Оценку успешности (активность бота через 7 дней)
- Векторный эмбеддинг профиля

При новом интервью — ищет топ-3 похожих конфигурации и предлагает их как основу.

---

## Безопасность

- SSH credentials, токены, OAuth данные → шифрование Fernet (симметричное, ключ в env)
- Credentials используются при деплое и хранятся для повторных обновлений
- Telegram ID как основной идентификатор пользователя
- Доступ к чужим данным исключён на уровне БД (user_id FK везде)

---

## Нефункциональные требования

- **Масштаб:** 500+ пользователей, параллельные деплои через Celery workers
- **Время деплоя:** < 15 минут на чистый VPS
- **Надёжность:** retry при ошибках деплоя (3 попытки), уведомление при провале
- **Хостинги:** Beget, TimeWeb (Ubuntu 20.04/22.04)

---

## Вне скопа (пока)

- Веб-панель управления
- Поддержка других VPS-провайдеров
- Windows-серверы
- Мобильное приложение

---

## Открытые вопросы для реализации

1. Конкретные тарифы freemium (какие агенты бесплатно, какие платно)
2. Выбор провайдера эмбеддингов (Claude API vs sentence-transformers)
3. Механизм обновления агентов на уже развёрнутых VPS
4. Политика хранения SSH credentials (TTL? Удаление по запросу?)
5. Beget или TimeWeb — приоритет для первого MVP

---

## Приложение: Исследование

- Официальная Telegram интеграция Claude Code: MCP-плагин (Grammy + Bun)
- Для all-Python стека используем aiogram + `claude -p` headless режим
- pgvector встраивается в PostgreSQL, отдельная векторная БД не нужна
- Celery необходим: деплой занимает 5-15 минут, блокировать aiogram нельзя
- SQLite на VPS пользователя — оптимально для одного изолированного бота
