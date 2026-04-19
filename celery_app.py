from celery import Celery

from jarvisfather.config import settings

app = Celery(
    "jarvisfather",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["jarvisfather.deployer.tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={},  # задачи check_bot_activity планируются динамически через apply_async(countdown=...)
)
