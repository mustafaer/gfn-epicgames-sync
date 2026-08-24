"""Audits GeForce NOW ownership and reverts incorrect Epic entries.

GFN lets you assert ownership manually, and that assertion is never verified.
A game marked as owned but missing from the real Epic library will fail to
launch, because the cloud machine signs in to Epic and cannot find it.

This module walks GFN's own "My Library", records the storefront GFN
attributes to each game, and flags the ones claimed as Epic that the Epic
account does not actually own.
"""
import json
import time

from playwright.sync_api import sync_playwright

from . import epiclib, mark
from .normalize import norm, norm_loose, same_game
from .paths import AUDIT, LIBRARY_IDS
from .ui import say, sym

TITLE_SELECTOR = "[class*=evidence-panel-title-text]"
SEE_MORE = '[aria-label="See more"]'
UNMARK_TEXT = "Unmark as owned"
GAME_URL = "https://play.geforcenow.com/games?game-id={game_id}&lang=en_US"

# Tile artwork URLs embed the game id, which is far cheaper to collect than
# opening each tile: https://img.nvidiagrid.net/apps/<uuid>/...
_TILE_IDS_JS = """() => [...document.querySelectorAll('gfn-game-tile img')]
    .map(img => (img.src.match(/\\/apps\\/([0-9a-f-]{36})\\//) || [])[1])
    .filter(Boolean)"""

_VIEWPORT = "cdk-virtual-scroll-viewport"


def collect_library_ids(page, timeout_s: int = 240):
    """Scroll the virtualised My Library grid and collect every game id."""
    page.locator('[aria-label="SEE ALL My Library"]').first.click(timeout=15000)
    page.wait_for_timeout(4500)

    seen, started, stagnant, offset = set(), time.time(), 0, 0
    while stagnant < 6 and time.time() - started < timeout_s:
        before = len(seen)
        seen.update(page.evaluate(_TILE_IDS_JS))
        offset += 600
        page.evaluate(
            f"(y) => {{const v=document.querySelector('{_VIEWPORT}'); if (v) v.scrollTop=y;}}",
            offset,
        )
        page.wait_for_timeout(450)
        stagnant = stagnant + 1 if len(seen) == before else 0

        at_end = page.evaluate(
            f"() => {{const v=document.querySelector('{_VIEWPORT}');"
            " return v ? v.scrollTop + v.clientHeight >= v.scrollHeight - 40 : true;}"
        )
        if at_end and stagnant >= 2:
            break

    # Tiles at the very top can be recycled away mid-scroll; sweep once more.
    page.evaluate(f"() => {{const v=document.querySelector('{_VIEWPORT}'); if (v) v.scrollTop=0;}}")
    page.wait_for_timeout(900)
    seen.update(page.evaluate(_TILE_IDS_JS))

    ids = sorted(seen)
    LIBRARY_IDS.write_text(json.dumps(ids, indent=1), encoding="utf-8")
    return ids


