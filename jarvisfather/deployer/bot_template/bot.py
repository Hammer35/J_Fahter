"""
Персональный бот пользователя на VPS.
Получает сообщения в Telegram, передаёт Claude Code, возвращает ответ.
"""
import asyncio
import logging
import os
import subprocess
from pathlib import Path

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
DB_PATH = Path(__file__).parent / "history.db"
CONTEXT_MESSAGES = 12       # последних сообщений в контекст
MAX_RESPONSE_LEN = 4000     # лимит Telegram — 4096, с запасом
CLAUDE_TIMEOUT = 120        # секунд


# ---------------------------------------------------------------------------
# База данных
# ---------------------------------------------------------------------------

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def save_message(role: str, content: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (role, content),
        )
        await db.commit()


async def get_context() -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (CONTEXT_MESSAGES,),
        ) as cursor:
            rows = await cursor.fetchall()
    rows.reverse()
    return "\n".join(f"{role}: {content}" for role, content in rows)


async def clear_history() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages")
        await db.commit()


# ---------------------------------------------------------------------------
# Claude Code
# ---------------------------------------------------------------------------

async def ask_claude(user_message: str) -> str:
    context = await get_context()
    prompt = f"{context}\nuser: {user_message}" if context else f"user: {user_message}"

    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["claude", "-p", prompt, "--output-format", "text"],
                    capture_output=True,
                    text=True,
                    timeout=CLAUDE_TIMEOUT,
                ),
            ),
            timeout=CLAUDE_TIMEOUT + 5,
        )
    except asyncio.TimeoutError:
        return "Запрос занял слишком много времени. Попробуй ещё раз или задай более конкретный вопрос."

    if result.returncode != 0:
        err = result.stderr.strip()
        logger.error("Claude error: %s", err)
        return "Не смог получить ответ. Попробуй переформулировать запрос."

    return result.stdout.strip() or "Ответ пустой. Попробуй ещё раз."


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def split_message(text: str, limit: int = MAX_RESPONSE_LEN) -> list[str]:
    """Разбивает длинный текст на части для Telegram."""
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        # Ищем ближайший перенос строки перед лимитом
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return parts


# ---------------------------------------------------------------------------
# Бот
# ---------------------------------------------------------------------------

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я твой персональный AI-ассистент на базе Claude.\n\n"
        "Просто напиши мне что нужно — помогу с любой задачей.\n\n"
        "Команды:\n"
        "/help — список возможностей\n"
        "/reset — очистить историю разговора"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Что я умею:\n\n"
        "• Создавать презентации и тексты\n"
        "• Писать маркетинговые материалы\n"
        "• Отвечать на вопросы и исследовать темы\n"
        "• Помогать с деловой перепиской\n"
        "• Анализировать информацию\n\n"
        "Просто напиши задачу своими словами — я помогу.\n\n"
        "/reset — начать разговор заново"
    )


@dp.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    await clear_history()
    await message.answer("История разговора очищена. Начинаем с чистого листа!")


@dp.message(F.text)
async def handle_message(message: Message) -> None:
    user_text = message.text

    # Typing indicator пока Claude думает
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    typing_task = asyncio.create_task(_keep_typing(message.chat.id))

    try:
        await save_message("user", user_text)
        response = await ask_claude(user_text)
        await save_message("assistant", response)
    except Exception as e:
        logger.exception("Ошибка обработки сообщения")
        response = "Что-то пошло не так. Попробуй ещё раз."
    finally:
        typing_task.cancel()

    # Отправляем ответ (разбиваем если длинный)
    for part in split_message(response):
        await message.answer(part)


async def _keep_typing(chat_id: int) -> None:
    """Поддерживает typing indicator пока Claude отвечает."""
    try:
        while True:
            await asyncio.sleep(4)
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

async def main() -> None:
    await init_db()
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
