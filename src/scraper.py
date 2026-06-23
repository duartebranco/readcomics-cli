"""Backward-compatible entry-point.

``from src.scraper import ComicScraper`` still works but new code should use
``from src.providers import get_provider`` instead.
"""

from src.providers import get_provider  # noqa: F401
from src.providers.base import BaseComicProvider as ComicScraper  # noqa: F401
