# gfn-epicgames-sync

[![CI](https://github.com/mustafaer/gfn-epicgames-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/mustafaer/gfn-epicgames-sync/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%20%E2%80%93%203.13-blue)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](#install)
[![License](https://img.shields.io/badge/license-GPL--3.0-green)](LICENSE)

Bulk-mark your **Epic Games Store** library as owned on **GeForce NOW** — and
find the ownership claims that were marked by mistake.

The command is `epicsync`; the distribution installs from
`gfn-epicgames-sync`.

GeForce NOW syncs your library automatically for Steam, Ubisoft Connect, Xbox,
Battle.net and others. For the Epic Games Store it does not: the Connections
screen states plainly `Game library sync — Not supported`, and there is no
`RESYNC` button. Automatic sign-in covers Fortnite only. Every other Epic game
you own has to be marked by hand, one at a time.

This tool does that for you, and it will not lie on your behalf: it marks a
game only when your real Epic library actually contains it.

---

## What it does

1. Reads your Epic library through [legendary](https://github.com/legendary-gl/legendary),
   which uses Epic's official OAuth flow. **Your password is never entered into
   epicsync.**
2. Drives the GeForce NOW web client in your own signed-in browser session.
3. For every game you own, walks GFN's ownership flow and confirms **only when
   the dialog names the Epic Games Store**.

   Your library is always read for the **Windows** platform, because that is
   what GeForce NOW streams. Reading it for the host platform — legendary's
   default — hides most of the library on macOS and Linux.
4. Audits the other direction too — finds games GFN thinks you own on Epic that
   your Epic library does not contain, and reverts them.

## Install

Requires **Python 3.9+** and a desktop **Google Chrome** (or Edge) install.

```bash
git clone https://github.com/mustafaer/gfn-epicgames-sync
```

```bash
cd gfn-epicgames-sync && pip install .
```

Using a virtual environment is recommended:

```bash
python3 -m venv .venv && ./.venv/bin/pip install .
```

If you do not have Chrome or Edge, install Playwright's browser instead:

```bash
python -m playwright install chromium
```

<details>
<summary>Platform notes</summary>

| Platform | Status | Notes |
|---|---|---|
| **macOS** | Verified end to end | Chrome is picked up from `/Applications`. |
| **Linux** | Logic unit-tested, browser flow unverified | Install `google-chrome-stable` or `microsoft-edge-stable`, or use the bundled browser. Needs a display — see below. |
| **Windows** | Logic unit-tested, browser flow unverified | Use PowerShell or Windows Terminal; `cmd.exe` falls back to ASCII markers automatically. Stale browser locks must be cleared by hand ([troubleshooting](docs/troubleshooting.md)). |

Path resolution, `legendary` discovery, console encoding and process probing
are covered by tests that simulate all three platforms, and CI runs the suite
on each. What has not been exercised on Linux and Windows is the live browser
automation itself; reports are welcome.

**A display is required.** The GFN client is an Angular app that never finishes
bootstrapping in a headless browser — it stalls on the NVIDIA splash screen.
Every command therefore opens a real window. On a headless Linux box, run it
under `xvfb-run`.
</details>

## Quick start

```bash
legendary auth
```

```bash
epicsync login
```

```bash
epicsync sweep --dry-run
```

```bash
epicsync sweep
```

`sweep` is the recommended path: it checks every game you own against the live
GFN client. Progress is saved after each game, so you can stop at any time and
re-run to resume.

## Commands

| Command | Purpose |
|---|---|
| `epicsync auth` | Show Epic sign-in status |
| `epicsync login` | Sign in to the GFN web client (session is stored locally) |
| `epicsync sweep` | Check every owned game against the live client and mark it |
| `epicsync plan` | Match your library against NVIDIA's public catalog |
| `epicsync mark` | Mark only the games from `plan` |
| `epicsync audit` | Find Epic claims your library cannot back |
| `epicsync unmark` | Revert those incorrect claims |
| `epicsync status` | Summarize saved progress |
| `epicsync where` | Print the data directory |
| `epicsync inspect "<title>"` | Dump a game page's controls (UI calibration) |

Add `--dry-run` to `sweep`, `mark` and `unmark` to see what would happen
without changing anything. Full options for every command are in the
[command reference](docs/commands.md).

## How marking works

`MARK AS OWNED` is not a single click. It is a three-stage flow:

1. **Resync** — *"Finding where you own this game"*. GFN re-checks your
   connected store accounts (~10–15 s). Epic is never found here, because Epic
   library sync is not supported; this stage alone never succeeds.
2. **Store picker** — *"Choose a game store"*, shown when several storefronts
   carry the game. Stores you do not own it on are tagged `Game not found`.
   epicsync selects **Epic Games Store**.
3. **Confirmation** — *"Press CONTINUE to manually mark this game as owned"*.
   This is an assertion by you, not something GFN verifies.

### The safety gate

The confirmation names the storefront it is about to mark. **epicsync refuses
to press `CONTINUE` unless that text contains `Epic Games Store`**, and clicks
`EXIT` instead. Without this, a game whose GFN entry resolves to Steam would be
recorded as a Steam purchase you may not own.

A `BUY` button sits directly beside `MARK AS OWNED`. Any control whose label
contains `BUY`, `PURCHASE`, `SUBSCRIBE` or `UPGRADE` is excluded from every
click path in the code.

## Known limitations

- **Already-playable games cannot be re-attributed.** If GFN already sources a
  game from Steam, no `MARK AS OWNED` control is rendered, so its Epic
  ownership cannot be added. `epicsync status` lists these.
- **GFN does not offer Epic for every title.** Some games show
  `Game not found` next to Epic in the picker. Nothing can be done there.
- **NVIDIA's public catalog is incomplete and can be stale.** It lists roughly
  1,550 games while the live client reports about 2,200, and some storefront
  entries disagree with the live UI. This is why `sweep` bypasses it and
  `plan`/`mark` are kept only as a fast approximation.
- **Marking is an assertion.** Claiming a game you do not own means it will
  fail to launch. `epicsync audit` exists to catch exactly that.
- **Audit results are candidates, not verdicts.** Title matching between GFN
  and Epic is heuristic. `unmark` always lists what it will touch and requires
  a typed confirmation; review the list before agreeing.

## Where data is stored

Run `epicsync where` to see the exact path.

| Platform | Location |
|---|---|
| macOS | `~/Library/Application Support/gfn-epicgames-sync` |
| Linux | `$XDG_DATA_HOME/gfn-epicgames-sync` (default `~/.local/share/gfn-epicgames-sync`) |
| Windows | `%LOCALAPPDATA%\gfn-epicgames-sync` |

Override with the `EPICSYNC_DATA_DIR` environment variable. The directory holds
your browser session, progress state and cached library data — treat it as
private.

## Roadmap

- Publish to PyPI so `pip install gfn-epicgames-sync` works without cloning
- Re-attribute games GFN already sources from another store, if NVIDIA ever
  exposes the `Change game store` action for owned titles

## Documentation

- [Command reference](docs/commands.md) — every command, option and output file
- [How it works](docs/how-it-works.md) — the reverse-engineered flow in detail
- [Troubleshooting](docs/troubleshooting.md) — when the UI changes or a run fails
- [Contributing](CONTRIBUTING.md)

## Disclaimer

Not affiliated with, endorsed by, or sponsored by NVIDIA or Epic Games. It
automates an action you can already perform by hand in your own account, on
games you already own. You are responsible for the ownership you assert.

Licensed under the [GNU General Public License v3.0](LICENSE).
