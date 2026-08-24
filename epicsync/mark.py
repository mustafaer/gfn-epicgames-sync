"""Marks Epic Games Store ownership inside the GeForce NOW web client.

Everything here was derived from the live client; the behavior it depends on:

* The Angular app never bootstraps headless, so the browser always runs headed.
* The search box is hidden from the accessibility tree; it is reached by
  placeholder, and a query only executes once Enter is pressed.
* ``MARK AS OWNED`` starts a three-stage flow inside ``gfn-ownership-dialog``:
  1. a resync of connected store accounts ("Finding where you own this game"),
  2. a store picker when several storefronts carry the game,
  3. a confirmation naming the store that will be marked.
* A ``BUY`` button sits next to ``MARK AS OWNED``; it must never be clicked.
"""
import json
import re
import time

from playwright.sync_api import sync_playwright

from .browser import launch
from .normalize import covers, norm, norm_loose
from .paths import PROFILE, STATE
from .ui import say, sym

BASE = "https://play.geforcenow.com/"
SEARCH_INPUT = "input[placeholder*='Search' i]"
PANEL = "[class*=store-platform-options-container]"

DIALOG = "gfn-ownership-dialog"
STAGE = "gfn-ownership-stage-layout"
EPIC = "Epic Games Store"
NOT_FOUND = "game not found"

OWN_BUTTON_TEXTS = ("MARK AS OWNED", "I OWN THIS GAME")
ALREADY_OWNED_TEXTS = ("PLAY", "RESUME", "INSTALL")
# Never click a control containing any of these - purchase protection.
FORBIDDEN_TEXTS = ("BUY", "PURCHASE", "SUBSCRIBE", "UPGRADE")

# Locates the tile for a title and tags it, so the click target is unambiguous.
# Index arithmetic is avoided on purpose: a visibility-filtered index in JS does
# not line up with Playwright's nth(), which also counts hidden elements.
_VISIBLE_LABELS_JS = """() => [...document.querySelectorAll('[aria-label]')]
    .filter(el => el.offsetParent !== null)
    .map(el => el.getAttribute('aria-label'))
    .filter(Boolean)"""

# Tags one specific label so the click target is unambiguous. Index arithmetic
# is avoided on purpose: a visibility-filtered index computed in JS does not
# line up with Playwright's nth(), which also counts hidden elements.
_TAG_JS = """(wanted) => {
    document.querySelectorAll('[data-epicsync-target]')
        .forEach(el => el.removeAttribute('data-epicsync-target'));
    const node = [...document.querySelectorAll('[aria-label]')]
        .filter(el => el.offsetParent !== null)
        .find(el => el.getAttribute('aria-label') === wanted);
    if (!node) return false;
    node.setAttribute('data-epicsync-target', '1');
    return true;
}"""


def pick_label(labels, wanted):
    """Choose the search result that really is ``wanted``.

    Matching is delegated to :func:`covers`, which is directional: a GFN
    result may add words to the title you asked for, but never the reverse.
    A plain prefix test such as ``"airborne kingdom ost".startsWith("airborne
    kingdom")`` opens a different product - a soundtrack entry lands on the
    base game and runs the ownership flow against it.
    """
    exact = [label for label in labels if norm(label) == norm(wanted)]
    if exact:
        return exact[0]
    loose = [label for label in labels if norm_loose(label) == norm_loose(wanted)]
    if loose:
        return loose[0]
    for label in labels:
        if covers(label, wanted):
            return label
    return None


# --------------------------------------------------------------------------- #
# page lifecycle
# --------------------------------------------------------------------------- #
def open_context(pw, headless: bool = False):
    return launch(pw, headless=headless)


def boot(page, attempts: int = 14) -> bool:
    """Load the client and wait for the Angular shell. False if signed out."""
    page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
    for _ in range(attempts):
        page.wait_for_timeout(2500)
        if page.evaluate("() => document.querySelectorAll('*').length") > 250:
            return "loginwall" not in page.url
    return False


def warmup(page):
    """The first query after boot is noticeably slower; spend it on a dummy."""
    try:
        _search(page, "warmup")
        page.wait_for_timeout(2500)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# element helpers
# --------------------------------------------------------------------------- #
def buttons(page):
    found = []
    for button in page.get_by_role("button").all():
        try:
            found.append((button, (button.inner_text() or "").strip().upper()))
        except Exception:
            continue
    return found


def find_button(page, wanted):
    for button, text in buttons(page):
        if not text or any(bad in text for bad in FORBIDDEN_TEXTS):
            continue
        if any(word in text for word in wanted):
            return button, text
    return None, None


def selected_store(page) -> str:
    """Which storefront GFN currently attributes this game to."""
    try:
        value = page.evaluate(
            """() => {
                const chosen = document.querySelector('[class*=selected-store-details]');
                const options = document.querySelector('[class*=store-platform-options-container]');
                const node = chosen || options;
                return node ? (node.innerText || '').replace(/\\n/g, ' ').trim() : '';
            }"""
        )
        return (value or "?")[:60]
    except Exception:
        return "?"


