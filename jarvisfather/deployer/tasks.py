from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session

from celery_app import app
from jarvisfather.catalog.loader import CatalogItem, load_catalog
from jarvisfather.config import settings
from jarvisfather.crypto.fernet import decrypt, encrypt
from jarvisfather.db.models import Deployment, DeploymentStatus, User, UserServer
from jarvisfather.deployer.ssh_client import SSHClient
from jarvisfather.rag.indexer import index_configuration, update_success_score

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent / "scripts"
BOT_TEMPLATE_DIR = Path(__file__).parent / "bot_template"
CATALOG_DIR = Path(__file__).parent.parent / "catalog"

# Синхронный движок для Celery (Celery не async)
_engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))


def _notify(telegram_id: int, text: str) -> None:
    """Отправляет уведомление пользователю через Telegram Bot API."""
    try:
        httpx.post(
            f"https://api.telegram.org/bot{settings.bot_token}/sendMessage",
            json={"chat_id": telegram_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        logger.warning("Не удалось отправить уведомление: %s", e)


def _update_deployment(session: Session, deployment_id: int, **kwargs) -> None:
    session.execute(
        update(Deployment).where(Deployment.id == deployment_id).values(**kwargs)
    )
    session.commit()


def _get_catalog_items(names: list[str], kind: str) -> list[CatalogItem]:
    return [i for i in load_catalog() if i.name in names and i.kind == kind]


def _deploy(
    ssh: SSHClient,
    telegram_id: int,
    data: dict,
    deployment_id: int,
    session: Session,
) -> None:
    log_lines: list[str] = []

    def on_output(line: str) -> None:
        log_lines.append(line)
        if line.startswith("[JarvisFather]"):
            _notify(telegram_id, f"⚙️ {line.replace('[JarvisFather] ', '')}")

    def run(cmd: str, timeout: int = 300) -> None:
        code, out = ssh.run(cmd, on_output=on_output, timeout=timeout)
        if code != 0:
            raise RuntimeError(f"Команда завершилась с ошибкой ({code}):\n{out[-500:]}")

    # --- Шаг 1: установка системных пакетов и Claude Code ---
    _notify(telegram_id, "📦 Устанавливаю необходимые программы...")
    script_content = (SCRIPTS_DIR / "install.sh").read_text()
    ssh.put_content(script_content, "/tmp/jf_install.sh")
    run(
        f"BOT_TOKEN='{data['bot_token']}' "
        f"CLAUDE_AUTH_CODE='{data['claude_auth_code']}' "
        f"bash /tmp/jf_install.sh",
        timeout=600,
    )

    # --- Шаг 2: копирование агентов и скилов в ~/.claude ---
    _notify(telegram_id, "🤖 Настраиваю AI-агентов...")
    ssh.mkdir("~/.claude/agents")
    ssh.mkdir("~/.claude/skills")

    agents = _get_catalog_items(data.get("matched_agents", []), "agent")
    for agent in agents:
        content = f"---\nname: {agent.name}\ndescription: {agent.title}\n---\n\n{agent.body}\n"
        ssh.put_content(content, f"~/.claude/agents/{agent.name}.md")

    skills = _get_catalog_items(data.get("matched_skills", []), "skill")
    for skill in skills:
        content = f"---\nname: {skill.name}\ndescription: {skill.title}\n---\n\n{skill.body}\n"
        ssh.put_content(content, f"~/.claude/skills/{skill.name}.md")

    # settings.json
    ssh.put_content(
        '{"enableAllProjectMcpServers": false}\n',
        "~/.claude/settings.json",
    )

    # --- Шаг 3: копирование бота ---
    _notify(telegram_id, "🤖 Копирую бота...")
    ssh.mkdir("~/jarvis_bot")
    ssh.put_content(
        (BOT_TEMPLATE_DIR / "bot.py").read_text(),
        "~/jarvis_bot/bot.py",
    )

    # .env файл с токеном
    ssh.put_content(
        f"BOT_TOKEN={data['bot_token']}\n",
        "~/jarvis_bot/.env",
    )

    # --- Шаг 4: запуск ---
    _notify(telegram_id, "🚀 Запускаю бота...")
    run("systemctl --user restart jarvis_bot || systemctl --user start jarvis_bot")

    # Проверяем что сервис запустился
    code, status = ssh.run("systemctl --user is-active jarvis_bot")
    if "active" not in status:
        raise RuntimeError(f"Сервис не запустился: {status}")

    _update_deployment(
        session,
        deployment_id,
        status=DeploymentStatus.success,
        log="\n".join(log_lines),
        finished_at=datetime.now(timezone.utc),
    )


@app.task(bind=True, max_retries=3, default_retry_delay=30, name="deploy_agent")
def deploy_agent(self, telegram_id: int, data: dict) -> None:
    """
    Главная Celery задача: разворачивает агента на VPS пользователя.

    data содержит: server_ip, ssh_user, ssh_password, bot_token,
                   claude_auth_code, matched_agents, matched_skills
    """
    with Session(_engine) as session:
        # Создаём или обновляем запись деплоя
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            logger.error("Пользователь %s не найден", telegram_id)
            return

        # Сохраняем сервер с зашифрованными credentials
        server = UserServer(
            user_id=user.id,
            ip=data["server_ip"],
            ssh_user=data["ssh_user"],
            ssh_pass_enc=encrypt(data["ssh_password"]),
            bot_token_enc=encrypt(data["bot_token"]),
            claude_auth_enc=encrypt(data["claude_auth_code"]),
        )
        session.add(server)
        session.flush()

        deployment = Deployment(user_id=user.id, server_id=server.id)
        session.add(deployment)
        session.commit()
        deployment_id = deployment.id

    _notify(telegram_id, "🔧 Подключаюсь к серверу...")

    try:
        with SSHClient(
            host=data["server_ip"],
            user=data["ssh_user"],
            password=data["ssh_password"],
        ) as ssh:
            with Session(_engine) as session:
                _update_deployment(session, deployment_id, status=DeploymentStatus.running)
                _deploy(ssh, telegram_id, data, deployment_id, session)

        # Индексируем конфигурацию в RAG
        try:
            with Session(_engine) as session:
                user = session.query(User).filter_by(telegram_id=telegram_id).first()
                if user:
                    index_configuration(
                        session=session,
                        user_id=user.id,
                        business_type=data.get("business_type", "other"),
                        tasks=data.get("selected_tasks", []),
                        agents=data.get("matched_agents", []),
                        skills=data.get("matched_skills", []),
                    )
        except Exception as e:
            logger.warning("RAG индексация не удалась: %s", e)

        # Планируем проверку активности через 7 дней
        try:
            with Session(_engine) as session:
                server_rec = session.query(UserServer).filter_by(
                    ip=data["server_ip"]
                ).order_by(UserServer.id.desc()).first()
                if server_rec:
                    check_bot_activity.apply_async(
                        args=[telegram_id, server_rec.ip, server_rec.ssh_user, server_rec.ssh_pass_enc],
                        countdown=7 * 24 * 3600,
                    )
        except Exception as e:
            logger.warning("Не удалось запланировать проверку активности: %s", e)

        _notify(
            telegram_id,
            "✅ *Готово!*\n\n"
            "Твой персональный AI-ассистент установлен и запущен.\n"
            "Напиши своему боту — он уже ждёт тебя!",
        )

    except Exception as exc:
        logger.exception("Ошибка деплоя для %s", telegram_id)

        with Session(_engine) as session:
            _update_deployment(
                session,
                deployment_id,
                status=DeploymentStatus.failed,
                log=str(exc),
                finished_at=datetime.now(timezone.utc),
            )

        retry_num = self.request.retries
        if retry_num < self.max_retries:
            _notify(
                telegram_id,
                f"⚠️ Ошибка установки (попытка {retry_num + 1}/3). Повторяю...\n\n"
                f"`{str(exc)[:200]}`",
            )
            raise self.retry(exc=exc)
        else:
            _notify(
                telegram_id,
                "❌ *Установка не удалась* после 3 попыток.\n\n"
                f"Ошибка: `{str(exc)[:300]}`\n\n"
                "Проверь:\n"
                "• Доступен ли сервер по SSH\n"
                "• Правильно ли введены данные\n"
                "• Есть ли права root\n\n"
                "Напиши /start чтобы попробовать снова.",
            )

@app.task(name="check_bot_activity")
def check_bot_activity(telegram_id: int, server_ip: str, ssh_user: str, ssh_pass_enc: str) -> None:
    """
    Проверяет активность бота через 7 дней после деплоя.
    Считает количество сообщений в SQLite на VPS и обновляет success_score.
    """
    try:
        ssh_password = decrypt(ssh_pass_enc)
        with SSHClient(host=server_ip, user=ssh_user, password=ssh_password) as ssh:
            code, output = ssh.run(
                "sqlite3 ~/jarvis_bot/history.db 'SELECT COUNT(*) FROM messages WHERE role=\"user\"' 2>/dev/null || echo 0"
            )
            msg_count = int(output.strip()) if output.strip().isdigit() else 0

        # Нормализуем: 50+ сообщений за неделю = score 10
        score = min(10.0, msg_count / 5.0)

        with Session(_engine) as session:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                update_success_score(session, user.id, score)

        logger.info("Активность бота user=%s: %d сообщений, score=%.1f", telegram_id, msg_count, score)

    except Exception as e:
        logger.warning("Не удалось проверить активность для %s: %s", telegram_id, e)

@app.task(bind=True, max_retries=2, default_retry_delay=60, name="redeploy_pro")
def redeploy_pro(self, telegram_id: int, server_id: int, ip: str, ssh_user: str, ssh_password: str) -> None:
    """
    Повторный деплой после апгрейда на Pro.
    Добавляет pro-агентов в ~/.claude/agents/ без полной переустановки.
    """
    _notify(telegram_id, "🔄 Подключаюсь к серверу для обновления...")

    try:
        with SSHClient(host=ip, user=ssh_user, password=ssh_password) as ssh:
            # Получаем pro-агентов из каталога
            pro_agents = _get_catalog_items(
                ["analytics", "researcher"],
                "agent",
            )

            for agent in pro_agents:
                content = (
                    f"---\nname: {agent.name}\ndescription: {agent.title}\n---\n\n{agent.body}\n"
                )
                ssh.put_content(content, f"~/.claude/agents/{agent.name}.md")

            # Перезапускаем бота чтобы подхватил новые агенты
            ssh.run("systemctl --user restart jarvis_bot")

        _notify(
            telegram_id,
            "✅ *Pro-агенты установлены!*\n\n"
            "Твой бот обновлён — теперь доступны:\n"
            "• 📊 Аналитика и отчёты\n"
            "• 🔬 Исследования рынка\n\n"
            "Просто напиши боту что нужно проанализировать!",
        )

    except Exception as exc:
        logger.exception("Ошибка redeploy_pro для %s", telegram_id)
        if self.request.retries < self.max_retries:
            _notify(telegram_id, f"⚠️ Ошибка обновления, повторяю... `{str(exc)[:150]}`")
            raise self.retry(exc=exc)
        else:
            _notify(
                telegram_id,
                "❌ Не удалось обновить агентов автоматически.\n"
                "Напиши /start — переустановим с нуля с Pro-настройками.",
            )
