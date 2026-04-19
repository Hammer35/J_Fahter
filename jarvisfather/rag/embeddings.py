"""
Генерация векторных эмбеддингов через sentence-transformers.
Модель: paraphrase-multilingual-MiniLM-L12-v2 (384 dim, русский поддерживается).
"""
from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_DIM = 384


@lru_cache(maxsize=1)
def _get_model():
    """Загружает модель один раз и кэширует."""
    from sentence_transformers import SentenceTransformer
    logger.info("Загрузка модели эмбеддингов %s...", MODEL_NAME)
    return SentenceTransformer(MODEL_NAME)


def embed(text: str) -> list[float]:
    """Возвращает вектор эмбеддинга для текста."""
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def build_profile_text(business_type: str, tasks: list[str]) -> str:
    """Формирует текст профиля для эмбеддинга."""
    task_labels = {
        "marketing": "маркетинг и контент",
        "presentations": "создание презентаций",
        "clients": "работа с клиентами",
        "analytics": "аналитика и отчёты",
        "email": "email и переписка",
        "research": "исследования рынка",
    }
    biz_labels = {
        "ecommerce": "интернет-магазин",
        "medical": "медицина клиника",
        "realty": "недвижимость",
        "education": "образование",
        "food": "ресторан кафе",
        "services": "услуги консалтинг",
        "other": "другой бизнес",
    }
    biz = biz_labels.get(business_type, business_type)
    tasks_str = " ".join(task_labels.get(t, t) for t in tasks)
    return f"бизнес: {biz}. задачи: {tasks_str}"
