import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from jarvisfather.bot.handlers import interview, payment, start
from jarvisfather.config import settings

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=settings.bot_token)
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    dp.include_router(start.router)
    dp.include_router(interview.router)
    dp.include_router(payment.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
