import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from jarvisfather.bot.interview.states import Interview
from jarvisfather.bot.keyboards.inline import confirm_kb, tasks_kb
from jarvisfather.catalog.loader import match_catalog
from jarvisfather.deployer.claude_auth import extract_claude_auth_code
from jarvisfather.rag.retriever import find_similar

router = Router()

BUSINESS_LABELS = {
    "ecommerce": "Интернет-магазин",
    "medical": "Медицина / Клиника",
    "realty": "Недвижимость",
    "education": "Образование",
    "food": "Ресторан / Кафе",
    "services": "Услуги / Консалтинг",
    "other": "Другое",
}

TASK_LABELS = {
    "presentations": "Презентации",
    "marketing": "Маркетинг и контент",
    "clients": "Работа с клиентами",
    "analytics": "Аналитика и отчёты",
    "email": "Email и переписка",
    "research": "Исследования",
}


# --- Шаг 1: тип бизнеса ---

@router.callback_query(Interview.business_type, F.data.startswith("biz:"))
async def step_business(callback: CallbackQuery, state: FSMContext) -> None:
    biz_key = callback.data.split(":")[1]
    await state.update_data(business_type=biz_key)
    await callback.message.edit_text(
        f"✅ *{BUSINESS_LABELS[biz_key]}* — понял.\n\n"
        "Теперь выбери *задачи*, которые должен решать твой AI-агент.\n"
        "Можешь выбрать несколько — нажми нужные и в конце напиши *готово*.",
        parse_mode="Markdown",
        reply_markup=tasks_kb(),
    )
    await state.update_data(selected_tasks=[])
    await state.set_state(Interview.tasks)


# --- Шаг 2: задачи (мультивыбор через callback) ---

@router.callback_query(Interview.tasks, F.data.startswith("task:"))
async def step_task_select(callback: CallbackQuery, state: FSMContext) -> None:
    task_key = callback.data.split(":")[1]
    data = await state.get_data()
    selected: list = data.get("selected_tasks", [])

    if task_key in selected:
        selected.remove(task_key)
    else:
        selected.append(task_key)

    await state.update_data(selected_tasks=selected)

    selected_labels = ", ".join(TASK_LABELS[t] for t in selected) or "ничего не выбрано"
    await callback.answer(f"Выбрано: {selected_labels}", show_alert=False)


@router.message(Interview.tasks, F.text.lower().in_({"готово", "далее", "ок", "ok"}))
async def step_tasks_done(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    selected = data.get("selected_tasks", [])

    if not selected:
        await message.answer("Выбери хотя бы одну задачу, затем напиши *готово*.", parse_mode="Markdown")
        return

    biz_type = data["business_type"]
    biz_label = BUSINESS_LABELS.get(biz_type, biz_type)

    # Пробуем RAG (синхронно через executor, чтобы не блокировать loop)
    rag_agents = rag_skills = None
    rag_note = ""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from jarvisfather.config import settings
        engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"))
        with Session(engine) as session:
            similar = find_similar(session, biz_type, selected)
        if similar:
            best = similar[0]
            rag_agents = best["agents"]
            rag_skills = best["skills"]
            rag_note = "_Подобрано на основе успешных установок_ ✨\n\n"
    except Exception:
        pass  # БД недоступна или данных мало — fallback на каталог

    # Проверяем тариф пользователя
    user_tier = "free"
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SyncSession
        from jarvisfather.config import settings as cfg
        _sync_engine = create_engine(cfg.database_url.replace("+asyncpg", "+psycopg2"))
        with SyncSession(_sync_engine) as s:
            from jarvisfather.db.models import User as UserModel
            u = s.query(UserModel).filter_by(telegram_id=message.from_user.id).first()
            if u:
                user_tier = u.tier
    except Exception:
        pass

    agents, skills = match_catalog(biz_type, selected, tier=user_tier, rag_agents=rag_agents, rag_skills=rag_skills)

    # Проверяем есть ли заблокированные pro-агенты
    PRO_TASKS = {"analytics", "research"}
    has_pro_tasks = bool(set(selected) & PRO_TASKS)
    pro_hint = ""
    if has_pro_tasks and user_tier == "free":
        pro_hint = (
            "\n💡 _Агенты аналитики и исследований доступны в Pro-тарифе._\n"
            "_Напиши /upgrade чтобы узнать подробнее._\n"
        )

    agents_text = "\n".join(f"  • {a.title}" for a in agents) or "  • Базовый ассистент"
    skills_text = "\n".join(f"  • {s.title}" for s in skills) or "  • Нет"

    # Сохраняем подобранные агенты для деплоя
    await state.update_data(
        matched_agents=[a.name for a in agents],
        matched_skills=[s.name for s in skills],
    )

    await message.answer(
        f"🤖 Подобрал конфигурацию для твоего профиля:\n\n"
        f"{rag_note}"
        f"*Бизнес:* {biz_label}\n\n"
        f"*Агенты:*\n{agents_text}\n\n"
        f"*Навыки:*\n{skills_text}\n"
        f"{pro_hint}\n"
        f"Всё это будет установлено на твоём сервере автоматически.\n\n"
        f"Всё верно?",
        parse_mode="Markdown",
        reply_markup=confirm_kb(),
    )
    await state.set_state(Interview.confirm_agents)


# --- Шаг 3: подтверждение ---

@router.callback_query(Interview.confirm_agents, F.data == "confirm:restart")
async def step_restart(callback: CallbackQuery, state: FSMContext) -> None:
    from jarvisfather.bot.keyboards.inline import business_type_kb
    await state.clear()
    await callback.message.edit_text(
        "Хорошо, начнём сначала. *Какой у тебя бизнес?*",
        parse_mode="Markdown",
        reply_markup=business_type_kb(),
    )
    await state.set_state(Interview.business_type)


@router.callback_query(Interview.confirm_agents, F.data == "confirm:yes")
async def step_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "Отлично! Теперь мне нужны данные твоего сервера для установки.\n\n"
        "Введи *IP-адрес* сервера:",
        parse_mode="Markdown",
    )
    await state.set_state(Interview.server_ip)


