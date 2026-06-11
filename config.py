"""Shared Astroturf defaults and path helpers."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_SUBREDDIT = "redscarepod"
CULTURE_FEATURES_TEMPLATE = "data/culture/{subreddit}_features.json"


def resolve_subreddit(name: str | None = None) -> str:
    """Subreddit name without r/; SUBREDDIT env overrides when name is omitted."""
    return (name or os.environ.get("SUBREDDIT") or DEFAULT_SUBREDDIT).strip()


def culture_features_path(subreddit: str | None = None) -> Path:
    return Path(CULTURE_FEATURES_TEMPLATE.format(subreddit=resolve_subreddit(subreddit)))
