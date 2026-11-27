"""reels-wiki: saved Instagram Reels -> atomic notes in an Obsidian LLM Wiki vault.

SDK entry points (all importable without side effects):

    from reels_wiki import enqueue, import_ig_export, process_queue, load_config
"""
from __future__ import annotations

__version__ = "0.1.6"  # x-release-please-version

from .core.config import Config, ConfigError, load_config
from .ingestion.ig_export import import_ig_export
from .ingestion.queue_manager import QueueManager, enqueue, extract_shortcode, normalize_url, queue_stats

__all__ = [
    "Config",
    "ConfigError",
    "QueueManager",
    "enqueue",
    "extract_shortcode",
    "import_ig_export",
    "load_config",
    "normalize_url",
    "process_queue",
    "queue_stats",
    "reprocess",
]


def __getattr__(name: str):  # lazy: pipeline pulls in heavy optional deps only when used
    if name in {"process_queue", "reprocess"}:
        from .pipeline import runner

        return getattr(runner, name)
    raise AttributeError(name)
