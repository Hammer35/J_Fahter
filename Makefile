.PHONY: up down bot worker test migrate logs

# Запуск PostgreSQL + Redis
up:
	docker compose up -d
	@echo "Ждём готовности PostgreSQL..."
	@sleep 3

# Остановка
down:
	docker compose down

# Миграции БД
migrate:
	PYTHONPATH=. .venv/bin/alembic upgrade head

# Запуск бота
bot:
	PYTHONPATH=. .venv/bin/python main.py

# Запуск Celery worker
worker:
	PYTHONPATH=. .venv/bin/celery -A celery_app worker --loglevel=info --concurrency=4

# Запуск всего (для разработки — в разных терминалах)
dev: up migrate
	@echo ""
	@echo "Запусти в терминале 1:  make bot"
	@echo "Запусти в терминале 2:  make worker"

# Тесты
test:
	PYTHONPATH=. .venv/bin/pytest tests/ -v

# Логи сервисов
logs:
	docker compose logs -f
