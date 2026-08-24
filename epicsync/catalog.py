"""NVIDIA's public list of GeForce NOW supported games.

Note: this list is incomplete and can be stale. GFN's live client reports
roughly 2200 titles while the public JSON carries about 1550, and some
storefront entries disagree with the live UI. It is useful as a quick
pre-filter, but ``epicsync sweep`` deliberately bypasses it.
"""
import json
import urllib.request

from .paths import GFN_CATALOG

URL_TEMPLATE = (
    "https://static.nvidiagrid.net/supported-public-game-list/locales/gfnpc-{locale}.json"
)
USER_AGENT = "gfn-epicgames-sync (+https://github.com/mustafaer/gfn-epicgames-sync)"


def fetch(locale: str = "en-US", force: bool = False):
    """Download (or read from cache) the supported-games list."""
    if GFN_CATALOG.exists() and not force:
        return json.loads(GFN_CATALOG.read_text(encoding="utf-8"))

    request = urllib.request.Request(
        URL_TEMPLATE.format(locale=locale), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    # The locale-less gfnpc.json returns null; guard against that shape.
    if not isinstance(data, list) or not data:
        raise RuntimeError(
            f"Unexpected catalog payload ({type(data).__name__}). "
            "Try a different --locale."
        )

    GFN_CATALOG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def epic_titles(catalog):
    """Return only the available Epic Games Store entries."""
    entries = []
    for game in catalog:
        if (game.get("store") or "").strip().lower() != "epic":
            continue
        if (game.get("status") or "AVAILABLE").upper() != "AVAILABLE":
            continue
        entries.append(
            {
                "gfn_id": game.get("id"),
                "title": game.get("title"),
                "sort_name": game.get("sortName"),
                "publisher": game.get("publisher"),
                "genres": game.get("genres") or [],
                "optimized": bool(game.get("isFullyOptimized")),
            }
        )
    return entries