# --------------------------------------------------------------------------- #
# navigation
# --------------------------------------------------------------------------- #
def _search(page, title: str):
    box = page.locator(SEARCH_INPUT).first
    try:
        box.click(timeout=8000)
    except Exception:
        boot(page)                       # the shell can break after a flow
        box = page.locator(SEARCH_INPUT).first
        box.click(timeout=15000)
    box.fill("")
    box.fill(title)
    page.wait_for_timeout(350)           # let Angular register the value
    page.keyboard.press("Enter")         # GFN does not search as you type


def open_game(page, title: str, find_timeout: int = 3500) -> bool:
    """Search for a title and open its detail panel.

    Waiting is condition-based: the loop polls the rendered result labels until
    one of them matches, so a hit returns as soon as the tile appears and a
    title GFN does not carry costs only ``find_timeout``.
    """
    _search(page, title)

    deadline = time.time() + find_timeout / 1000
    chosen = None
    while time.time() < deadline:
        labels = page.evaluate(_VISIBLE_LABELS_JS)
        chosen = pick_label(labels, title)
        if chosen:
            break
        page.wait_for_timeout(250)

    if not chosen or not page.evaluate(_TAG_JS, chosen):
        return False

    page.locator("[data-epicsync-target]").first.click(timeout=8000)
    try:
        page.wait_for_selector(PANEL, timeout=8000)
    except Exception:
        return False
    return True


def close_details(page):
    for button in page.get_by_role("button", name=re.compile("close game details", re.I)).all():
        try:
            button.click(timeout=2000)
            page.wait_for_selector(PANEL, state="detached", timeout=3000)
            return
        except Exception:
            pass
    page.keyboard.press("Escape")
    try:
        page.wait_for_selector(PANEL, state="detached", timeout=3000)
    except Exception:
        page.wait_for_timeout(500)


# --------------------------------------------------------------------------- #
# ownership flow
# --------------------------------------------------------------------------- #
def stage_text(page) -> str:
    try:
        return (page.locator(STAGE).first.inner_text(timeout=1500) or "").replace("\n", " | ")
    except Exception:
        return ""


