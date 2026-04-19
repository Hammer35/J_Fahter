"""
Поиск похожих конфигураций через косинусное сходство эмбеддингов.
"""
from __future__ import annotations

import json
import logging
import math

from sqlalchemy.orm import Session

from jarvisfather.db.models import Configuration
from jarvisfather.rag.embeddings import build_profile_text, embed

logger = logging.getLogger(__name__)

MIN_CONFIGS_FOR_RAG = 5    # минимум записей в БД для активации RAG
SIMILARITY_THRESHOLD = 0.75
TOP_K = 3


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_similar(
    session: Session,
    business_type: str,
    tasks: list[str],
    top_k: int = TOP_K,
) -> list[dict] | None:
    """
    Ищет top_k похожих конфигураций.
    Возвращает None если данных недостаточно для RAG.
    Возвращает список dict с ключами: agents, skills, score.
    """
    total = session.query(Configuration).count()
    if total < MIN_CONFIGS_FOR_RAG:
        logger.debug("RAG: недостаточно данных (%d/%d), используем каталог", total, MIN_CONFIGS_FOR_RAG)
        return None

    try:
        query_vector = embed(build_profile_text(business_type, tasks))
    except Exception as e:
        logger.warning("RAG: ошибка эмбеддинга запроса: %s", e)
        return None

    # Загружаем конфигурации с эмбеддингами
    configs = (
        session.query(Configuration)
        .filter(Configuration.embedding.isnot(None))
        .all()
    )

    if not configs:
        return None

    # Считаем сходство
    scored: list[tuple[float, Configuration]] = []
    for config in configs:
        try:
            vec = json.loads(config.embedding)
            sim = _cosine_similarity(query_vector, vec)
            # Учитываем success_score как бонус (вес 20%)
            adjusted = sim * 0.8 + (config.success_score / 10.0) * 0.2
            scored.append((adjusted, config))
        except Exception:
            continue

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for s in scored[:top_k] if s[0] >= SIMILARITY_THRESHOLD]

    if not top:
        return None

    results = []
    for score, config in top:
        results.append({
            "agents": json.loads(config.agents),
            "skills": json.loads(config.skills),
            "score": round(score, 3),
            "business_type": config.business_type,
        })

    logger.info("RAG: найдено %d похожих конфигураций (top score=%.3f)", len(results), top[0][0])
    return results
