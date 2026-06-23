from src.providers.base import BaseComicProvider


class RcoStationProvider(BaseComicProvider):
    """Provider for rcostation.xyz."""

    name = "rcostation"
    base_url = "https://rcostation.xyz"
