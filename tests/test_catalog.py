"""Тесты каталога агентов и матчера."""
import pytest

from jarvisfather.catalog.loader import load_catalog, match_catalog


def test_catalog_loads():
    items = load_catalog()
    assert len(items) >= 5, "Каталог должен содержать минимум 5 элементов"


def test_catalog_has_agents_and_skills():
    items = load_catalog()
    agents = [i for i in items if i.kind == "agent"]
    skills = [i for i in items if i.kind == "skill"]
    assert len(agents) >= 3
    assert len(skills) >= 1


def test_catalog_tiers():
    items = load_catalog()
    tiers = {i.tier for i in items}
    assert "free" in tiers
    assert "pro" in tiers


def test_match_ecommerce_marketing():
    agents, skills = match_catalog("ecommerce", ["marketing"])
    agent_names = [a.name for a in agents]
    assert "marketing-content" in agent_names
    assert "ecommerce-specialist" in agent_names


def test_match_services_email():
    agents, skills = match_catalog("services", ["email", "clients"])
    agent_names = [a.name for a in agents]
    assert "email-writer" in agent_names
    assert "client-support" in agent_names


def test_free_tier_excludes_pro():
    agents, _ = match_catalog("services", ["analytics", "research"], tier="free")
    pro_agents = [a for a in agents if a.tier == "pro"]
    assert len(pro_agents) == 0, "Free тариф не должен включать pro-агентов"


def test_pro_tier_includes_pro():
    agents, _ = match_catalog("services", ["analytics", "research"], tier="pro")
    pro_agents = [a for a in agents if a.tier == "pro"]
    assert len(pro_agents) > 0, "Pro тариф должен включать pro-агентов"


def test_rag_override():
    """RAG результаты имеют приоритет над keyword-matching."""
    agents, skills = match_catalog(
        "ecommerce",
        ["marketing"],
        rag_agents=["presentations"],
        rag_skills=["summarize"],
    )
    assert any(a.name == "presentations" for a in agents)
    assert any(s.name == "summarize" for s in skills)


def test_unknown_business_type():
    """Неизвестный тип бизнеса не должен вызывать ошибку."""
    agents, skills = match_catalog("unknown_biz", ["marketing"])
    assert isinstance(agents, list)
    assert isinstance(skills, list)
