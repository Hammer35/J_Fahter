from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def business_type_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🛒 Интернет-магазин", callback_data="biz:ecommerce")],
        [InlineKeyboardButton(text="🏥 Медицина / Клиника", callback_data="biz:medical")],
        [InlineKeyboardButton(text="🏠 Недвижимость", callback_data="biz:realty")],
        [InlineKeyboardButton(text="📚 Образование", callback_data="biz:education")],
        [InlineKeyboardButton(text="🍽 Ресторан / Кафе", callback_data="biz:food")],
        [InlineKeyboardButton(text="💼 Услуги / Консалтинг", callback_data="biz:services")],
        [InlineKeyboardButton(text="✍️ Другое", callback_data="biz:other")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tasks_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📊 Презентации", callback_data="task:presentations")],
        [InlineKeyboardButton(text="📣 Маркетинг и контент", callback_data="task:marketing")],
        [InlineKeyboardButton(text="🤝 Работа с клиентами", callback_data="task:clients")],
        [InlineKeyboardButton(text="📈 Аналитика и отчёты", callback_data="task:analytics")],
        [InlineKeyboardButton(text="📧 Email и переписка", callback_data="task:email")],
        [InlineKeyboardButton(text="🔍 Исследования", callback_data="task:research")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Всё верно, начать установку", callback_data="confirm:yes"),
            InlineKeyboardButton(text="🔄 Начать заново", callback_data="confirm:restart"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
