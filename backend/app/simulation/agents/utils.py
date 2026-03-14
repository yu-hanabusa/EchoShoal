"""Shared utilities for agent implementations."""

from __future__ import annotations

from app.simulation.models import SkillCategory

_SKILL_VALUES = {s.value for s in SkillCategory}


def _parse_skill(raw: str | None) -> SkillCategory | None:
    """Parse a skill string (value like 'ai_ml') into SkillCategory, or None."""
    if not raw:
        return None
    val = raw.lower()
    if val in _SKILL_VALUES:
        return SkillCategory(val)
    return None
