from aiogram.fsm.state import State, StatesGroup


class Interview(StatesGroup):
    # Интервью
    business_type = State()      # тип бизнеса
    tasks = State()              # задачи для автоматизации
    confirm_agents = State()     # подтверждение подобранных агентов

    # Сбор credentials
    server_ip = State()
    ssh_user = State()
    ssh_password = State()
    bot_token = State()
    claude_auth_url = State()

    # Ожидание деплоя
    deploying = State()
