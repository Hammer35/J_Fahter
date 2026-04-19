"""
Обработчики оплаты через Telegram Stars (XTR).
Команда /upgrade → инвойс → оплата → апгрейд тарифа → повторный деплой.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    SuccessfulPayment,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvisfather.db.engine import async_session
from jarvisfather.db.models import User, UserServer

logger = logging.getLogger(__name__)

router = Router()

PRO_PRICE_STARS = 299           # цена в Telegram Stars
PRO_PAYLOAD = "pro_upgrade"     # идентификатор платежа


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message) -> None:
    """Показывает информацию о Pro-тарифе и кнопку оплаты."""
    await message.answer(
        "⭐ *JarvisFather Pro*\n\n"
        "Что открывается:\n"
        "• 🔬 Агент исследований рынка\n"
        "• 📊 Агент аналитики и отчётов\n"
        "• Приоритетные обновления агентов\n\n"
        f"Стоимость: *{PRO_PRICE_STARS} ⭐ Telegram Stars*\n\n"
        "Нажми кнопку ниже чтобы оплатить:",
        parse_mode="Markdown",
    )
    await message.answer_invoice(
        title="JarvisFather Pro",
        description="Доступ к продвинутым AI-агентам: аналитика, исследования рынка",
        payload=PRO_PAYLOAD,
        currency="XTR",
        prices=[LabeledPrice(label="JarvisFather Pro", amount=PRO_PRICE_STARS)],
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Telegram требует подтвердить платёж в течение 10 секунд."""
    if query.invoice_payload == PRO_PAYLOAD:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Неизвестный платёж")


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, state: FSMContext) -> None:
    """Обрабатывает успешный платёж — апгрейд тарифа и повторный деплой."""
    payment: SuccessfulPayment = message.successful_payment
    if payment.invoice_payload != PRO_PAYLOAD:
        return

    telegram_id = message.from_user.id
    logger.info("Успешная оплата Pro: telegram_id=%s stars=%s", telegram_id, payment.total_amount)

    # Апгрейд тарифа в БД
    async with async_session() as session:
        user = await _get_user(session, telegram_id)
        if not user:
            await message.answer("Ошибка: пользователь не найден. Напиши /start")
            return

        user.tier = "pro"
        await session.commit()

        # Проверяем есть ли сервер для повторного деплоя
        server = await _get_last_server(session, user.id)

    await message.answer(
        "✅ *Pro-тариф активирован!*\n\n"
        "Спасибо за поддержку. Теперь тебе доступны все агенты.",
        parse_mode="Markdown",
    )

    if server:
        await message.answer(
            "🔄 Обновляю конфигурацию на твоём сервере — добавляю pro-агентов.\n"
            "Это займёт несколько минут..."
        )
        _trigger_redeploy(telegram_id, server)
    else:
        await message.answer(
            "Сервер не найден. Напиши /start чтобы настроить агентов заново."
        )


async def _get_user(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def _get_last_server(session: AsyncSession, user_id: int) -> UserServer | None:
    result = await session.execute(
        select(UserServer)
        .where(UserServer.user_id == user_id, UserServer.status == "active")
        .order_by(UserServer.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _trigger_redeploy(telegram_id: int, server: UserServer) -> None:
    """Запускает Celery задачу повторного деплоя с pro-агентами."""
    from jarvisfather.crypto.fernet import decrypt
    from jarvisfather.deployer.tasks import redeploy_pro

    try:
        redeploy_pro.delay(
            telegram_id=telegram_id,
            server_id=server.id,
            ip=server.ip,
            ssh_user=server.ssh_user,
            ssh_password=decrypt(server.ssh_pass_enc),
        )
    except Exception as e:
        logger.error("Не удалось запустить повторный деплой: %s", e)
