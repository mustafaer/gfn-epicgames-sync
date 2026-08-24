"""Filesystem locations, resolved per platform.

Data is kept outside the source tree so the tool behaves correctly when
installed as a package. Override with the ``EPICSYNC_DATA_DIR`` env var.
"""
import os
import sys
from pathlib import Path

APP = "gfn-epicgames-sync"


def _default_data_dir() -> Path:
    override = os.environ.get("EPICSYNC_DATA_DIR")
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return Path(base or Path.home() / "AppData/Local") / APP
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support" / APP
    # Linux / BSD - XDG
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / APP


DATA = _default_data_dir()


def ensure_data_dir() -> Path:
    """Create the data directory. Called once from the CLI entry point.

    Importing a module should not touch the filesystem, so this is explicit
    rather than a side effect of ``import epicsync.paths``.
    """
    DATA.mkdir(parents=True, exist_ok=True)
    return DATA


GFN_CATALOG = DATA / "gfn-catalog.json"     # NVIDIA public supported-games list
EPIC_LIBRARY = DATA / "epic-library.json"   # normalized legendary output
PLAN = DATA / "plan.json"                   # catalog-based match plan
REPORT = DATA / "report.md"                 # human-readable plan report
STATE = DATA / "mark-state.json"            # resumable progress
LIBRARY_IDS = DATA / "library-ids.json"     # GFN "My Library" game ids
AUDIT = DATA / "audit.json"                 # per-game ownership snapshot
PROFILE = DATA / "browser-profile"          # persistent Playwright session
