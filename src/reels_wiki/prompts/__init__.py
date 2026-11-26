"""Jinja2 prompt loader for ``reels_wiki``."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from jinja2 import Environment, PackageLoader


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=PackageLoader("reels_wiki", "prompts"),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_prompt(template_name: str, **context: Any) -> str:
    """Render a Jinja2 template from ``reels_wiki/prompts/`` with the given context."""
    return _env().get_template(template_name).render(**context).strip()
