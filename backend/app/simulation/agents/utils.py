"""Shared utilities for agent implementations."""

from __future__ import annotations

from app.simulation.models import MarketDimension

_DIMENSION_VALUES = {d.value for d in MarketDimension}


def _parse_dimension(raw: str | None) -> MarketDimension | None:
    """Parse a dimension string (value like 'user_adoption') into MarketDimension, or None."""
    if not raw:
        return None
    val = raw.lower()
    if val in _DIMENSION_VALUES:
        return MarketDimension(val)
    return None