def open_by_id(page, game_id: str) -> bool:
    """Deep-link straight to a game - much faster than searching by title."""
    page.goto(GAME_URL.format(game_id=game_id), wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_selector(mark.PANEL, timeout=12000)
        return True
    except Exception:
        return False


def read_game(page):
    try:
        title = page.locator(TITLE_SELECTOR).first.inner_text(timeout=3000).strip()
    except Exception:
        title = None
    return title, mark.selected_store(page)


def run_audit(refresh_ids: bool = False):
    """Snapshot every library entry and compare Epic claims to reality."""
    library = epiclib.fetch()
    owned = {norm(g["title"]) for g in library} | {norm_loose(g["title"]) for g in library}

    rows = []
    with sync_playwright() as pw:
        context = mark.open_context(pw)
        page = context.pages[0] if context.pages else context.new_page()
        if not mark.boot(page):
            context.close()
            raise RuntimeError("Not signed in to GFN. Run: epicsync login")

        if LIBRARY_IDS.exists() and not refresh_ids:
            ids = json.loads(LIBRARY_IDS.read_text(encoding="utf-8"))
        else:
            ids = collect_library_ids(page)
        say(f"Scanning {len(ids)} games in your GFN library\n")

        for index, game_id in enumerate(ids, 1):
            if not open_by_id(page, game_id):
                continue
            title, store = read_game(page)
            if not title:
                continue

            is_epic = mark.EPIC.lower() in store.lower()
            in_library = norm(title) in owned or norm_loose(title) in owned
            rows.append({
                "game_id": game_id, "title": title, "store": store,
                "epic": is_epic, "in_epic_library": in_library,
            })

            if is_epic and not in_library:
                say(f"[{index}/{len(ids)}] {sym('warn')}  {title} - "
                    "claimed on Epic but not in your library")
            elif index % 25 == 0:
                say(f"[{index}/{len(ids)}] ...")

        context.close()

    AUDIT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def suspects(rows=None):
    """Games GFN believes you own on Epic that your Epic library lacks.

    The library check is recomputed here rather than trusting the flag stored
    at scan time: a stale or truncated library snapshot would otherwise turn
    legitimately owned games into deletion candidates.
    """
    if rows is None:
        rows = json.loads(AUDIT.read_text(encoding="utf-8"))

    library = epiclib.fetch()
    if not library:
        raise RuntimeError(
            "Your Epic library came back empty; refusing to flag anything. "
            "Check `legendary list-games --platform Windows`."
        )
    exact = {norm(g["title"]) for g in library} | {norm_loose(g["title"]) for g in library}

    flagged = []
    for row in rows:
        if not row["epic"]:
            continue
        title = row["title"]
        if norm(title) in exact or norm_loose(title) in exact:
            continue
        if any(same_game(title, g["title"]) for g in library):
            continue
        flagged.append(row)
    return flagged


def unmark(targets, dry_run: bool = False, delay: float = 0.5, assume_yes: bool = False):
    """Revert ownership via the game menu's 'Unmark as owned' entry.

    Reverting is destructive: a claim removed by mistake has to be re-made by
    hand. Unless ``dry_run`` is set, an explicit confirmation is required.
    """
    if not dry_run and not assume_yes:
        say(f"\n{sym('warn')} This removes {len(targets)} ownership claim(s) from your "
            "GFN library.")
        say("Titles matched loosely against your Epic library may still be games "
            "you own.")
        try:
            answer = input("Type 'yes' to continue: ").strip().lower()
        except EOFError:
            answer = ""
        if answer != "yes":
            say("Aborted; nothing changed.")
            return 0, 0

    reverted = failed = 0
    with sync_playwright() as pw:
        context = mark.open_context(pw)
        page = context.pages[0] if context.pages else context.new_page()
        if not mark.boot(page):
            context.close()
            raise RuntimeError("Not signed in to GFN. Run: epicsync login")

        for index, target in enumerate(targets, 1):
            name = target["title"]
            say(f"[{index}/{len(targets)}] {sym('arrow')} {name}")
            try:
                if not open_by_id(page, target["game_id"]):
                    raise RuntimeError("game page did not open")

                _, store = read_game(page)
                if mark.EPIC.lower() not in store.lower():
                    say(f"      {sym('skip')}  no longer an Epic claim ({store})")
                    continue

                page.locator(SEE_MORE).first.click(timeout=8000)
                page.wait_for_timeout(1200)
                entry = page.get_by_text(UNMARK_TEXT, exact=True).first
                entry.wait_for(state="visible", timeout=5000)

                if dry_run:
                    say(f"      [dry-run] would click '{UNMARK_TEXT}'")
                    page.keyboard.press("Escape")
                    reverted += 1
                    continue

                entry.click(timeout=6000)
                page.wait_for_timeout(2000)
                for label in ("CONTINUE", "CONFIRM", "UNMARK", "YES", "OK"):
                    try:
                        mark.dialog_button(page, label, 2500)
                        page.wait_for_timeout(1500)
                        break
                    except Exception:
                        continue

                page.wait_for_timeout(1500)
                _, after = read_game(page)
                if mark.EPIC.lower() in after.lower() and "owned" in after.lower():
                    raise RuntimeError(f"still claimed on Epic ({after})")
                reverted += 1
                say(f"      {sym('ok')} reverted (now: {after or '-'})")

            except Exception as error:
                failed += 1
                say(f"      {sym('fail')} {str(error)[:110]}")
            time.sleep(delay)

        context.close()

    verb = "would be reverted" if dry_run else "reverted"
    say(f"\nSummary: {reverted} {verb}, {failed} errors")
    return reverted, failed
