"""
Индексирует успешные конфигурации деплоев в БД для последующего RAG-поиска.
Вызывается после успешного деплоя из Celery задачи.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from jarvisfather.db.models import Configuration
from jarvisfather.rag.embeddings import build_profile_text, embed

logger = logging.getLogger(__name__)


def index_configuration(
    session: Session,
    user_id: int,
    business_type: str,
    tasks: list[str],
    agents: list[str],
    skills: list[str],
) -> None:
    """Сохраняет конфигурацию с эмбеддингом в таблицу configurations."""
    profile_text = build_profile_text(business_type, tasks)

    try:
        vector = embed(profile_text)
        embedding_json = json.dumps(vector)
    except Exception as e:
        logger.warning("Не удалось сгенерировать эмбеддинг: %s", e)
        embedding_json = None

    config = Configuration(
        user_id=user_id,
        business_type=business_type,
        tasks=json.dumps(tasks, ensure_ascii=False),
        agents=json.dumps(agents, ensure_ascii=False),
        skills=json.dumps(skills, ensure_ascii=False),
        success_score=0.0,   # обновится через 7 дней
        embedding=embedding_json,
    )
    session.add(config)
    session.commit()
    logger.info("Конфигурация проиндексирована: user=%s biz=%s", user_id, business_type)


def update_success_score(session: Session, user_id: int, score: float) -> None:
    """Обновляет оценку успешности последней конфигурации пользователя."""
    config = (
        session.query(Configuration)
        .filter_by(user_id=user_id)
        .order_by(Configuration.created_at.desc())
        .first()
    )
    if config:
        config.success_score = score
        session.commit()
        logger.info("success_score обновлён: user=%s score=%.2f", user_id, score)
