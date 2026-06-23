from src.providers.base import BaseComicProvider


class ReadComicOnlineProvider(BaseComicProvider):
    """Provider for readcomiconline.li (defunct since May 2026)."""

    name = "readcomiconline"
    base_url = "https://readcomiconline.li"
