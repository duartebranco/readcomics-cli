"""
Render images inline in the terminal using ANSI 24-bit color and half-block characters.

This technique uses the lower half block character with foreground color set to
the bottom pixel and background color set to the top pixel, giving us 2 vertical pixels
per character cell. Works in virtually any terminal that supports 24-bit/truecolor
(kitty, iTerm2, WezTerm, GNOME Terminal, Windows Terminal, etc.).
"""

import io
import os
import sys

try:
    from PIL import Image as PILImage

    PILLOW_AVAILABLE = True
except ImportError:
    PILImage = None  # type: ignore[assignment,misc]
    PILLOW_AVAILABLE = False


def _supports_color() -> bool:
    """Best-effort check for 24-bit color support."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return True
    term = os.environ.get("TERM", "").lower()
    if "256color" in term or "kitty" in term:
        return True
    # Assume most modern terminals support it
    return True


def render_image(
    image_data: bytes,
    max_width: int = 40,
    max_height: int = 30,
    indent: int = 4,
) -> "str | None":
    """
    Render raw image bytes as colored half-block characters.

    Args:
        image_data: Raw bytes of a JPEG/PNG/etc image.
        max_width: Maximum number of columns to use.
        max_height: Maximum number of character rows (each row = 2 pixels).
        indent: Number of spaces to prepend to each line.

    Returns:
        A string with ANSI escape codes that, when printed, displays the image.
        Returns None if rendering isn't possible (missing Pillow, no color, etc.).
    """
    if not PILLOW_AVAILABLE or PILImage is None or not _supports_color():
        return None

    try:
        img = PILImage.open(io.BytesIO(image_data))
    except Exception:
        return None

    img = img.convert("RGB")

    # Resize to fit within max_width x (max_height * 2) pixels, preserving aspect ratio.
    # We multiply max_height by 2 because each character row represents 2 pixel rows.
    orig_w, orig_h = img.size
    max_pixel_h = max_height * 2

    scale = min(max_width / orig_w, max_pixel_h / orig_h)
    new_w = max(1, int(orig_w * scale))
    new_h = max(1, int(orig_h * scale))

    # Make height even so we always have pairs of rows
    if new_h % 2 != 0:
        new_h += 1

    # Use Resampling.LANCZOS on modern Pillow, fall back to LANCZOS constant
    try:
        resample = PILImage.Resampling.LANCZOS  # type: ignore[union-attr]
    except AttributeError:
        resample = PILImage.LANCZOS  # type: ignore[union-attr]

    img = img.resize((new_w, new_h), resample)
    pixels = img.load()  # type: ignore[assignment]

    prefix = " " * indent
    lines: list[str] = []

    for y in range(0, new_h, 2):
        chars: list[str] = []
        for x in range(new_w):
            # Top pixel -> background color, Bottom pixel -> foreground color
            px_top = pixels[x, y]  # type: ignore[index]
            r_top = px_top[0]  # type: ignore[index]
            g_top = px_top[1]  # type: ignore[index]
            b_top = px_top[2]  # type: ignore[index]

            if y + 1 < new_h:
                px_bot = pixels[x, y + 1]  # type: ignore[index]
                r_bot = px_bot[0]  # type: ignore[index]
                g_bot = px_bot[1]  # type: ignore[index]
                b_bot = px_bot[2]  # type: ignore[index]
            else:
                r_bot, g_bot, b_bot = r_top, g_top, b_top

            # \033[38;2;R;G;Bm  = set foreground (bottom pixel)
            # \033[48;2;R;G;Bm  = set background (top pixel)
            chars.append(
                f"\033[38;2;{r_bot};{g_bot};{b_bot}m"
                f"\033[48;2;{r_top};{g_top};{b_top}m"
                f"\u2584"
            )

        lines.append(prefix + "".join(chars) + "\033[0m")

    return "\n".join(lines)


def render_image_from_url(
    http_client: object,
    url: str,
    **kwargs: int,
) -> "str | None":
    """
    Convenience: fetch an image URL and render it.

    Args:
        http_client: An httpx.Client instance.
        url: The image URL to fetch.
        **kwargs: Passed to render_image (max_width, max_height, indent).

    Returns:
        Rendered string or None.
    """
    try:
        response = http_client.get(url, timeout=10)  # type: ignore[union-attr]
        response.raise_for_status()  # type: ignore[union-attr]
        return render_image(response.content, **kwargs)  # type: ignore[union-attr]
    except Exception:
        return None