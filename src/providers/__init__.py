from src.providers.base import BaseComicProvider
from src.providers.readcomiconline import ReadComicOnlineProvider
from src.providers.rcostation import RcoStationProvider

PROVIDERS: dict[str, type[BaseComicProvider]] = {
    "readcomiconline": ReadComicOnlineProvider,
    "rcostation": RcoStationProvider,
}

DEFAULT_PROVIDER = "rcostation"


def get_provider(name: str | None = None, **kwargs) -> BaseComicProvider:
    """Instantiate and return a provider by name.

    Falls back to ``DEFAULT_PROVIDER`` when *name* is ``None``.
    """
    key = name or DEFAULT_PROVIDER
    if key not in PROVIDERS:
        available = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"Unknown provider '{key}'. Available: {available}")
    return PROVIDERS[key](**kwargs)


def list_providers() -> list[str]:
    """Return sorted list of registered provider names."""
    return sorted(PROVIDERS)