def wait_stage(page, timeout_s: int = 90) -> str:
    """Wait out the resync screen and return the settled stage text."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        text = stage_text(page)
        lowered = text.lower()
        if text and "finding where you own" not in lowered and "may take some time" not in lowered:
            return text
        page.wait_for_timeout(2000)
    return stage_text(page)


def epic_available(stage: str) -> bool:
    """True unless the Epic row in the store picker is tagged 'Game not found'."""
    parts = [part.strip() for part in stage.split("|") if part.strip()]
    for index, part in enumerate(parts):
        if part.lower() == EPIC.lower():
            following = parts[index + 1].lower() if index + 1 < len(parts) else ""
            return NOT_FOUND not in following
    return False


def dialog_click(page, text: str, timeout: int = 8000):
    """Scope clicks to the dialog; identical labels sit behind the overlay."""
    page.locator(DIALOG).get_by_text(text, exact=True).first.click(timeout=timeout)


def dialog_button(page, name: str, timeout: int = 8000):
    page.locator(DIALOG).get_by_role(
        "button", name=re.compile(f"^{name}$", re.I)
    ).first.click(timeout=timeout)


def exit_dialog(page):
    for attempt in (lambda: dialog_button(page, "EXIT", 4000),
                    lambda: page.keyboard.press("Escape")):
        try:
            attempt()
            page.wait_for_timeout(1500)
            if not stage_text(page):
                return
        except Exception:
            continue


def mark_one(page, dry_run: bool) -> str:
    """Run the ownership flow for the open game.

    Returns ``marked``, ``dry`` or ``skip:<reason>``.
    """
    button, _ = find_button(page, OWN_BUTTON_TEXTS)
    if button is None:
        raise RuntimeError("no 'MARK AS OWNED' control")
    button.click(timeout=8000)

    stage = wait_stage(page)
    if not stage:
        raise RuntimeError("ownership dialog did not open")

    if "choose a game store" in stage.lower():
        if not epic_available(stage):
            exit_dialog(page)
            return "skip:epic-unavailable"
        dialog_click(page, EPIC)
        page.wait_for_timeout(3000)
        stage = wait_stage(page)

    # Safety gate: never confirm unless the dialog names the Epic store.
    if EPIC.lower() not in stage.lower():
        parts = [p.strip() for p in stage.split("|") if p.strip()]
        store = next((p for p in parts[1:] if p.lower() != "pc digital version"), "?")
        exit_dialog(page)
        return f"skip:wrong-store({store[:24]})"

    if dry_run:
        exit_dialog(page)
        return "dry"

    dialog_button(page, "CONTINUE")
    page.wait_for_timeout(4000)
    exit_dialog(page)
    return "marked"


# --------------------------------------------------------------------------- #
# progress state
# --------------------------------------------------------------------------- #
def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"done": {}, "failed": {}}


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def login(timeout_min: int = 15) -> bool:
    """Open the client so the user can sign in; the session is persisted."""
    deadline = time.time() + timeout_min * 60
    with sync_playwright() as pw:
        context = open_context(pw)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        say(sym("arrow"), "Sign in with your NVIDIA account in the window that opened.")
        say(sym("arrow"), "Accept any cookie or terms banner yourself; epicsync will not.")
        while time.time() < deadline:
            try:
                nodes = page.evaluate("() => document.querySelectorAll('*').length")
            except Exception:
                nodes = 0
            if "loginwall" not in page.url and nodes > 250:
                say(sym("ok"), f"Signed in. Session stored in {PROFILE}")
                page.wait_for_timeout(2000)
                context.close()
                return True
            page.wait_for_timeout(3000)
        say(sym("fail"), "Timed out waiting for sign-in.")
        context.close()
        return False


def inspect(title: str):
    """Dump the buttons on a game page - useful when GFN changes its UI."""
    with sync_playwright() as pw:
        context = open_context(pw)
        page = context.pages[0] if context.pages else context.new_page()
        if not boot(page):
            say(sym("fail"), "Not signed in. Run: epicsync login")
            context.close()
            return
        warmup(page)
        if not open_game(page, title):
            say(sym("fail"), f"'{title}' was not found in search results")
            context.close()
            return
        say(f"\nURL: {page.url}\nStore: {selected_store(page)}\n\nButtons:")
        for _, text in buttons(page):
            if text:
                say("   ", repr(text))
        context.close()


def run(targets, dry_run: bool = False, delay: float = 0.4):
    """Process ``targets`` (dicts with ``gfn_id`` and ``gfn_title``)."""
    state = load_state()
    marked = skipped = failed = absent = 0
    total = len(targets)

    with sync_playwright() as pw:
        context = open_context(pw)
        page = context.pages[0] if context.pages else context.new_page()

        if not boot(page):
            context.close()
            raise RuntimeError("Not signed in to GFN. Run: epicsync login")
        warmup(page)

        for index, target in enumerate(targets, 1):
            key, name = str(target["gfn_id"]), target["gfn_title"]

            if key in state["done"]:
                say(f"[{index}/{total}] {sym('skip')}  {name}")
                skipped += 1
                continue

            say(f"[{index}/{total}] {sym('arrow')} {name}")
            try:
                if not open_game(page, name):
                    # Not carried by GFN at all - an ordinary outcome.
                    say(f"      {sym('dot')}  not on GFN")
                    state["done"][key] = {"title": name, "how": "skip:not-on-gfn"}
                    absent += 1
                    save_state(state)
                    continue

                _, playable = find_button(page, ALREADY_OWNED_TEXTS)
                if playable:
                    store = selected_store(page)
                    is_epic = EPIC.lower() in store.lower()
                    suffix = "" if is_epic else f"  {sym('warn')} not Epic"
                    say(f"      {sym('skip')}  playable ({playable}) - {store}{suffix}")
                    state["done"][key] = {
                        "title": name, "how": f"already:{playable}",
                        "store": store, "epic": is_epic,
                    }
                    skipped += 1
                    save_state(state)
                    close_details(page)
                    continue

                result = mark_one(page, dry_run)
                if result == "marked":
                    marked += 1
                    say(f"      {sym('ok')} marked as owned on Epic")
                    state["done"][key] = {"title": name, "how": "marked", "epic": True}
                elif result == "dry":
                    marked += 1
                    say("      [dry-run] reached the Epic confirmation")
                else:
                    skipped += 1
                    say(f"      {sym('skip')}  {result}")
                    state["done"][key] = {"title": name, "how": result}
                save_state(state)
                close_details(page)

            except Exception as error:
                message = str(error)
                # A dead browser fails every remaining game identically; stop
                # rather than grinding through the list recording noise.
                if "has been closed" in message or "Target closed" in message:
                    say(f"\n{sym('fail')} The browser closed unexpectedly - stopping.")
                    say("Progress is saved; re-run the same command to resume.")
                    break
                failed += 1
                state["failed"][key] = {"title": name, "error": message[:300]}
                save_state(state)
                say(f"      {sym('fail')} {message[:120]}")
                try:
                    close_details(page)
                except Exception:
                    pass

            time.sleep(delay)

        context.close()

    verb = "would be marked" if dry_run else "marked on Epic"
    say(f"\nSummary: {marked} {verb} | {skipped} skipped | "
        f"{absent} not on GFN | {failed} errors")
    return marked, skipped, failed, absent
