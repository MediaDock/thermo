"""Shared helpers for the Epson thermal printer (/dev/usb/lp0)."""

import textwrap
from contextlib import contextmanager
from pathlib import Path

from escpos.printer import File

PRINTER_DEV = "/dev/usb/lp0"
LINE_WIDTH  = 21    # characters per line at double width (80 mm paper)


@contextmanager
def open_printer():
    """Yield an open printer, or None if it is not available.

    Errors raised while printing are logged instead of propagated,
    and the device is always closed afterwards.
    """
    try:
        p = File(PRINTER_DEV)
    except Exception as e:
        print(f"[!] Printer not available: {e}")
        yield None
        return

    try:
        yield p
    except Exception as e:
        print(f"[!] Printer error: {e}")
    finally:
        try:
            p.close()
        except Exception:
            pass


def rule() -> str:
    """A full-width horizontal line at double width."""
    return "-" * LINE_WIDTH + "\n"


def wrap(text: str) -> str:
    """Wrap each line of text to LINE_WIDTH, keeping blank lines."""
    return "\n".join(
        textwrap.fill(line, width=LINE_WIDTH) if line else ""
        for line in text.splitlines()
    )


def load_logo(path: Path, width: int):
    """Load a logo flattened onto white (transparent areas would print black).

    Returns a 1-bit PIL image scaled to `width` px, or None if unavailable.
    """
    from PIL import Image

    if not path.exists():
        print(f"[!] No logo at {path}, printing without")
        return None
    try:
        img = Image.open(path).convert("RGBA")
    except Exception as e:
        print(f"[!] Cannot read logo, printing without: {e}")
        return None
    bg = Image.new("RGBA", img.size, "white")
    img = Image.alpha_composite(bg, img).convert("L")
    height = round(img.height * width / img.width)
    img = img.resize((width, height), Image.LANCZOS)
    # Hard black/white threshold for crisp edges instead of dithering
    return img.point(lambda v: 0 if v < 128 else 255, "1")
