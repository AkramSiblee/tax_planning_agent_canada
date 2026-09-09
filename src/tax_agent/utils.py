"""Shared formatting helpers. See skills/report-generation/SKILL.md."""
from __future__ import annotations


def format_currency(value: float) -> str:
    """Always two decimals, thousands separator, negatives in parentheses."""
    if value < 0:
        return f"(${abs(value):,.2f})"
    return f"${value:,.2f}"


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def slugify(name: str) -> str:
    """Turn a client/entity name into a filesystem-safe folder slug."""
    keep = [c.lower() if c.isalnum() else "-" for c in name.strip()]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")
