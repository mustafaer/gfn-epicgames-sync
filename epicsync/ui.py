"""Console output helpers.

Windows terminals are not guaranteed to be UTF-8, so symbols degrade to
ASCII when the active stdout encoding cannot represent them.
"""
import sys

_SYMBOLS = {
    "ok": ("✓", "[ok]"),
    "skip": ("⏭", "[skip]"),
    "warn": ("⚠", "[!]"),
    "fail": ("✗", "[fail]"),
    "dot": ("·", "-"),
    "arrow": ("→", "->"),
}


def _unicode_ok() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or ""
    if encoding.lower().replace("-", "") in {"utf8", "utf16", "utf32"}:
        return True
    try:
        "✓⏭⚠✗·→".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError, TypeError):
        return False


_RICH = _unicode_ok()


def sym(name: str) -> str:
    rich, plain = _SYMBOLS[name]
    return rich if _RICH else plain


def say(*parts):
    """Print a line, replacing any symbol that the terminal cannot encode."""
    text = " ".join(str(p) for p in parts)
    if not _RICH:
        for rich, plain in _SYMBOLS.values():
            text = text.replace(rich, plain)
    print(text, flush=True)
