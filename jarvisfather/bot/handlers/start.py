from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from jarvisfather.bot.interview.states import Interview
from jarvisfather.bot.keyboards.inline import business_type_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "👋 Привет! Я *JarvisFather* — помогу установить персонального AI-агента на твой сервер.\n\n"
        "Проведу короткое интервью, подберу нужные инструменты и автоматически всё настрою. "
        "Тебе останется только пользоваться.\n\n"
        "Давай начнём. *Какой у тебя бизнес?*",
        parse_mode="Markdown",
        reply_markup=business_type_kb(),
    )
    await state.set_state(Interview.business_type)
