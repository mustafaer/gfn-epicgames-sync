# How it works

Everything below was established against the live GeForce NOW client. None of
it is documented by NVIDIA, so it can change; [Troubleshooting](troubleshooting.md)
explains how to re-calibrate.

## Why the tool exists

GFN's Connections screen reports, per storefront, whether library sync is
supported. For a typical account:

| Store | Library sync | Resync button |
|---|---|---|
| Steam | 245 games synced | yes |
| Ubisoft Connect | 22 games synced | yes |
| Xbox | 21 games synced | yes |
| Battle.net | 10 games synced | yes |
| **Epic Games Store** | **Not supported** | **no** |

Epic is the only connected store with no library sync, so its games must be
marked by hand. Automatic sign-in is limited to Fortnite.

## Data sources

### Epic library — `legendary`

`legendary list-games --json` returns everything on the account. Three details
matter:

- **Always ask for the Windows platform.** legendary defaults to the *host*
  platform, so on macOS it lists only titles that ship a Mac build. On the
  reference account that is 261 entries against **845** for Windows. GeForce
  NOW streams Windows builds, so the host default silently hides most of the
  library — and made an early audit flag 161 genuinely owned games as bogus
  claims. epicsync always passes `--platform Windows`.

- Epic libraries also contain **Unreal Engine marketplace assets**, soundtracks
  and test builds. Real games carry a `games` category; asset packs carry
  `projects`, `asset-format/game-engine` and similar. Only entries with `games`
  are kept — on the reference account, 845 raw Windows entries became 705 games.
- DLC and add-ons are dropped via `addons`, `digitalextras`, `plugins`.

### GFN catalog — public JSON (unreliable)

`https://static.nvidiagrid.net/supported-public-game-list/locales/gfnpc-en-US.json`
returns about 1,550 entries. The locale-less `gfnpc.json` returns `null`.

This list should not be trusted as the source of truth:

- The live client reports **2,192** games against the JSON's 1,550.
- Titles present in GFN are missing from it entirely.
- Storefront data disagrees. The JSON lists an Epic entry for
  `Prison Architect`; the live client offers only Steam.

`epicsync sweep` therefore ignores it and asks the client directly.

## Driving the client

### The browser must be headed

The client is an Angular app (`gfn-root`). In headless Chromium it never
bootstraps — the DOM stays at ~64 nodes and the page sits on the NVIDIA splash
screen. Headed, it reaches ~1,800 nodes. Every command runs headed.

### Search

The search box is present in the DOM but hidden from the accessibility tree, so
role-based selectors find nothing. It is located by placeholder
(`input[placeholder*='Search' i]`), and **a query only runs once Enter is
pressed** — GFN does not search as you type.

Waiting is condition-based rather than fixed: the tool waits for the target
tile to appear. A hit resolves in ~1.3 s; a title GFN does not carry costs the
3.5 s timeout. The first query after boot is much slower, so a throwaway
"warmup" search is issued first.

### Clicking the right tile

A subtle failure worth recording: computing an element index in JavaScript over
a *visibility-filtered* list and then using Playwright's `nth()` does not line
up, because `nth()` also counts hidden elements. Every click landed on the
`Filter` button instead of the game. The fix is to tag the target in the DOM
(`data-epicsync-target`) and click that attribute — no index arithmetic.

### Deep links

Games are reachable directly:

```
https://play.geforcenow.com/games?game-id=<uuid>&lang=en_US
```

The `audit` command uses this, which is faster than searching and immune to
title-matching problems. Game ids are harvested from tile artwork URLs
(`https://img.nvidiagrid.net/apps/<uuid>/...`) while scrolling the virtualised
`cdk-virtual-scroll-viewport` — 470 ids in about 21 seconds.

## The ownership flow

Clicking `MARK AS OWNED` opens `gfn-ownership-dialog`, whose text lives in
`gfn-ownership-stage-layout`:

```
Stage 1  "Finding where you own this game"
         "Checking all your connected accounts to sync this game..."
         "Syncing Steam and Xbox game libraries..."      [STOP RESYNC]

Stage 2  "Choose a game store"
         "Where do you own this game and want to play?"
         Game stores: | Epic Games Store | Steam → Game not found | Xbox → Game not found

Stage 3  "Press CONTINUE to manually mark this game as owned only if you
          have this in your Epic Games Store library"    [CONTINUE] [EXIT]
```

Stage 2 appears only when several storefronts carry the game. With a single
store, GFN jumps straight to stage 3 — for whichever store that is. This is
precisely why the safety gate is needed.

Notes:

- A store followed by `Game not found` is not selectable.
- Clicks in stage 2 must be scoped to the dialog. The same store name is
  rendered as a badge on the detail panel behind the overlay, and Playwright
  will resolve to that one and then fail because the overlay intercepts
  pointer events.
- Stage 3 names the store. `epicsync` presses `CONTINUE` only when that text
  contains `Epic Games Store`; otherwise it presses `EXIT`.

## Reverting a claim

The game page's `[aria-label="See more"]` menu contains:

- `Change game store`
- `Add shortcut`
- **`Unmark as owned`**
- `Visit game store`

`epicsync unmark` re-reads the storefront first, skips anything no longer
attributed to Epic, clicks the entry, confirms if a dialog appears, then
verifies the claim is gone.

## Detecting bad claims

GFN never validates a manual ownership claim. A game marked as owned but absent
from the real Epic library will fail to launch, because the cloud machine signs
in to Epic and cannot find it.

`epicsync audit` walks every entry in GFN's "My Library", records the storefront
GFN attributes to each, and flags anything claimed on Epic that `legendary` does
not report. The title is read from `[class*=evidence-panel-title-text]` — a
generic `h1` selector returns a stale value from the previous page.

### Matching is deliberately generous

Storefront titles rarely match library titles exactly:

| GFN | Epic library |
|---|---|
| `Metro Exodus PC Enhanced Edition` | `Metro Exodus Enhanced Edition` |
| `Zombie Army 4` | `Zombie Army 4 Dead War` |
| `The Textorcist: The Story of Ray Bibbia` | `The Textorcist` |
| `Rustler` | `Rustler - Grand Theft Horse` |

`same_game()` treats one title's words being a subset of the other's as a
match, because the error is asymmetric: a false "you do not own this" deletes
a legitimate claim, while a missed one merely leaves a game that will not
launch. Generosity stops at sequels — the extra words may not contain a bare
number or roman numeral, so `Battlefield` never absorbs `Battlefield 6`.

On the reference account this took the flagged set from 161 to 2, and both
survivors were genuine.

### Safeguards

- `suspects()` recomputes the library comparison every time instead of trusting
  the flag stored during the scan; a stale snapshot is exactly what produced
  the 161 false positives.
- It refuses to flag anything at all if the Epic library comes back empty.
- `unmark` prints every title and requires a typed `yes` (or `--yes`).
