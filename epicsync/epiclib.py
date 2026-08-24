"""Reads the Epic Games library through the `legendary` CLI.

legendary performs Epic's official OAuth flow, so no credentials are ever
entered into epicsync itself. See https://github.com/legendary-gl/legendary
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import EPIC_LIBRARY

# Epic libraries also contain Unreal Engine marketplace assets. Real games
# carry a "games" category; asset packs carry "projects", "assets", etc.
REQUIRED_CATEGORY = "games"
SKIP_CATEGORIES = {"addons", "digitalextras", "plugins"}

# legendary defaults to the host platform - "Mac" on macOS - which lists only
# titles that ship a Mac build. GeForce NOW streams Windows builds, so asking
# for the host platform silently hides most of the library (261 vs 845 entries
# on the reference account) and would make an audit flag owned games as bogus.
PLATFORM = "Windows"


def executable() -> str:
    """Locate legendary, preferring the interpreter's own environment."""
    bin_dir = Path(sys.executable).parent
    candidates = [
        bin_dir / "legendary",
        bin_dir / "legendary.exe",
        bin_dir / "Scripts" / "legendary.exe",   # Windows venv layout
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which("legendary")
    if found:
        return found

    raise RuntimeError(
        "legendary was not found.\n"
        "Install it with:  pip install legendary-gl"
    )


def _run(args):
    env = dict(os.environ, PYTHONWARNINGS="ignore")
    return subprocess.run(
        [executable(), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _status():
    result = _run(["status", "--json"])
    if result.returncode != 0:
        return {}
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        return {}


def is_authenticated() -> bool:
    # legendary exits 0 even when signed out, reporting "<not logged in>".
    account = _status().get("account") or ""
    return bool(account) and not account.startswith("<")


def account() -> str:
    account_name = _status().get("account") or "?"
    return "?" if account_name.startswith("<") else account_name


def filter_games(raw):
    """Keep real games: drop DLC, add-ons and Unreal Engine marketplace assets."""
    games = []
    for entry in raw:
        metadata = entry.get("metadata") or {}
        categories = {
            (item.get("path") or "").lower()
            for item in (metadata.get("categories") or [])
        }
        if REQUIRED_CATEGORY not in categories:
            continue
        if categories & SKIP_CATEGORIES or entry.get("is_dlc"):
            continue

        title = entry.get("app_title") or metadata.get("title")
        if not title:
            continue
        games.append(
            {
                "app_name": entry.get("app_name"),
                "title": title,
                "namespace": (entry.get("asset_infos", {})
                              .get("Windows", {})
                              .get("namespace")),
            }
        )

    games.sort(key=lambda game: game["title"].lower())
    return games


def fetch(force: bool = False):
    """Return the owned Epic games, excluding DLC and marketplace assets."""
    if EPIC_LIBRARY.exists() and not force:
        return json.loads(EPIC_LIBRARY.read_text(encoding="utf-8"))

    result = _run(["list-games", "--platform", PLATFORM, "--json"])
    if result.returncode != 0:
        raise RuntimeError(
            "`legendary list-games` failed.\n"
            f"{(result.stderr or '').strip()[:800]}"
        )

    games = filter_games(json.loads(result.stdout))
    EPIC_LIBRARY.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding="utf-8")
    return games
