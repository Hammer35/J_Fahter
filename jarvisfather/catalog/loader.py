from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

CATALOG_DIR = Path(__file__).parent


@dataclass
class CatalogItem:
    name: str
    title: str
    tier: str
    business_types: list[str]
    tasks: list[str]
    body: str
    kind: str  # "agent" или "skill"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Извлекает YAML-подобный frontmatter и тело документа."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text

    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = [v.strip() for v in value[1:-1].split(",")]
        else:
            meta[key.strip()] = value

    return meta, match.group(2).strip()


def load_catalog() -> list[CatalogItem]:
    items: list[CatalogItem] = []

    for kind, subdir in (("agent", "agents"), ("skill", "skills")):
        for path in (CATALOG_DIR / subdir).glob("*.md"):
            meta, body = _parse_frontmatter(path.read_text())
            if not meta:
                continue
            items.append(CatalogItem(
                name=meta.get("name", path.stem),
                title=meta.get("title", path.stem),
                tier=meta.get("tier", "free"),
                business_types=meta.get("business_types", []),
                tasks=meta.get("tasks", []),
                body=body,
                kind=kind,
            ))

    return items


def match_catalog(
    business_type: str,
    selected_tasks: list[str],
    tier: str = "free",
    rag_agents: list[str] | None = None,
    rag_skills: list[str] | None = None,
) -> tuple[list[CatalogItem], list[CatalogItem]]:
    """
    Возвращает (agents, skills) подходящие под профиль пользователя.

    Если переданы rag_agents/rag_skills — используем их (результат RAG-поиска).
    Иначе — keyword matching по каталогу.
    """
    all_items = load_catalog()
    allowed_tiers = {"free"} if tier == "free" else {"free", "pro"}

    # RAG-режим: берём конкретные агенты/скилы из похожих конфигураций
    if rag_agents is not None:
        agents = [i for i in all_items if i.kind == "agent" and i.name in rag_agents and i.tier in allowed_tiers]
        skills = [i for i in all_items if i.kind == "skill" and i.name in (rag_skills or []) and i.tier in allowed_tiers]
        return agents, skills

    # Keyword-режим (fallback)
    def matches(item: CatalogItem) -> bool:
        if item.tier not in allowed_tiers:
            return False
        biz_ok = not item.business_types or business_type in item.business_types
        task_ok = bool(set(item.tasks) & set(selected_tasks)) if item.tasks else True
        return biz_ok and task_ok

    matched = [i for i in all_items if matches(i)]
    agents = [i for i in matched if i.kind == "agent"]
    skills = [i for i in matched if i.kind == "skill"]

    return agents, skills