# --- Сбор credentials ---

@router.message(Interview.server_ip)
async def step_server_ip(message: Message, state: FSMContext) -> None:
    ip = message.text.strip()
    # Простая валидация IP
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        await message.answer("Похоже это не IP-адрес. Введи в формате *123.45.67.89*", parse_mode="Markdown")
        return
    await state.update_data(server_ip=ip)
    await message.answer("Введи *имя пользователя* для SSH (обычно `root`):", parse_mode="Markdown")
    await state.set_state(Interview.ssh_user)


@router.message(Interview.ssh_user)
async def step_ssh_user(message: Message, state: FSMContext) -> None:
    await state.update_data(ssh_user=message.text.strip())
    await message.answer("Введи *пароль* от SSH:", parse_mode="Markdown")
    await state.set_state(Interview.ssh_password)


@router.message(Interview.ssh_password)
async def step_ssh_password(message: Message, state: FSMContext) -> None:
    await state.update_data(ssh_password=message.text.strip())
    await message.answer(
        "Введи *токен твоего Telegram бота*.\n"
        "Получить его можно у @BotFather → /newbot",
        parse_mode="Markdown",
    )
    await state.set_state(Interview.bot_token)


@router.message(Interview.bot_token)
async def step_bot_token(message: Message, state: FSMContext) -> None:
    token = message.text.strip()
    if ":" not in token:
        await message.answer("Токен выглядит неверно. Скопируй его точно из @BotFather.")
        return
    await state.update_data(bot_token=token)
    await message.answer(
        "Последний шаг — авторизация Claude.\n\n"
        "1. Открой в браузере: https://claude.ai/login\n"
        "2. Войди в свой аккаунт\n"
        "3. Скопируй полный URL из адресной строки и отправь мне",
        parse_mode="Markdown",
    )
    await state.set_state(Interview.claude_auth_url)


@router.message(Interview.claude_auth_url)
async def step_claude_auth(message: Message, state: FSMContext) -> None:
    url = message.text.strip()
    if not url.startswith("http"):
        await message.answer("Отправь полный URL из адресной строки браузера.")
        return

    auth_code = extract_claude_auth_code(url)
    if not auth_code:
        await message.answer(
            "Не смог найти код авторизации в этом URL.\n"
            "Убедись что скопировал адресную строку *после* входа в аккаунт Claude.",
            parse_mode="Markdown",
        )
        return

    await state.update_data(claude_auth_code=auth_code)
    data = await state.get_data()

    await message.answer(
        "✅ Все данные получены!\n\n"
        "Начинаю установку на твой сервер. Это займёт около *10-15 минут*.\n"
        "Я уведомлю тебя когда всё будет готово. ☕",
        parse_mode="Markdown",
    )
    await state.set_state(Interview.deploying)

    from jarvisfather.deployer.tasks import deploy_agent
    deploy_agent.delay(message.from_user.id, data)
